"""P12: preserve schema-invalid responses as evaluable failures; one final request."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import run_condition_llm_p10 as prior
from tools import run_condition_llm_openai_pilot_r2_norm_v2_p8 as engine
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as base
from tools import extract_condition_candidates_llm as llm
from tools import evaluate_condition_pipeline_v11 as evaluator

SOURCE = prior.OUT
RUN_ID = 'llm_pilot_2_5c3_r2_p12'
OUT = base.DEV / RUN_ID
CLAIM = base.DEV / '.llm_pilot_2_5c3_r2_p12_claim.json'
pilot = engine.pilot_r2.prior

def fingerprint():
    ledger = base.read_json(SOURCE/'request_ledger.json')
    if ledger['used'] != 12 or ledger['limit'] != 13 or base.read_json(SOURCE/'manifest.json')['status'] != 'P8_BLOCKED':
        raise RuntimeError('P12_SOURCE_STATE_CHANGED')
    ids, frozen = base.verify_14_fixed_checks()
    files = [p for p in SOURCE.rglob('*') if p.is_file()]
    files += [Path(__file__), Path(llm.__file__), Path(engine.__file__), Path(base.__file__), Path(evaluator.__file__),
              Path(prior.__file__), base.PARENT_RAW, Path(pilot.__file__)]
    return {'run_id':RUN_ID,'source_run_id':'llm_pilot_2_5c3_r2_norm_v2_p10',
            'files':{p.relative_to(ROOT).as_posix():base.digest(p) for p in sorted(set(files))},
            'pilot_notice_ids':ids,'fixed_inputs':frozen,'limit':13,'inherited_used':12,
            'prompt_sha256':hashlib.sha256(llm.system_prompt().encode()).hexdigest(),
            'normalization_sha256':llm.ATTRIBUTE_NORMALIZATION_RULES_SHA256,
            'generation_settings':base.read_json(base.PARENT_MANIFEST)['fingerprint']}

def classify_schema_failure(directory: Path):
    raw_path = directory/'raw_llm_responses.jsonl'
    rows = llm._read_jsonl(raw_path)
    report = base.read_json(directory/'run_report.json')
    expected_hash = report['artifact_hashes']['raw_llm_responses.jsonl']
    if base.digest(raw_path) != expected_hash or len(rows) != 1:
        raise RuntimeError('RESPONSE_INTEGRITY_VIOLATION')
    row = rows[0]
    execution = llm._read_jsonl(directory/'per_notice_execution.jsonl')
    if (len(execution) != 1 or execution[0]['status'] != 'SCHEMA_VALIDATION_ERROR'
            or row.get('provider_metadata',{}).get('http_status') != 200
            or row['provider_metadata'].get('finish_reason') != 'stop'
            or row.get('provider_error') or len(row.get('response_attempts',[])) != 1):
        raise RuntimeError('NOT_A_REPRODUCIBLE_LLM_SCHEMA_FAILURE')
    for name in ['predictions_after_validation.jsonl','llm_condition_predictions.jsonl','notice_condition_sets.jsonl']:
        if llm._read_jsonl(directory/name):
            raise RuntimeError('UNEXPECTED_VALIDATED_OUTPUT_ON_FAILURE')
    text = row['response_attempts'][0]
    original = json.loads(text)
    errors = llm.intermediate_schema_diagnostics(row['notice_id'],text)
    if not errors:
        raise RuntimeError('SCHEMA_FAILURE_NOT_REPRODUCED')
    return {'notice_id':row['notice_id'],'execution_status':'SCHEMA_VALIDATION_ERROR',
            'response_received':True,'json_parsed':True,'extraction_succeeded':False,
            'evaluation_eligible':True,'decision_eligible':False,'technical_gate_status':'EXTRACTION_FAILED',
            'source_file_sha256':base.digest(raw_path),'diagnostic_proposal_count':len(original.get('conditions',[])),
            'validated_candidate_count':0,'intermediate_schema_errors':errors,
            'post_validation_prediction_policy':'EMPTY_PREDICTIONS',
            'pre_validation_policy':'EXISTING_PREVALIDATION_ADAPTER_WITH_RAW_UNMODIFIED_PROPOSALS'}

def states():
    ids = base.read_json(OUT/'manifest.json')['fingerprint']['pilot_notice_ids']
    result=[]
    for i,nid in enumerate(ids):
        if i==0:
            result.append({'notice_id':nid,'response_received':True,'json_parsed':True,
                'extraction_succeeded':True,'technical_gate_pass':True,'evaluation_eligible':True,
                'decision_eligible':False,'validated_candidate_count':4})
            continue
        d=OUT/f'notice_{i:02d}'
        if not (d/'run_report.json').exists():
            result.append({'notice_id':nid,'unexecuted':True,'evaluation_eligible':False});continue
        report=base.read_json(d/'run_report.json')
        status=next(iter(report['status_counts']))
        if status=='SCHEMA_VALIDATION_ERROR':
            result.append({**classify_schema_failure(d),'technical_gate_pass':False});continue
        raw=llm._read_jsonl(d/'raw_llm_responses.jsonl')
        received=bool(raw and raw[0].get('provider_metadata',{}).get('http_status')==200)
        gate=base.read_json(d/'technical_gate.json') if (d/'technical_gate.json').exists() else {}
        parsed=False
        if received and raw[0].get('response_attempts'):
            try: json.loads(raw[0]['response_attempts'][-1]);parsed=True
            except (ValueError,TypeError):pass
        result.append({'notice_id':nid,'execution_status':status,'response_received':received,
            'json_parsed':parsed,'extraction_succeeded':status=='COMPLETED' and gate.get('status')=='PASS',
            'technical_gate_pass':gate.get('status')=='PASS','evaluation_eligible':status=='COMPLETED' and gate.get('status')=='PASS',
            'api_connection_failed':status=='CONNECTION_ERROR','decision_eligible':False,
            'validated_candidate_count':report['condition_count']})
    return result

def update_manifest():
    manifest=base.read_json(OUT/'manifest.json');ledger=base.read_json(OUT/'request_ledger.json')
    records=states()
    fields={'http_response_notice_ids':'response_received','json_parsed_notice_ids':'json_parsed',
            'technical_pass_notice_ids':'technical_gate_pass','evaluation_eligible_notice_ids':'evaluation_eligible',
            'api_connection_failure_notice_ids':'api_connection_failed','unexecuted_notice_ids':'unexecuted'}
    for name,key in fields.items():manifest[name]=[r['notice_id'] for r in records if r.get(key)]
    manifest['schema_failure_notice_ids']=[r['notice_id'] for r in records if r.get('execution_status')=='SCHEMA_VALIDATION_ERROR']
    manifest['evaluable_failure_notice_ids']=[r['notice_id'] for r in records if r.get('evaluation_eligible') and not r.get('extraction_succeeded')]
    manifest.update({'cumulative_used':ledger['used'],'remaining_request_count':ledger['limit']-ledger['used'],
        'api_call_count':len(ledger['p8_attempts']),'evaluation_ready':all(r['evaluation_eligible'] for r in records),
        'decision_eligible':False})
    if manifest['evaluation_ready']:manifest['status']='EVALUATION_READY'
    base.write_json_atomic(OUT/'manifest.json',manifest)
    base.write_json_atomic(OUT/'execution_states.json',records)
    return manifest

def prepare():
    with base.successor_lock():
        fp=fingerprint()
        if (OUT/'manifest.json').exists():
            if base.read_json(OUT/'manifest.json')['fingerprint']!=fp:raise RuntimeError('P12_FINGERPRINT_CHANGED')
            return base.read_json(OUT/'preparation_report.json')
        if OUT.exists() and any(OUT.iterdir()):raise RuntimeError('P12_OUTPUT_EXISTS')
        failure=classify_schema_failure(SOURCE/'notice_08')
        preservation={}
        for name in ['lead_replay_v2']+[f'notice_{i:02d}' for i in range(1,9)]:
            shutil.copytree(SOURCE/name,OUT/name)
            for p in (SOURCE/name).rglob('*'):
                if p.is_file():
                    dest=OUT/p.relative_to(SOURCE)
                    if p.read_bytes()!=dest.read_bytes():raise RuntimeError('COPY_INTEGRITY_FAILURE')
                    preservation[p.relative_to(SOURCE).as_posix()]=base.digest(p)
        base.write_json_atomic(OUT/'notice_08/evaluable_failure.json',failure)
        llm._write_jsonl(OUT/'notice_08/intermediate_schema_errors_reproduced.jsonl',failure['intermediate_schema_errors'])
        ledger=copy.deepcopy(base.read_json(SOURCE/'request_ledger.json'))
        ledger['prior_p10_attempts']=ledger['p8_attempts'];ledger['p8_attempts']=[]
        ledger['lineage'].update({'p12_source_ledger_sha256':base.digest(SOURCE/'request_ledger.json'),
                                   'p12_new_budget_granted':0,'p12_allowed_ordinals':[13]})
        base.write_json_atomic(OUT/'request_ledger.json',ledger)
        base.claim_single_successor(CLAIM,{'run_id':RUN_ID,'source_ledger_sha256':base.digest(SOURCE/'request_ledger.json'),
            'fingerprint_sha256':hashlib.sha256(json.dumps(fp,sort_keys=True).encode()).hexdigest()})
        base.write_json_atomic(OUT/'manifest.json',{'run_id':RUN_ID,'status':'PREPARED_NO_API_CALLS','fingerprint':fp,
            'request_limit':13,'cumulative_used':12,'remaining_request_count':1,'api_call_count':0,
            'prepared_unexecuted_notice_ids':fp['pilot_notice_ids'][9:],'decision_eligible':False})
        manifest=update_manifest()
        result={'status':manifest['status'],'api_call_count':0,'responses_preserved':9,
            'technical_pass_count':len(manifest['technical_pass_notice_ids']),
            'evaluation_eligible_count':len(manifest['evaluation_eligible_notice_ids']),
            'schema_failure_count':len(manifest['schema_failure_notice_ids']),
            'request_limit':13,'requests_used':12,'remaining':1,'copied_file_hashes':preservation}
        base.write_json_atomic(OUT/'preparation_report.json',result)
        base.write_json_atomic(OUT/'quality_improvement_todo.json',[
            '한글 field 정규화','field/category_id 의미 정합성','hiring_target','team_member_age',
            'residence/residence_proof','military_service_proof','BETWEEN minimum/maximum',
            'UNKNOWN operator','프롬프트/중간 스키마 정합성','속성 카탈로그 확장 및 단일화'])
        return result

async def final_batch(env,fp):
    expected=fp['generation_settings']
    provider=llm.OpenAIDirectProvider(api_key=env['OPENAI_API_KEY'],model=expected['model_id'],
        timeout_s=expected['timeout_seconds'],max_completion_tokens=expected['max_completion_tokens'],
        reasoning_effort=expected['reasoning_effort'])
    try:
        if fingerprint()!=fp:raise RuntimeError('P12_FINGERPRINT_CHANGED')
        nid=fp['pilot_notice_ids'][9];d=OUT/'notice_09'
        if d.exists() or base.read_json(OUT/'request_ledger.json')['p8_attempts']:
            raise RuntimeError('P12_DUPLICATE_REQUEST_BLOCKED')
        report=await llm.run_pilot(provider,[nid],output_dir=d,request_budget=engine.P8Budget(nid),max_format_attempts=1)
        succeeded=report['status_counts'].get('COMPLETED')==1
        engine.finish_attempt(nid,'COMPLETED' if succeeded else 'FAILED_RESPONSE')
        if succeeded:
            offline=base.replay_notice(d/'raw_llm_responses.jsonl',d)
            base.write_json_atomic(d/'technical_gate.json',base.tech_gate_for_notice(d,offline))
        elif report['status_counts'].get('SCHEMA_VALIDATION_ERROR')==1:
            base.write_json_atomic(d/'evaluable_failure.json',classify_schema_failure(d))
        manifest=update_manifest()
        if not manifest['evaluation_ready']:
            manifest['status']='P12_BLOCKED';base.write_json_atomic(OUT/'manifest.json',manifest)
        return {'status':manifest['status'],'requests_used':manifest['cumulative_used'],
                'remaining':manifest['remaining_request_count'],'api_call_count':manifest['api_call_count']}
    finally:await provider.aclose()

@contextmanager
def configured_engine():
    with patch.multiple(engine,RUN_ID=RUN_ID,RUN_DIR=OUT,ALREADY_USED=12,P8_MAX_REQUESTS=1,
        START_INDEX=9,CLAIM_PATH=CLAIM,build_fingerprint=fingerprint,_run_remaining_async=final_batch):yield

def evaluate():
    if fingerprint()!=base.read_json(OUT/'manifest.json')['fingerprint']:raise RuntimeError('P12_FINGERPRINT_CHANGED')
    manifest=update_manifest()
    if not manifest['evaluation_ready']:raise RuntimeError('TEN_NOTICE_EVALUATION_NOT_READY')
    ids=manifest['fingerprint']['pilot_notice_ids'];idset=set(ids)
    gold=[r for r in pilot.read_jsonl(pilot.GOLD/'reviewed_condition_gold.jsonl') if r['notice_id'] in idset]
    logic_gold=[r for r in pilot.read_jsonl(pilot.GOLD/'reviewed_logic_gold.jsonl') if r['notice_id'] in idset]
    total=sum(len(r.get('gold_conditions',[]))+len(r.get('missed_condition_candidates',[])) for r in gold)
    if len(gold)!=10 or total!=62:raise RuntimeError('FROZEN_10_NOTICE_62_CONDITION_MISMATCH')
    post=[];pre=[];logic=[]
    for i,nid in enumerate(ids):
        d=OUT/'lead_replay_v2' if i==0 else OUT/f'notice_{i:02d}'
        failure=(d/'evaluable_failure.json').exists()
        if failure:
            classify_schema_failure(d)
            raw=llm._read_jsonl(d/'raw_llm_responses.jsonl')[0]
            obj=json.loads(raw['response_attempts'][-1])
        else:
            replay_dir=d if i==0 else d/'attribute_replay_v2'
            post.extend(r['candidate'] for r in llm._read_jsonl(replay_dir/'predictions_after_validation.jsonl'))
            obj={'conditions':[r['proposal'] for r in llm._read_jsonl(replay_dir/'predictions_before_validation.jsonl')]}
            sets=llm._read_jsonl(d/'notice_condition_sets.jsonl') if (d/'notice_condition_sets.jsonl').exists() else []
            if not sets and i==0:
                inputs={r['notice_id']:r for r in llm._read_jsonl(llm.INPUTS)}
                original=json.loads(llm._read_jsonl(base.PARENT_RAW)[0]['response_attempts'][-1])
                record=llm._response_to_artifacts(inputs[nid],original)['notice_set']
                if record:sets=[record]
            logic.extend(sets)
        pre.append({'notice_id':nid,'intermediate_response':obj})
    named={'baseline_v1':[r for r in pilot.read_jsonl(pilot.BASELINE_OUT) if r['notice_id'] in idset],
           'rule_experiment_E':[r for r in pilot.read_jsonl(pilot.RULE_E) if r['notice_id'] in idset],
           'llm_pre_validation':pilot.prevalidation_predictions(pre,pilot.INPUTS),'llm_post_validation':post}
    comparisons={name:pilot.evaluate_conditions(gold,preds) for name,preds in named.items()}
    rows,summary=pilot.comparison_rows(comparisons)
    pilot.write_csv(OUT/'pilot_baseline_comparison.csv',rows)
    logic_report=evaluator.evaluate_records(gold,logic_gold,post,logic)
    base.write_json_atomic(OUT/'strict_logic_and_condition_report.json',logic_report)
    counts={key:len(manifest[key]) for key in ['http_response_notice_ids','technical_pass_notice_ids',
        'evaluation_eligible_notice_ids','schema_failure_notice_ids']}
    result={'status':'PILOT_EVALUATED','notice_ids':ids,'gold_condition_count':total,'evaluation':summary,
        'execution_counts':counts,'api_response_success_rate':counts['http_response_notice_ids']/10,
        'technical_extraction_success_rate':counts['technical_pass_notice_ids']/10,
        'evaluation_inclusion_rate':counts['evaluation_eligible_notice_ids']/10,
        'zero_validated_candidate_count':sum(r.get('validated_candidate_count')==0 for r in states()),
        'prevalidation_policy':'EXISTING_ADAPTER_RAW_PROPOSALS_INCLUDING_SCHEMA_INVALID_RESPONSE',
        'decision_eligible':False}
    base.write_json_atomic(OUT/'evaluation_summary.json',result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    for mode in ['prepare','check-execution','run-remaining','evaluate']:modes.add_argument('--'+mode,action='store_true')
    parser.add_argument('--authorize-api',action='store_true');parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    args=parser.parse_args()
    if args.run_remaining and not args.authorize_api:parser.error('--run-remaining requires --authorize-api')
    if args.authorize_api and not args.run_remaining:parser.error('--authorize-api only applies to --run-remaining')
    if args.prepare:result=prepare()
    elif args.evaluate:result=evaluate()
    else:
        with configured_engine():result=engine.run_remaining(args.env_file,check_only=args.check_execution)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
