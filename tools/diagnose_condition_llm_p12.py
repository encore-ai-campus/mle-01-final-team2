"""Read-only strict-score reproduction and auditable DEVELOPMENT-only alignment diagnosis.

Diagnostic correspondences below are human-reviewed analysis annotations, never
extraction rules or corrected predictions. No normalized predictions are scored.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import run_condition_llm_p12 as p

OUT=p.base.DEV/'llm_pilot_2_5c3d1_diagnosis'
V=p.evaluator
J=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True)

def csv_write(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:J(v) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()} for row in rows)

# Gold row order -> raw proposal index; these are diagnosis-only correspondences.
ALIGN=[[1,2,3,4,0],[0,1,2,3,4,5,6,7,8,9,None],[0,1,2,4,3,5],
       [1,0,2,2,2,2],[1,3,2,0,4,4,4],[0,1,2,3],[0,1,2,3,4,5],
       [0,2,3],[0,2,2,1,3,4,6,7,8,9],[1,0,2,3]]
CAUSE=[['VALUE_NORMALIZATION_MISMATCH']*4+['SEMANTIC_AMBIGUITY'],
 ['VALUE_NORMALIZATION_MISMATCH']+['ATTRIBUTE_MAPPING_MISMATCH']*9+['CONDITION_GRANULARITY_MISMATCH'],
 ['VALUE_NORMALIZATION_MISMATCH','ATTRIBUTE_MAPPING_MISMATCH','EVIDENCE_SPAN_MISMATCH','EVIDENCE_SPAN_MISMATCH','UNSUPPORTED_ATTRIBUTE','UNSUPPORTED_ATTRIBUTE'],
 ['UNSUPPORTED_ATTRIBUTE']*2+['CONDITION_GRANULARITY_MISMATCH']*4,
 ['ATTRIBUTE_MAPPING_MISMATCH','VALUE_NORMALIZATION_MISMATCH','EVIDENCE_SPAN_MISMATCH','ATTRIBUTE_MAPPING_MISMATCH']+['CONDITION_GRANULARITY_MISMATCH']*3,
 ['VALUE_NORMALIZATION_MISMATCH','VALUE_NORMALIZATION_MISMATCH','ATTRIBUTE_MAPPING_MISMATCH',None],
 ['UNSUPPORTED_ATTRIBUTE','ATTRIBUTE_MAPPING_MISMATCH','EVIDENCE_SPAN_MISMATCH','UNSUPPORTED_ATTRIBUTE','UNSUPPORTED_ATTRIBUTE','UNSUPPORTED_ATTRIBUTE'],
 ['VALUE_NORMALIZATION_MISMATCH','UNSUPPORTED_ATTRIBUTE','OTHER_OR_UNRESOLVED'],
 ['SCHEMA_REJECTION']*10,
 ['ATTRIBUTE_MAPPING_MISMATCH','EVIDENCE_SPAN_MISMATCH','CONDITION_TYPE_MISMATCH','EVIDENCE_SPAN_MISMATCH']]

def main():
    if OUT.exists():raise FileExistsError('Refusing to overwrite diagnosis')
    OUT.mkdir()
    protected=[x for x in p.OUT.rglob('*') if x.is_file()]
    protected += [p.pilot.GOLD/'reviewed_condition_gold.jsonl',p.pilot.GOLD/'reviewed_logic_gold.jsonl',
        Path(V.__file__),Path(p.llm.__file__),Path(p.pilot.__file__),p.pilot.BASELINE_OUT,p.pilot.RULE_E,
        p.pilot.BASELINE_LOGIC,p.pilot.RULE_E_LOGIC,p.llm.INPUTS]
    before={x:p.base.digest(x) for x in protected}
    saved=p.base.read_json(p.OUT/'evaluation_summary.json');ids=saved['notice_ids']
    gold=[r for r in p.pilot.read_jsonl(p.pilot.GOLD/'reviewed_condition_gold.jsonl') if r['notice_id'] in ids]
    logicgold=[r for r in p.pilot.read_jsonl(p.pilot.GOLD/'reviewed_logic_gold.jsonl') if r['notice_id'] in ids]
    by_gold={r['notice_id']:r for r in gold}
    post=[];intermediate=[];raws={};details={};post_by={};logicpred=[];logic_audit=[]
    for i,nid in enumerate(ids):
        d=p.OUT/('lead_replay_v2' if i==0 else f'notice_{i:02d}')
        rawfile=p.base.PARENT_RAW if i==0 else d/'raw_llm_responses.jsonl'
        obj=json.loads(p.llm._read_jsonl(rawfile)[0]['response_attempts'][-1]);raws[nid]=obj
        intermediate.append({'notice_id':nid,'intermediate_response':obj})
        rd=d if i==0 else d/'attribute_replay_v2'
        preds=[r['candidate'] for r in p.llm._read_jsonl(rd/'predictions_after_validation.jsonl')] if rd.exists() else []
        post.extend(preds);post_by[nid]=preds
        details[nid]=p.llm._read_jsonl(rd/'validation_details.jsonl') if rd.exists() else []
        if i==0:
            source=next(r for r in p.llm._read_jsonl(p.llm.INPUTS) if r['notice_id']==nid)
            sets=[p.llm._response_to_artifacts(source,obj)['notice_set']]
        else:sets=p.llm._read_jsonl(d/'notice_condition_sets.jsonl')
        logicpred.extend(s for s in sets if s)
        if rd.exists():
            proposal=p.llm._read_jsonl(rd/'logic_proposals.jsonl')[0]
            logic_audit.append({'notice_id':nid,'raw_group_count':len(obj['logic_sections']),
                'proposal_group_count':len(proposal['logic_sections']),
                'raw_exception_count':len(obj['exceptions']),'exception_objects_preserved':obj['exceptions']==proposal['exceptions'],
                'raw_unresolved_relations_preserved':obj['unresolved_relations']==proposal['unresolved_relations'],
                'unresolved_indexes':proposal['unresolved_condition_indexes'],
                'completeness':proposal['logical_completeness']})
    pre=p.pilot.prevalidation_predictions(intermediate,p.llm.INPUTS)
    named={'baseline_v1':[r for r in p.pilot.read_jsonl(p.pilot.BASELINE_OUT) if r['notice_id'] in ids],
           'rule_experiment_E':[r for r in p.pilot.read_jsonl(p.pilot.RULE_E) if r['notice_id'] in ids],
           'llm_pre_validation':pre,'llm_post_validation':post}
    evaluated={k:p.pilot.evaluate_conditions(gold,v) for k,v in named.items()}
    for name,(summary,_,_) in evaluated.items():
        assert summary==saved['evaluation'][name],name
    logic=V.evaluate_records(gold,logicgold,post,logicpred)
    assert logic==p.base.read_json(p.OUT/'strict_logic_and_condition_report.json')
    partial=[];fn=[];fp=[];audit=[];comparison=[]
    matched_ids={name:set() for name in named}
    pair_by_gold={};pair_by_pred={}
    for i,nid in enumerate(ids):
        gs=by_gold[nid]['gold_conditions']+by_gold[nid].get('missed_condition_candidates',[])
        matches={name:V.match_notice(gs,[r for r in rows if r['notice_id']==nid]) for name,rows in named.items()}
        for name,match in matches.items():
            matched_ids[name].update(q['gold_id'] for q in match['pairs'] if q['status']=='EXACT_MATCH')
        for pair in matches['llm_post_validation']['pairs']:
            pair_by_gold[pair['gold_id']]=pair;pair_by_pred[pair['prediction_id']]=pair
            if pair['status']=='PARTIAL_MATCH':
                g,pr=pair['gold'],pair['prediction'];diff=pair['differences']
                reason='EVIDENCE_SPAN_MISMATCH' if diff==['evidence'] else 'VALUE_NORMALIZATION_MISMATCH'
                equivalent=('SAME_CORE_PREDICATE_CONTEXT_REVIEW_REQUIRED' if g['field'] in ['APPLICANT_ADDRESS','BUSINESS_LOCATION'] and 'value' in diff else
                            'SAME_CORE_PREDICATE' if g['field'] not in ['DOCUMENT_SUBMISSION'] else 'SCOPE_AND_GRANULARITY_REVIEW_REQUIRED')
                partial.append({'notice_id':nid,'gold_id':pair['gold_id'],'prediction_id':pair['prediction_id'],
                    'gold_text':g['raw_text'],'prediction_evidence':pr['raw_text'],
                    'gold_field':g['field'],'prediction_field':pr['field'],'gold_value':g['value'],'prediction_value':pr['value'],
                    'gold_operator':g['operator'],'prediction_operator':pr['operator'],
                    'gold_unit':g['unit'],'prediction_unit':pr['unit'],
                    'gold_evidence':V.evidence(g,gold=True),'prediction_evidence_location':V.evidence(pr,gold=False),
                    'exact_match_blockers':diff,'primary_reason':reason,'semantic_equivalence':equivalent,
                    'granularity_difference':'MULTIPLE_REQUIREMENTS_IN_DOCUMENT_VALUE' if g['field']=='DOCUMENT_SUBMISSION' else 'SAME_PREDICATE_BROADER_QUOTE' if 'evidence' in diff else 'NONE',
                    'offline_improvement':'PARTIAL_ONLY; SPAN_POLICY_STILL_BLOCKS' if 'evidence' in diff and len(diff)>1 else
                        'POSSIBLE_UNIT_MAPPING' if diff==['unit'] else 'EVIDENCE_SELECTION_REVIEW; NO_AUTOMATIC_SPAN_TRIMMING',
                    'count_as_tp':False})
        raw=raws[nid]['conditions'];ds={r['proposal_index']:r for r in details[nid]}
        for j,g in enumerate(gs):
            gid=V._identity(g);ri=ALIGN[i][j];proposal=raw[ri] if ri is not None else None
            detail=ds.get(ri,{})
            pair=pair_by_gold.get(gid);pred=pair['prediction'] if pair else None
            if pred is None and detail.get('candidate_id'):
                pred=next((r for r in post_by[nid] if r['condition_id']==detail['candidate_id']),None)
            differences=V.common_differences(g,pred) if pred else []
            if pred and not V.evidence_exact(g,pred):differences.append('evidence')
            exact=gid in matched_ids['llm_post_validation']
            row={'notice_id':nid,'source_system':nid.split(':')[0],'gold_id':gid,'gold_type':g['condition_type'],
                 'gold_text':g['raw_text'],'gold_field':g['field'],'gold_value':g['value'],'gold_operator':g['operator'],
                 'raw_proposal_index':ri,'raw_proposal':proposal,'raw_validation_status':detail.get('final_status','SCHEMA_REJECTED' if i==8 else 'NO_CANDIDATE'),
                 'raw_validation_reason':detail.get('reason'),'related_prediction_id':pred.get('condition_id') if pred else None,
                 'gold_record':g,'prediction_record':pred,'exact_match':exact,
                 'alignment_basis':'MANUAL_DIAGNOSTIC_CORRESPONDENCE; NOT EXTRACTION_CORRECTION',
                 'alignment_confidence':'REVIEW_REQUIRED' if (i,j) in [(1,10),(7,2)] else 'SUPPORTED_BY_TEXT_AND_PREDICATE'}
            if proposal is not None:
                raw_adapted=p.pilot.prevalidation_predictions([{'notice_id':nid,
                    'intermediate_response':{'conditions':[proposal]}}],p.llm.INPUTS)[0]
                row['raw_adapter_differences']=V.common_differences(g,raw_adapted)
                if not V.evidence_exact(g,raw_adapted):row['raw_adapter_differences'].append('evidence')
                row['raw_evidence_location']=V.evidence(raw_adapted,gold=False)
            audit.append(row)
            if not exact:
                primary=CAUSE[i][j]
                secondary=list(differences)+row.get('raw_adapter_differences',[])
                if detail.get('reason'):secondary.append(detail['reason'])
                if proposal and proposal['field'].upper()!=str(g['field']):secondary.append('ATTRIBUTE_MAPPING_MISMATCH')
                if ri is not None and ALIGN[i].count(ri)>1:secondary.append('CONDITION_GRANULARITY_MISMATCH')
                fn.append({**row,'primary_reason':primary,'secondary_reasons':sorted(set(secondary)),
                    'offline_scope':'NO; INVALID_RESPONSE_RETAINED' if primary=='SCHEMA_REJECTION' else
                        'HUMAN_REVIEW' if primary in ['SEMANTIC_AMBIGUITY','OTHER_OR_UNRESOLVED'] else
                        'POTENTIAL_NORMALIZATION_OR_REPLAY; NOT_MEASURED'})
            rv=gid in matched_ids['baseline_v1'];re=gid in matched_ids['rule_experiment_E'];lm=exact
            comparison.append({'notice_id':nid,'gold_id':gid,'gold_text':g['raw_text'],
                'rule_v1_exact':rv,'rule_e_exact':re,'llm_exact':lm,
                'bucket':'BOTH' if (rv or re) and lm else 'RULE_ONLY' if rv or re else 'LLM_ONLY' if lm else 'NEITHER',
                'llm_failure_reason':None if lm else CAUSE[i][j],'llm_raw_proposal_index':ri})
        for pr in post_by[nid]:
            pid=pr['condition_id'];pair=pair_by_pred.get(pid)
            if pair and pair['status']=='EXACT_MATCH':continue
            related=next((x for x in audit if x['notice_id']==nid and x['related_prediction_id']==pid),None)
            if related:
                corresponding=next(x for x in fn if x['gold_id']==related['gold_id'])
                reason=corresponding['primary_reason']
                gid=related['gold_id']
            else:reason='OTHER_OR_UNRESOLVED';gid=None
            fp.append({'notice_id':nid,'prediction_id':pid,'condition_type':pr['condition_type'],'field':pr['field'],
                'operator':pr['operator'],'value':pr['value'],'unit':pr['unit'],'evidence':pr['raw_text'],
                'evidence_location':V.evidence(pr,gold=False),'related_gold_id':gid,'primary_reason':reason,
                'classification':'SUPPORTED_BY_SOURCE_BUT_NOT_STRICT_EXACT',
                'hallucination_confirmed':False,'prediction_record':pr,
                'review_note':'Attribute semantics require catalog review' if reason=='ATTRIBUTE_MAPPING_MISMATCH' else
                    'Exact blocker is recorded; no automatic semantic TP promotion'})
    assert len(partial)==16 and len(fn)==61 and len(fp)==31 and len(audit)==62
    csv_write('condition_alignment_audit.csv',audit);csv_write('partial_match_analysis.csv',partial)
    csv_write('false_negative_analysis.csv',fn);csv_write('false_positive_analysis.csv',fp)
    csv_write('rule_llm_comparison.csv',comparison)
    summary={'evaluation_reproduced':True,'gold_count':62,'raw_proposals':len(pre),'post_predictions':len(post),
        'metrics':{k:v[0] for k,v in evaluated.items()},'fn_primary_counts':dict(Counter(r['primary_reason'] for r in fn)),
        'fp_primary_counts':dict(Counter(r['primary_reason'] for r in fp)),
        'partial_primary_counts':dict(Counter(r['primary_reason'] for r in partial)),
        'partial_blocker_combinations':dict(Counter('|'.join(r['exact_match_blockers']) for r in partial)),
        'partial_blocker_incidence':dict(Counter(x for r in partial for x in r['exact_match_blockers'])),
        'rule_llm_buckets':dict(Counter(r['bucket'] for r in comparison)),
        'fn_by_source':{s:dict(Counter(r['primary_reason'] for r in fn if r['source_system']==s)) for s in ['BIZINFO','KSTARTUP']},
        'fn_by_type':{t:dict(Counter(r['primary_reason'] for r in fn if r['gold_type']==t)) for t in ['ELIGIBILITY','EXCLUSION','PREFERENCE']},
        'ledger':{'used':p.base.read_json(p.OUT/'request_ledger.json')['used'],'limit':13,'remaining':0},
        'api_calls_during_diagnosis':0,'logic_preservation':logic_audit,
        'logic_measured_totals':{k:{metric:sum(d['logic'][k].get(metric,0) for d in logic['notices']) for metric in metrics}
            for k,metrics in {'logical_relation':['tp','fp','fn'],'logical_group_exact':['correct','predicted','gold'],
                'exceptions':['tp','fp','fn'],'preference_benefit_links':['tp','fp','fn']}.items()},
        'ast_notice_exact_count':sum(d['logic']['notice_structure_exact'] for d in logic['notices']),
        'interpretation_warning':'Manual FN/FP correspondences are diagnostic, not proven universal aliases; partial matching is not semantic equivalence.'}
    p.base.write_json_atomic(OUT/'diagnosis_summary.json',summary)
    p.base.write_json_atomic(OUT/'logic_reproduction.json',logic)
    assert before=={x:p.base.digest(x) for x in protected}
    p.base.write_json_atomic(OUT/'manifest.json',{'diagnosis_id':OUT.name,'split':'DEVELOPMENT','api_call_count':0,
        'source_hashes':{x.relative_to(ROOT).as_posix():v for x,v in before.items()},
        'diagnostic_script_sha256':p.base.digest(Path(__file__)),
        'outputs':{x.name:p.base.digest(x) for x in OUT.iterdir() if x.is_file()},
        'source_bytes_preserved':True,'gold_used_for_diagnosis_only':True,'extraction_correction_performed':False})
    print(J(summary))

if __name__=='__main__':main()
