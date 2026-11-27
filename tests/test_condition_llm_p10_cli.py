"""Exercise the CLI parser, fingerprint, claim, ledger, batch, SDK and cleanup offline."""
import json
import subprocess
import sys
import unittest
from tools import run_condition_llm_p10 as p10


class P10CLITests(unittest.TestCase):
    def test_fingerprint_is_identical_inside_and_outside_engine_context(self):
        saved = p10.base.read_json(p10.OUT / 'manifest.json')['fingerprint']
        self.assertEqual(saved, p10.fingerprint())
        with p10.configured_engine():
            self.assertEqual(saved, p10.engine.build_fingerprint())
            self.assertEqual(p10.engine.RUN_ID, p10.RUN_ID)
            self.assertEqual(saved['source_run_id'], p10.SOURCE_RUN_ID)

    def test_actual_offline_cli_preflight(self):
        result = subprocess.run([sys.executable, str(p10.Path(p10.__file__)), '--check-execution'],
                                capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'EXECUTION_PREFLIGHT_PASS')
        self.assertEqual((report['requests_used'], report['remaining']), (10,3))

    def test_live_cli_entry_uses_real_batch_and_sdk_with_mock_transport_and_temporary_ledger(self):
        # The child invokes the same main()/argparse entry with live-mode arguments.
        # Only HTTP transport, credential loading, and artifact locations are isolated.
        script = r'''
import json, shutil, socket, sys, tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
from tools import run_condition_llm_p10 as p
protected = [p.OUT/'request_ledger.json', p.SOURCE/'request_ledger.json']
protected += [x for x in p.SOURCE.rglob('raw_llm_responses.jsonl')]
before = {x:p.base.digest(x) for x in protected}
real_provider = p.llm.OpenAIDirectProvider
real_connect = socket.socket.connect
def guarded_connect(sock, address):
    # Windows asyncio's self-pipe uses a loopback socketpair.
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
        return real_connect(sock, address)
    raise AssertionError('EXTERNAL_NETWORK_FORBIDDEN')
providers = []
requests = []
def handler(request):
    requests.append(request)
    return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,
        'model':'gpt-5.6-luna','choices':[{'index':0,'finish_reason':'stop',
        'message':{'role':'assistant','content':'{}'}}]})
def factory(**kwargs):
    kwargs['http_client'] = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = real_provider(**kwargs)
    providers.append(provider)
    return provider
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)/'run'
    shutil.copytree(p.OUT,out)
    claim = Path(tmp)/'claim.json'
    shutil.copy2(p.CLAIM,claim)
    with patch.object(p,'OUT',out), patch.object(p,'CLAIM',claim), \
         patch.object(p.base,'LOCK_PATH',Path(tmp)/'lock'), \
         patch.object(p.llm,'load_env_safely',return_value={'OPENAI_API_KEY':'offline-key','OPENAI_CHAT_MODEL':'gpt-5.6-luna'}), \
         patch.object(p.llm,'OpenAIDirectProvider',side_effect=factory), \
         patch.object(socket.socket,'connect',guarded_connect), \
         patch.object(sys,'argv',['run_condition_llm_p10.py','--run-remaining','--authorize-api']):
        assert p.main()==0
    ledger=p.base.read_json(out/'request_ledger.json')
    assert ledger['used']==11 and ledger['p8_attempts'][0]['request_ordinal']==11
    assert ledger['p8_attempts'][0]['notice_id']=='KSTARTUP:177447'
    assert len(requests)==1 and len(providers)==1 and providers[0].client.is_closed()
    assert p.base.read_json(out/'notice_07/run_report.json')['failure_count']==1
assert before=={x:p.base.digest(x) for x in protected}
print('CLI_BATCH_SDK_MOCK_PASS; PRODUCTION_HASHES_PRESERVED')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('CLI_BATCH_SDK_MOCK_PASS; PRODUCTION_HASHES_PRESERVED', result.stdout)

if __name__ == '__main__':
    unittest.main()
