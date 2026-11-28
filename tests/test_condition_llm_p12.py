import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import httpx

from tests.local_data import LLM_P12_CLAIM, needs
from tools import run_condition_llm_p12 as p

@contextmanager
def isolated():
    if not p.CLAIM.exists():  # 실행 PC에만 있는 p12 claim(tests/local_data.py)
        raise unittest.SkipTest(f'로컬 전용 데이터 없음: {p.CLAIM.name}')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);out=root/'run';claim=root/'claim.json'
        shutil.copytree(p.OUT,out);shutil.copy2(p.CLAIM,claim)
        with patch.object(p,'OUT',out),patch.object(p,'CLAIM',claim),patch.object(p.base,'LOCK_PATH',root/'lock'):
            yield out

class P12Tests(unittest.TestCase):
    def test_error_details_and_reproduction(self):
        with isolated() as out:
            failure=p.classify_schema_failure(out/'notice_08')
            self.assertTrue(failure['evaluation_eligible'])
            self.assertFalse(failure['extraction_succeeded'])
            self.assertEqual(failure['diagnostic_proposal_count'],10)
            error=failure['intermediate_schema_errors'][0]
            self.assertEqual(error['json_path'],['conditions',5,'operator'])
            self.assertEqual(error['actual_value'],'UNKNOWN')
            self.assertEqual(error['violated_rule'],'enum')
            self.assertTrue(error['error_reproduced'])

    def test_internal_error_not_evaluable(self):
        with isolated() as out:
            path=out/'notice_08/per_notice_execution.jsonl'
            rows=p.llm._read_jsonl(path);rows[0]['status']='PROVIDER_ERROR'
            p.llm._write_jsonl(path,rows)
            with self.assertRaisesRegex(RuntimeError,'NOT_A_REPRODUCIBLE'):
                p.classify_schema_failure(out/'notice_08')

    def test_corrupt_response_not_evaluable(self):
        with isolated() as out:
            path=out/'notice_08/raw_llm_responses.jsonl'
            path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaisesRegex(RuntimeError,'INTEGRITY'):
                p.classify_schema_failure(out/'notice_08')

    def test_success_output_cannot_be_classified_as_failure(self):
        with isolated() as out:
            with self.assertRaisesRegex(RuntimeError,'NOT_A_REPRODUCIBLE'):
                p.classify_schema_failure(out/'notice_07')

    def test_preserved_candidates_logic_and_raw_bytes(self):
        with isolated() as out:
            report=p.base.read_json(out/'preparation_report.json')
            for rel,expected in report['copied_file_hashes'].items():
                self.assertEqual(p.base.digest(out/rel),expected)

    def test_manifest_classifies_http_schema_and_budget(self):
        with isolated() as out:
            m=p.update_manifest()
            self.assertEqual(len(m['http_response_notice_ids']),9)
            self.assertEqual(len(m['technical_pass_notice_ids']),8)
            self.assertEqual(len(m['evaluation_eligible_notice_ids']),9)
            self.assertEqual(m['api_connection_failure_notice_ids'],[])
            self.assertEqual(m['schema_failure_notice_ids'],['KSTARTUP:178507'])
            self.assertEqual(m['unexecuted_notice_ids'],['KSTARTUP:179386'])
            self.assertEqual((m['cumulative_used'],m['remaining_request_count']),(12,1))

    def test_budget_only_ordinal_13(self):
        with isolated() as out,p.configured_engine():
            b=p.engine.P8Budget('synthetic-test-only')
            self.assertTrue(b.consume());self.assertEqual(b.last_request_ordinal,13)
            self.assertFalse(b.consume())

    def test_fingerprint_and_claim_tamper_blocks_cli(self):
        with isolated() as out:
            path=out/'manifest.json';m=p.base.read_json(path)
            m['fingerprint']['limit']=99;p.base.write_json_atomic(path,m)
            with patch.object(sys,'argv',['p12','--check-execution']),self.assertRaisesRegex(RuntimeError,'FINGERPRINT'):
                p.main()
        with isolated() as out:
            p.base.write_json_atomic(p.CLAIM,{'fingerprint_sha256':'wrong'})
            with patch.object(sys,'argv',['p12','--check-execution']),self.assertRaisesRegex(RuntimeError,'CLAIM'):
                p.main()

    @needs(LLM_P12_CLAIM)
    def test_real_subprocess_cli_preflight(self):
        # CLI checks read immutable real inputs; all output/ledger locations are temporary.
        script='''
import sys
from unittest.mock import patch
from tests.test_condition_llm_p12 import isolated
from tools import run_condition_llm_p12 as p
with isolated(),patch.object(sys,'argv',['p12','--check-execution']):
    p.main()
'''
        r=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'],'EXECUTION_PREFLIGHT_PASS')

    def test_cli_batch_sdk_then_ten_notice_evaluation_offline(self):
        # Real SDK and batch; only HTTP transport, credentials and artifact directory replaced.
        with isolated() as out:
            actual=p.llm.OpenAIDirectProvider;providers=[];requests=[]
            def handler(request):
                requests.append(request)
                return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,
                    'model':'gpt-5.6-luna','choices':[{'index':0,'finish_reason':'stop',
                    'message':{'role':'assistant','content':'{}'}}]})
            def factory(**kwargs):
                kwargs['http_client']=httpx.AsyncClient(transport=httpx.MockTransport(handler))
                provider=actual(**kwargs);providers.append(provider);return provider
            with patch.object(p.llm,'OpenAIDirectProvider',side_effect=factory),\
                 patch.object(p.llm,'load_env_safely',return_value={'OPENAI_API_KEY':'offline','OPENAI_CHAT_MODEL':'gpt-5.6-luna'}),\
                 patch.object(sys,'argv',['p12','--run-remaining','--authorize-api']):
                p.main()
            self.assertEqual(len(requests),1)
            self.assertTrue(providers[0].client.is_closed())
            ledger=p.base.read_json(out/'request_ledger.json')
            self.assertEqual(ledger['used'],13)
            self.assertEqual(ledger['p8_attempts'][0]['notice_id'],'KSTARTUP:179386')
            self.assertEqual(ledger['p8_attempts'][0]['request_ordinal'],13)
            m=p.base.read_json(out/'manifest.json')
            self.assertTrue(m['evaluation_ready'])
            self.assertEqual(len(m['technical_pass_notice_ids']),8)
            result=p.evaluate()
            self.assertEqual(len(result['notice_ids']),10)
            self.assertEqual(result['gold_condition_count'],62)
            details=p.base.read_json(out/'strict_logic_and_condition_report.json')['notices']
            failure=next(r for r in details if r['notice_id']=='KSTARTUP:178507')
            self.assertEqual(failure['common']['tp'],0)
            self.assertGreater(failure['common']['fn'],0)
            self.assertEqual(result['evaluation_inclusion_rate'],1)

if __name__=='__main__':unittest.main()
