"""Offline N0--N5 experiments on frozen P12 responses; existing validators/evaluator only."""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import condition_safe_normalization_experiment as normal
from tools import extract_condition_candidates_llm as llm
from tools import replay_condition_llm_attribute_normalization as replay
from tools import run_condition_llm_p12 as p12

DEFAULT=p12.base.DEV/'condition_normalization_2_5c3d2c_v1'
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):p12.base.write_json_atomic(path,value)
def rows(path,value):llm._write_jsonl(path,value)
def csv_write(path,records):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
def refs(node):
    if isinstance(node,dict):
        if node.get('node_type')=='CONDITION_REF':yield node['condition_id']
        for value in node.values():yield from refs(value)
    elif isinstance(node,list):
        for value in node:yield from refs(value)

def run(out):
    if out.exists():raise FileExistsError('Refusing existing experiment output')
    out.mkdir(parents=True)
    source=p12.OUT
    ids=p12.base.read_json(source/'manifest.json')['fingerprint']['pilot_notice_ids']
    protected=[p for p in source.rglob('*') if p.is_file()]
    protected += [p for p in normal.CONTRACT.iterdir() if p.is_file()]
    protected += [p for p in (ROOT/'schemas/conditions').glob('*.json')]
    protected += [llm.INPUTS,llm.SAMPLES,p12.base.PARENT_RAW,Path(llm.__file__),Path(replay.__file__),
        Path(p12.evaluator.__file__),Path(p12.pilot.__file__),ROOT/'tools/evaluate_condition_pipeline.py',
        p12.pilot.GOLD/'reviewed_condition_gold.jsonl',p12.pilot.GOLD/'reviewed_logic_gold.jsonl',p12.pilot.GOLD/'manifest.json']
    protected_hash={p.relative_to(ROOT).as_posix():digest(p) for p in protected}
    ledger=p12.base.read_json(source/'request_ledger.json');assert (ledger['used'],ledger['limit'])==(13,13)
    saved=p12.base.read_json(source/'evaluation_summary.json')
    inputs={r['notice_id']:r for r in llm._read_jsonl(llm.INPUTS)}
    # No gold records are passed to the normalizer; scoring happens after predictions are generated.
    spec=normal.specification();write(out/'safe_normalization_subset_v1.json',spec)
    fp={'contract':digest(out/'safe_normalization_subset_v1.json'),
        'normalizer':digest(normal.__file__),'runner':digest(__file__),
        'preserved_sources':protected_hash,'api_call_count':0}
    all_preds={};all_details={};change_logs=[];reject_logs=[];reports={};norm_responses={}
    safety={'schema_errors':0,'evidence_span_errors':0,'reference_errors':0,'decision_eligible_true':0,
        'source_mutation_errors':0,'idempotency_errors':0,'temporal_errors':0,'logic_preservation_errors':0,
        'deterministic_replay_errors':0,'normalization_order_conflicts':0}
    for arm in normal.EXPERIMENTS:
        d=out/arm;d.mkdir();predictions=[];details=[];arm_changes=[];arm_reject=[]
        for i,nid in enumerate(ids):
            nd=d/f'notice_{i:02d}';nd.mkdir()
            rawpath=p12.base.PARENT_RAW if i==0 else source/f'notice_{i:02d}/raw_llm_responses.jsonl'
            raw=llm._read_jsonl(rawpath)[0];original=json.loads(raw['response_attempts'][-1]);response=copy.deepcopy(original)
            baseline_dir=source/('lead_replay_v2' if i==0 else f'notice_{i:02d}/attribute_replay_v2')
            base_details=llm._read_jsonl(baseline_dir/'validation_details.jsonl') if baseline_dir.exists() else []
            base_by={r['proposal_index']:r for r in base_details}
            schema_errors=list(llm.INTERMEDIATE_VALIDATOR.iter_errors(original))
            if schema_errors:
                failure=p12.classify_schema_failure(source/f'notice_{i:02d}')
                rows(nd/'original_proposals_diagnostic.jsonl',[{'notice_id':nid,'proposal_index':j,'proposal':c} for j,c in enumerate(original['conditions'])])
                write(nd/'evaluable_failure.json',failure)
                rows(nd/'condition_predictions.jsonl',[])
                arm_reject.append({'experiment':arm,'notice_id':nid,'proposal_index':None,
                    'reason':'SCHEMA_REJECTION_RESPONSE_WIDE','original_response_sha256':digest(rawpath),
                    'diagnostic_proposal_count':len(original['conditions']),'contract_version':normal.VERSION})
                details.extend({'notice_id':nid,'proposal_index':j,'final_status':'SCHEMA_REJECTED',
                    'reason':'SCHEMA_VALIDATION_ERROR','candidate_id':None} for j in range(len(original['conditions'])))
                norm_responses[(arm,nid)]=original
                continue
            preliminary=[]
            for index,condition in enumerate(original['conditions']):
                before=copy.deepcopy(condition)
                transformed,events,refusals=normal.normalize(condition,arm,inputs[nid]['raw_text'])
                response['conditions'][index]=transformed
                assert before==condition
                assert normal.normalize(condition,arm,inputs[nid]['raw_text'])[0]==transformed
                if normal.normalize(transformed,arm,inputs[nid]['raw_text'])[0]!=transformed:safety['idempotency_errors']+=1
                for key in condition:
                    if key not in ['unit','value','value_type'] and condition[key]!=transformed[key]:
                        safety['source_mutation_errors']+=1
                if condition.get('temporal_constraint')!=transformed.get('temporal_constraint'):safety['temporal_errors']+=1
                for refusal in refusals:
                    arm_reject.append({'experiment':arm,'notice_id':nid,'proposal_index':index,**refusal,'contract_version':normal.VERSION})
                if events:preliminary.append((index,events))
            assert not list(llm.INTERMEDIATE_VALIDATOR.iter_errors(response))
            norm_responses[(arm,nid)]=response
            rows(nd/'normalization_input.jsonl',[{'notice_id':nid,'intermediate_response':response}])
            rd=nd/'replay';report=replay.replay(nd/'normalization_input.jsonl',rd)
            artifacts=llm._response_to_artifacts(inputs[nid],response)
            sets=[artifacts['notice_set']] if artifacts['notice_set'] else []
            errors=llm.validate_artifacts(artifacts['conditions'],sets)
            safety['schema_errors']+=len(errors)
            write(nd/'schema_validation.json',{'errors':errors,'v11_schema_error_count':report['v11_schema_error_count']})
            rows(nd/'notice_condition_sets.jsonl',sets)
            candidate_rows=llm._read_jsonl(rd/'predictions_after_validation.jsonl')
            valid=llm._read_jsonl(rd/'validation_details.jsonl');valid_by={r['proposal_index']:r for r in valid}
            details.extend(valid);new_by={r['proposal_index']:r['candidate'] for r in candidate_rows}
            baseline_rows=llm._read_jsonl(baseline_dir/'predictions_after_validation.jsonl')
            old_by={r['proposal_index']:r['candidate'] for r in baseline_rows}
            for index,events in preliminary:
                arm_changes.append({'experiment':arm,'notice_id':nid,'proposal_index':index,
                    'old_candidate_id':base_by.get(index,{}).get('candidate_id'),
                    'new_candidate_id':valid_by[index].get('candidate_id'),
                    'original':normal.snapshot(original['conditions'][index]),'normalized':normal.snapshot(response['conditions'][index]),
                    'rules':events,'source_evidence':original['conditions'][index]['evidence_quotes'],
                    'old_span':old_by.get(index,{}).get('source',{}).get('location'),
                    'new_span':new_by.get(index,{}).get('source',{}).get('location'),
                    'validation_before':base_by.get(index),'validation_after':valid_by[index],
                    'original_response_sha256':digest(rawpath),'contract_version':normal.VERSION})
            for index,candidate in new_by.items():
                predictions.append(candidate)
                if index in old_by and (candidate['source']!=old_by[index]['source'] or candidate['evidence_references']!=old_by[index]['evidence_references']):
                    safety['evidence_span_errors']+=1
                location=candidate['source']['location']
                if inputs[nid]['raw_text'][location['start_char']:location['end_char']]!=candidate['raw_text']:
                    safety['evidence_span_errors']+=1
                if candidate['decision_eligible'] is not False:safety['decision_eligible_true']+=1
            ids_valid={r['condition_id'] for r in artifacts['conditions']}
            if not set(refs(sets)).issubset(ids_valid):safety['reference_errors']+=1
            proposal=artifacts['logic_proposal']
            if proposal['exceptions']!=original['exceptions'] or proposal['unresolved_relations']!=original['unresolved_relations']:
                safety['logic_preservation_errors']+=1
            if proposal['proposed_logic_sections']!=original['logic_sections']:safety['logic_preservation_errors']+=1
            if {int(x) for x in proposal['index_to_condition_id']}!={r['proposal_index'] for r in candidate_rows}:safety['reference_errors']+=1
            # Compare a second full replay's deterministic payloads in an isolated temporary path.
            with tempfile.TemporaryDirectory() as temp:
                second=Path(temp)/'replay';replay.replay(nd/'normalization_input.jsonl',second)
                for name in ['predictions_after_validation.jsonl','validation_details.jsonl','logic_proposals.jsonl']:
                    if digest(rd/name)!=digest(second/name):safety['deterministic_replay_errors']+=1
            rows(nd/'condition_predictions.jsonl',[r['candidate'] for r in candidate_rows])
        rows(d/'condition_predictions.jsonl',predictions);rows(d/'normalization_change_log.jsonl',arm_changes)
        rows(d/'normalization_rejections.jsonl',arm_reject)
        rows(d/'validation_details.jsonl',details)
        all_preds[arm]=predictions;all_details[arm]=details
        change_logs.extend(arm_changes);reject_logs.extend(arm_reject)
        arm_fp={**fp,'experiment':arm,'enabled_rules':normal.EXPERIMENTS[arm]}
        write(d/'normalization_experiment_manifest.json',{'experiment':arm,'fingerprint':arm_fp,
            'fingerprint_sha256':hashlib.sha256(json.dumps(arm_fp,sort_keys=True).encode()).hexdigest(),
            'enabled_rules':normal.EXPERIMENTS[arm],'contract_version':normal.VERSION,
            'output_hashes':{p.relative_to(d).as_posix():digest(p) for p in d.rglob('*') if p.is_file()},
            'api_call_count':0,'gold_used_in_normalization':False})
    # Integrated order is fixed; verify independent orders produce the same proposals.
    for nid in ids:
        original=norm_responses[('N0',nid)]
        if list(llm.INTERMEDIATE_VALIDATOR.iter_errors(original)):continue
        for condition in original['conditions']:
            a=copy.deepcopy(condition);b=copy.deepcopy(condition)
            for arm in ['N1','N2','N3','N4']:a=normal.normalize(a,arm,inputs[nid]['raw_text'])[0]
            for arm in ['N4','N3','N2','N1']:b=normal.normalize(b,arm,inputs[nid]['raw_text'])[0]
            if a!=b or a!=normal.normalize(condition,'N5',inputs[nid]['raw_text'])[0]:safety['normalization_order_conflicts']+=1
    # Only now read DEVELOPMENT gold for strict scoring, never for normalization.
    gold=[r for r in p12.pilot.read_jsonl(p12.pilot.GOLD/'reviewed_condition_gold.jsonl') if r['notice_id'] in ids]
    assert len(gold)==10 and sum(len(r.get('gold_conditions',[]))+len(r.get('missed_condition_candidates',[])) for r in gold)==62
    evaluations={arm:p12.pilot.evaluate_conditions(gold,preds) for arm,preds in all_preds.items()}
    assert evaluations['N0'][0]==saved['evaluation']['llm_post_validation']
    assert all_preds['N4']==all_preds['N0']
    exact={};partial={};fplist={};metrics=[]
    for arm,preds in all_preds.items():
        exact[arm]=set();partial[arm]=set();fplist[arm]=set()
        for row in gold:
            gs=row.get('gold_conditions',[])+row.get('missed_condition_candidates',[])
            match=p12.evaluator.match_notice(gs,[r for r in preds if r['notice_id']==row['notice_id']])
            for pair in match['pairs']:
                if pair['status']=='EXACT_MATCH':exact[arm].add(pair['gold_id'])
                else:partial[arm].add(pair['gold_id'])
            fplist[arm].update(match['unmatched_predictions'])
        summary,notice_details,failures=evaluations[arm]
        write(out/arm/'evaluation.json',{'summary':summary,'notices':notice_details,'failures':failures})
        counts=Counter(r['final_status'] for r in all_details[arm])
        for scope,scoped in [('OVERALL',summary['micro'])]+[(f'SOURCE:{k}',v) for k,v in summary['by_source'].items()]+[(f'TYPE:{k}',v) for k,v in summary['by_condition_type'].items()]:
            metrics.append({'experiment':arm,'scope':scope,**{k:scoped.get(k) for k in ['tp','fp','fn','precision','recall','f1','macro_f1','partial_match_count','zero_prediction_notices']},
                'accepted_candidates':counts['ACCEPTED_UNREVIEWED'],'held_candidates':counts['HELD_FOR_REVIEW'],
                'rejected_candidates':counts['REJECTED'],'schema_rejected_proposals':counts['SCHEMA_REJECTED'],
                'changed_proposals':sum(r['experiment']==arm for r in change_logs)})
    delta={}
    old_valid={(r['notice_id'],r['proposal_index']) for r in all_details['N0'] if r['final_status']=='ACCEPTED_UNREVIEWED'}
    for arm in all_preds:
        now_valid={(r['notice_id'],r['proposal_index']) for r in all_details[arm] if r['final_status']=='ACCEPTED_UNREVIEWED'}
        # Candidate IDs change with normalized values/units. Report that separately from FP counts.
        delta[arm]={'existing_tp_preserved':exact['N0'].issubset(exact[arm]),
            'new_exact_gold_ids':sorted(exact[arm]-exact['N0']),'lost_exact_gold_ids':sorted(exact['N0']-exact[arm]),
            'resolved_fn_count':len(exact[arm]-exact['N0']),
            'fp_count_delta':len(fplist[arm])-len(fplist['N0']),
            'old_fp_ids_absent':sorted(fplist['N0']-fplist[arm]),'new_fp_ids':sorted(fplist[arm]-fplist['N0']),
            'partial_to_exact_gold_ids':sorted(partial['N0'] & exact[arm]),
            'remaining_partial_gold_ids':sorted(partial[arm]),
            'recovered_proposals':sorted(now_valid-old_valid),'lost_valid_proposals':sorted(old_valid-now_valid),
            'fp_id_churn_warning':'ID removal/addition may represent same proposal after unit/value normalization; not necessarily resolved/new semantic FP'}
    rows(out/'normalization_change_log.jsonl',change_logs);rows(out/'normalization_rejections.jsonl',reject_logs)
    rows(out/'condition_predictions.jsonl',[{'experiment':arm,'candidate':c} for arm,preds in all_preds.items() for c in preds])
    csv_write(out/'experiment_metrics.csv',metrics)
    assert not any(safety.values()),safety
    assert all(digest(ROOT/path)==value for path,value in protected_hash.items())
    write(out/'regression_report.json',{'status':'PASS','checks':safety,'deltas':delta,
        'baseline_reproduced':True,'N4_status':'NO_CHANGE','source_hashes_preserved':True,
        'api_call_count':0,'logic_adapter_modified':False})
    write(out/'normalization_experiment_manifest.json',{'experiment_id':out.name,'fingerprint':fp,
        'baseline':saved['evaluation']['llm_post_validation'],'request_ledger_used':13,'request_ledger_limit':13,
        'api_call_count':0,'contract_promoted_to_production':False,
        'outputs':{p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()}})
    return {'status':'COMPLETE','metrics':[r for r in metrics if r['scope']=='OVERALL'],'safety':safety}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,default=DEFAULT)
    args=ap.parse_args();print(json.dumps(run(args.output_dir),ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
