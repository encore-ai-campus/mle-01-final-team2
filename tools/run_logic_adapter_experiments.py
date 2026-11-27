"""L0/L1/L2 evaluation-only experiments; no API and no source artifact updates."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import run_condition_llm_p12 as p
from tools import condition_logic_evaluation_adapter as adapter
from tools import run_condition_normalization_experiments as norm
from tools.evaluate_condition_pipeline import _groups_and_edges

DEFAULT=p.base.DEV/'logic_adapter_2_5c3d3_v1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):p.base.write_json_atomic(path,value)
def rows(path,records):p.llm._write_jsonl(path,records)
def csv_write(path,records):
    fields=list(dict.fromkeys(key for r in records for key in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in records)
def proposed_counts(sections):
    groups=links=0
    def walk(group):
        nonlocal groups,links
        if isinstance(group,dict):
            if group.get('operator') in adapter.LOGICAL_OPERATORS:
                groups+=1
                links+=len(group.get('children',group.get('condition_indexes',[])))
            for key in ['children','groups']:
                for child in group.get(key,[]):walk(child)
    for section in sections:walk(section)
    return {'groups':groups,'membership_links':links}

def signature_leaves(signature):
    if signature[0]=='REF':return {signature[1]}
    return set().union(*(signature_leaves(child) for child in signature[1])) if signature[1] else set()

def group_failure_rows(label,nid,gold_roots,pred_roots,id_map):
    gold_groups,_,_=_groups_and_edges(gold_roots,{})
    pred_groups,_,_=_groups_and_edges(pred_roots,id_map)
    aligned=set(id_map.values())
    unmatched=gold_groups-pred_groups
    rows=[]
    for signature,count in unmatched.items():
        leaves=signature_leaves(signature)
        same_leaves=[s for s in pred_groups if signature_leaves(s)==leaves]
        if leaves-aligned:reason='CONDITION_NODE_MISSING_OR_NONALIGNED'
        elif same_leaves and all(s[0]!=signature[0] for s in same_leaves):reason='AND_OR_OR_UNRESOLVED_OPERATOR_DIFFERENCE'
        elif same_leaves:reason='NESTED_STRUCTURE_OR_GROUP_RELATION_DIFFERENCE'
        elif not pred_groups:reason='LOGIC_GROUP_MISSING'
        else:reason='GROUP_GRANULARITY_OR_MEMBERSHIP_DIFFERENCE'
        rows.append({'experiment':label,'notice_id':nid,'record_kind':'GOLD_GROUP_FAILURE',
            'gold_group_signature':signature,'group_occurrences':count,'primary_reason':reason,
            'unaligned_gold_condition_ids':sorted(leaves-aligned),
            'same_leaf_set_predicted_group_count':len(same_leaves),
            'diagnostic_note':'Condition map is existing evaluator exact+partial map; group signatures are existing canonical signatures.'})
    return rows

def load_llm(kind,ids):
    preds=[];records={};proposals={};raw={};notices={}
    for i,nid in enumerate(ids):
        original_dir=p.OUT/('lead_replay_v2' if i==0 else f'notice_{i:02d}')
        rawfile=p.base.PARENT_RAW if i==0 else original_dir/'raw_llm_responses.jsonl'
        raw[nid]=json.loads(p.llm._read_jsonl(rawfile)[0]['response_attempts'][-1])
        if kind=='P12':
            d=original_dir;rd=d if i==0 else d/'attribute_replay_v2'
        else:
            d=norm.DEFAULT/'N1'/f'notice_{i:02d}';rd=d/'replay'
        if not rd.exists():records[nid]={};proposals[nid]={};notices[nid]=[];continue
        after=p.llm._read_jsonl(rd/'predictions_after_validation.jsonl')
        cs=[r['candidate'] for r in after];preds.extend(cs);notices[nid]=cs
        proposals[nid]=p.llm._read_jsonl(rd/'logic_proposals.jsonl')[0]
        if kind=='P12' and i==0:
            source=next(r for r in p.llm._read_jsonl(p.llm.INPUTS) if r['notice_id']==nid)
            record=p.llm._response_to_artifacts(source,raw[nid])['notice_set']
            records[nid]=record or {}
        else:
            sets=p.llm._read_jsonl(d/'notice_condition_sets.jsonl');records[nid]=sets[0] if sets else {}
    return preds,records,proposals,raw,notices

def summarize(label,evaluated,counts,condition_metrics):
    ds=evaluated['notices']
    group=Counter();edge=Counter()
    for d in ds:
        g=d['logic']['logical_group_exact'];e=d['logic']['logical_relation']
        group.update({'tp':g['correct'],'fp':g['predicted']-g['correct'],'fn':g['gold']-g['correct']})
        edge.update({k:e[k] for k in ['tp','fp','fn']})
    gs=p.evaluator.prf(group['tp'],group['fp'],group['fn']);es=p.evaluator.prf(edge['tp'],edge['fp'],edge['fn'])
    return {'experiment':label,**{'group_'+k:gs[k] for k in ['tp','fp','fn','precision','recall','f1']},
        **{'edge_'+k:es[k] for k in ['tp','fp','fn','precision','recall','f1']},
        'group_exact':f"{group['tp']}/{group['tp']+group['fn']}",
        'notice_ast_exact':sum(d['logic']['notice_structure_exact'] for d in ds),'notice_count':len(ds),
        'evaluable_groups':sum(c['evaluation_counts']['groups'] for c in counts),
        'evaluable_edges':sum(c['evaluation_counts']['edges'] for c in counts),
        'unexecutable_proposal_groups':sum(len(c.get('unexecutable_groups',[])) for c in counts),
        'unsupported_semantic_objects':sum(len(c.get('exceptions',[]))+len(c.get('unresolved_relations',[])) for c in counts),
        'reference_integrity_errors':sum(len(c.get('errors',[])) for c in counts),
        'condition_tp':condition_metrics['micro']['tp'],'condition_fp':condition_metrics['micro']['fp'],
        'condition_fn':condition_metrics['micro']['fn'],'condition_f1':condition_metrics['micro']['f1']}

def run(out):
    if out.exists():raise FileExistsError('Refusing to overwrite logic experiment')
    out.mkdir(parents=True)
    ids=p.base.read_json(p.OUT/'manifest.json')['fingerprint']['pilot_notice_ids']
    paths=[x for directory in [p.OUT,norm.DEFAULT] for x in directory.rglob('*') if x.is_file()]
    paths += [Path(p.evaluator.__file__),ROOT/'tools/evaluate_condition_pipeline.py',Path(p.llm.__file__),
        p.pilot.INPUTS,p.pilot.SAMPLES,p.base.PARENT_RAW,p.pilot.GOLD/'reviewed_condition_gold.jsonl',
        p.pilot.GOLD/'reviewed_logic_gold.jsonl',p.pilot.GOLD/'manifest.json',
        p.pilot.BASELINE_OUT,p.pilot.BASELINE_LOGIC,p.pilot.RULE_E,p.pilot.RULE_E_LOGIC]
    protected={path.relative_to(ROOT).as_posix():sha(path) for path in paths}
    gold=[r for r in p.pilot.read_jsonl(p.pilot.GOLD/'reviewed_condition_gold.jsonl') if r['notice_id'] in ids]
    lg=[r for r in p.pilot.read_jsonl(p.pilot.GOLD/'reviewed_logic_gold.jsonl') if r['notice_id'] in ids]
    assert len(gold)==10 and sum(len(r['gold_conditions'])+len(r.get('missed_condition_candidates',[])) for r in gold)==62
    gold_by={r['notice_id']:r for r in gold}
    p12=load_llm('P12',ids);n1=load_llm('N1',ids)
    runs=[('L0',p12,False),('L1',p12,True),('L2',n1,True)]
    for label,cp,lp in [('RULE_V1',p.pilot.BASELINE_OUT,p.pilot.BASELINE_LOGIC),('RULE_E',p.pilot.RULE_E,p.pilot.RULE_E_LOGIC)]:
        preds=[r for r in p.pilot.read_jsonl(cp) if r['notice_id'] in ids]
        recs={r['notice_id']:r for r in p.pilot.read_jsonl(lp) if r['notice_id'] in ids}
        notices={nid:[r for r in preds if r['notice_id']==nid] for nid in ids}
        runs.append((label,(preds,recs,{}, {},notices),True))
    summary=[];audits=[];failures=[];unsupported={};results={};pipeline=[]
    for label,data,improved in runs:
        preds,recs,proposals,raw,notices=data
        evaluated_records=[];arm_audits=[]
        for nid in ids:
            source=recs.get(nid,{})
            proposal=proposals.get(nid,{})
            if improved:
                output,audit=adapter.adapt(source,notices[nid],proposal)
                if audit['errors']:
                    raise RuntimeError('ADAPTER_REFERENCE_ERROR:'+label+':'+nid+':'+json.dumps(audit['errors']))
            else:
                output=source
                audit={'adapter_version':'P12_EXISTING','errors':[],
                    'evaluation_counts':adapter.tree_counts(p.evaluator._roots(source)),
                    'exceptions':[{} for _ in proposal.get('exceptions',[])],
                    'unresolved_relations':[{} for _ in proposal.get('unresolved_relations',[])],
                    'unexecutable_groups':[]}
            if output:evaluated_records.append(output)
            audit={'experiment':label,'notice_id':nid,**audit}
            audit['raw_logic_diagnostic']={
                'logic_sections':raw.get(nid,{}).get('logic_sections',[]),
                'exceptions':raw.get(nid,{}).get('exceptions',[]),
                'unresolved_relations':raw.get(nid,{}).get('unresolved_relations',[]),
                'available':nid in raw,'validated_proposal_available':bool(proposal),
                'note':'Raw schema-invalid response is diagnostic only; never converted to executable groups.'}
            arm_audits.append(audit);audits.append(audit)
            raw_counts=proposed_counts(raw.get(nid,{}).get('logic_sections',[]))
            source_groups=adapter.tree_counts([s['root'] for s in source.get('logic_sections',[])])
            fallback_groups=adapter.tree_counts(p.evaluator._roots(source))
            pg,pe,_=_groups_and_edges(p.evaluator._roots(output),{})
            pipeline.append({'experiment':label,'notice_id':nid,
                'original_proposal_groups':raw_counts['groups'],'original_proposal_membership_links':raw_counts['membership_links'],
                'postvalidation_section_groups':source_groups['groups'],
                'postvalidation_section_edges':source_groups['edges'],
                'postvalidation_proposal_sections':len(proposal.get('logic_sections',[])),
                'legacy_collection_groups':fallback_groups['groups'],
                'adapter_evaluation_root_groups':audit['evaluation_counts']['groups'],
                'adapter_evaluation_root_edges':audit['evaluation_counts']['edges'],
                'evaluator_recognized_groups':sum(pg.values()),'evaluator_recognized_edges':sum(pe.values()),
                'raw_counts_available':nid in raw})
        evaluated=p.evaluator.evaluate_records(gold,lg,preds,evaluated_records)
        assert evaluated==p.evaluator.evaluate_records(gold,lg,preds,evaluated_records)
        condition_metrics=p.pilot.evaluate_conditions(gold,preds)[0]
        if label=='L0':assert evaluated==p.base.read_json(p.OUT/'strict_logic_and_condition_report.json')
        if label in ['L0','L1']:assert condition_metrics==p.base.read_json(p.OUT/'evaluation_summary.json')['evaluation']['llm_post_validation']
        if label=='L2':assert condition_metrics==p.base.read_json(norm.DEFAULT/'N1/evaluation.json')['summary']
        results[label]=evaluated
        write(out/(label+'_evaluation.json'),evaluated)
        rows(out/(label+'_adapter_records.jsonl'),evaluated_records)
        summary.append(summarize(label,evaluated,arm_audits,condition_metrics))
        unsupported[label]={'semantic_scores':'NOT_MEASURED_NO_NEW_SEMANTIC_CRITERION',
            'preserved_exceptions':sum(len(audit['exceptions']) for audit in arm_audits),
            'preserved_unresolved_relations':sum(len(audit['unresolved_relations']) for audit in arm_audits),
            'unexecutable_proposal_groups':sum(len(audit['unexecutable_groups']) for audit in arm_audits),
            'completeness_records_preserved':sum(bool(proposals.get(nid)) for nid in ids),
            'phase_annotated_sections_preserved':sum(len(recs.get(nid,{}).get('logic_sections',[])) for nid in ids),
            'unsupported_object_count_scope':'Metric CSV counts exception + unresolved-relation objects only; completeness and phase metadata overlap and are listed separately.',
            'items':['Exception effects','Exception scope correctness','Unresolved relation meaning',
                'Logical completeness correctness','Phase-dependent logical change'],
            'legacy_exception_diagnostics':'Existing evaluator values retained in detailed evaluation but not treated as new semantic measurements',
            'rule_comparison_limit':'v1 trees support structural comparison; v1.1 effect/phase/proposal provenance missing for rules' if label.startswith('RULE') else None}
        for detail in evaluated['notices']:
            nid=detail['notice_id'];row=gold_by[nid]
            gs=row['gold_conditions']+row.get('missed_condition_candidates',[])
            matched=p.evaluator.match_notice(gs,notices[nid])
            exact=sum(pair['status']=='EXACT_MATCH' for pair in matched['pairs'])
            partial=matched['partial_count']
            logical=detail['logic'];a=next(a for a in arm_audits if a['notice_id']==nid)
            # Multi-label diagnostics, not a causal allocation of edge FN.
            reasons=[]
            if not notices[nid]:reasons.append('CONDITION_EXTRACTION_FAILED_OR_ZERO_CANDIDATES')
            elif matched['unmatched_gold']:reasons.append('CONDITION_STRICT_MISMATCH_OR_MISSING')
            if not a['evaluation_counts']['groups']:reasons.append('NO_EXECUTABLE_GROUP')
            if not logical['nested_structure_exact']['exact']:reasons.append('NESTED_STRUCTURE_DIFFERENCE')
            if a.get('unresolved_condition_indexes'):reasons.append('UNRESOLVED_CONDITION_REFERENCES')
            if not logical['notice_structure_exact']:reasons.append('AST_STRUCTURE_OR_NODE_ALIGNMENT_DIFFERENCE')
            if a.get('exceptions') or a.get('unresolved_relations'):reasons.append('SEMANTIC_EXTENSION_NOT_MEASURED')
            failures.append({'experiment':label,'notice_id':nid,'record_kind':'NOTICE_DIAGNOSTIC','strict_exact_conditions':exact,
                'partial_condition_pairs':partial,'missing_or_nonexact_gold_count':len(matched['unmatched_gold']),
                'evaluation_id_map_includes_partial':True,
                'group_score':logical['logical_group_exact'],'edge_score':logical['logical_relation'],
                'ast_exact':logical['notice_structure_exact'],'diagnostic_reasons':reasons,
                'causality_note':'Group and edge signatures include descendant identities; missing/nonaligned conditions can invalidate every edge in a group. Do not attribute every miss to AND/OR.'})
            gold_logic=next(r for r in lg if r['notice_id']==nid)
            pred_logic=next((r for r in evaluated_records if r['notice_id']==nid),{})
            failures.extend(group_failure_rows(label,nid,gold_logic['gold_logic_roots'],
                p.evaluator._roots(pred_logic),matched['id_map']))
    csv_write(out/'logic_metrics_comparison.csv',summary);csv_write(out/'logic_transport_counts.csv',pipeline)
    csv_write(out/'logic_failure_analysis.csv',failures);rows(out/'logic_reference_audit.jsonl',audits)
    write(out/'unsupported_logic_report.json',unsupported)
    assert all(sha(ROOT/name)==value for name,value in protected.items())
    assert results['L1']['common']==results['L0']['common']
    write(out/'regression_report.json',{'status':'PASS','L0_reproduced':True,'P12_condition_metrics_preserved':True,
        'N1_condition_metrics_preserved':True,'repeat_evaluation_identical':True,'source_hashes_preserved':True,
        'reference_integrity_errors':sum(len(a['errors']) for a in audits),'api_calls':0,
        'logic_generation_modified':False,'strict_evaluator_modified':False,
        'alignment_note':'Existing match_notice maps exact and partial condition pairs; adapter does not alter that policy.'})
    write(out/'logic_adapter_experiment_manifest.json',{'adapter_version':adapter.VERSION,
        'adapter_sha256':sha(adapter.__file__),'runner_sha256':sha(__file__),
        'preserved_sources':protected,'api_call_count':0,'ledger_used':13,'ledger_limit':13,
        'experiments':{label:{'source':'P12' if label in ['L0','L1'] else 'N1' if label=='L2' else label,
            'adapter':'P12_EXISTING' if label=='L0' else adapter.VERSION} for label,_,_ in runs},
        'outputs':{x.relative_to(out).as_posix():sha(x) for x in out.rglob('*') if x.is_file()}})
    return summary

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,default=DEFAULT)
    args=ap.parse_args();print(json.dumps(run(args.output_dir),ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
