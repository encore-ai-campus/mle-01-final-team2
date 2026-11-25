"""Diagnose baseline on DEVELOPMENT records only and build a human review packet."""
import csv,json,re
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'data/condition_inputs/v1/20261125/extracted/baseline'
INPUT=ROOT/'data/condition_inputs/v1/20261125/extraction_inputs.jsonl'; SAMPLES=ROOT/'data/condition_inputs/v1/20261125/representative_samples.jsonl'
OUT=ROOT/'data/condition_inputs/v1/20261125/quality_diagnostics'
def read(p):
 with Path(p).open(encoding='utf-8') as f:
  for l in f:
   if l.strip(): yield json.loads(l)
def run():
 dev={s['notice_id'] for s in read(SAMPLES) if s['split']=='DEVELOPMENT'}
 inputs={r['notice_id']:r for r in read(INPUT) if r['notice_id'] in dev}
 cond=defaultdict(list)
 for c in read(BASE/'development_conditions.jsonl'): cond[c['notice_id']].append(c)
 improved=defaultdict(list)
 for c in read(BASE.parent/'improved'/'development_conditions.jsonl'): improved[c['notice_id']].append(c)
 prov=list(read(BASE/'candidate_provenance.jsonl')); bycond={p['condition_id']:p for p in prov}
 review={r['notice_id']:r for r in read(BASE/'review_queue.jsonl')}
 cands=defaultdict(list)
 for r in read(ROOT/'data/condition_inputs/v1/20261125/candidate_refs.jsonl'):
  if r['notice_id'] in dev:cands[r['notice_id']].append(r)
 bins=Counter(); src=defaultdict(list); unused=Counter(); missing=[]; unmatched=Counter(); legacy_dupes=defaultdict(list)
 for nid,row in inputs.items():
  n=len(cond[nid]); bins['ZERO' if n==0 else 'ONE' if n==1 else 'TWO_PLUS']+=1
  src[row['source_system']].append(n)
  used={x for c in cond[nid] for x in bycond.get(c['condition_id'],{}).get('legacy_candidate_refs',[])}
  unused['connected']+=len(cands[nid]); unused['matched']+=len(used); unused['unmatched']+=len(cands[nid])-len(used)
  for x in cands[nid]:
   legacy_dupes[x['legacy_candidate_ref']].append(x)
   if x['candidate_ref'] not in used:
    a=x.get('attribute'); unmatched['UNSUPPORTED_CATEGORY' if a in {'certification','law_reference','employment'} else 'EVIDENCE_OR_SPAN_MISMATCH']+=1
  if n==0: missing.append({'notice_id':nid,'reason':'NO_RULE_MATCH_NOT_ABSENCE','candidate_count':len(cands[nid]),'text_length':len(row['raw_text'])})
 # Select 30 development notices deterministically, with failure and complexity strata.
 selected=[]
 def take(pool,n):
  for nid in sorted(pool):
   if nid not in selected and len(selected)<30:selected.append(nid)
   if sum(1 for x in selected if x in pool)>=n:break
 take([x for x in inputs if x in review],10)
 take([x for x in inputs if any(c['condition_type'] in {'EXCLUSION','PREFERENCE'} for c in cond[x])],5)
 take([x for x in inputs if len(cands[x])>=8],5)
 take([x for x in inputs if re.search(r'단,|다만|예외|또는|혹은|이내|이상|미만',inputs[x]['raw_text'])],10)
 for x in sorted(inputs):
  if len(selected)>=30:break
  if x not in selected:selected.append(x)
 packet=[]
 for nid in selected:
  row=inputs[nid]; existing=cond[nid] or [None]
  for c in existing:
   packet.append({'notice_id':nid,'source_system':row['source_system'],'source_field':'condition_texts.eligibility.text','original_text':row['raw_text'],'baseline_condition_id':c['condition_id'] if c else None,'baseline_condition_type':c['condition_type'] if c else None,'baseline_category':c['category_id'] if c else None,'baseline_operator':c['operator'] if c else None,'baseline_value':c['value'] if c else None,'baseline_unit':c['unit'] if c else None,'baseline_reference_date':c['reference_date'] if c else None,'baseline_evidence_text':c['source']['evidence_text'] if c else None,'improved_conditions':improved.get(nid,[]),'legacy_candidate_refs':bycond.get(c['condition_id'],{}).get('legacy_candidate_refs',[]) if c else [],'extraction_method':'RULE_BASED' if c else 'NO_MATCH','suspected_omission':not bool(c),'error_type':'HUMAN_REVIEW_REQUIRED' if not c else 'UNREVIEWED','reviewer_correction':None,'review_status':'UNREVIEWED','review_comment':None})
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'human_review.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in packet),encoding='utf-8')
 llm=[{'notice_id':nid,'source_system':inputs[nid]['source_system'],'text':inputs[nid]['raw_text'],'reason':'NO_RULE_MATCH' if not improved.get(nid) else 'RULE_COVERAGE_REVIEW','llm_status':'NOT_CONFIGURED','review_status':'UNREVIEWED','decision_eligible':False} for nid in sorted(inputs) if not improved.get(nid)]
 (OUT/'llm_assistance_candidates.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in llm),encoding='utf-8')
 cols=list(packet[0]);
 with (OUT/'human_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(packet)
 report={'development_notices':len(inputs),'conditions_by_notice_bins':dict(bins),'source_candidates':{s:{'notices':len(v),'mean':round(sum(v)/len(v),2),'max':max(v)} for s,v in src.items()},'candidate_reuse':dict(unused),'unmatched_candidate_reason_counts':dict(unmatched),'candidate_legacy_duplicate_groups_in_development':sum(len(v)>1 for v in legacy_dupes.values()),'review_queue_notices':len(review),'review_sample_notices':len(selected),'review_rows':len(packet),'sample_notice_ids':selected,'no_match':missing,'condition_candidates':sum(map(len,cond.values())),'baseline':{'candidates':sum(map(len,cond.values())),'zero_match_notices':bins['ZERO']},'improved':{'candidates':sum(map(len,improved.values())),'zero_match_notices':sum(not improved.get(nid) for nid in inputs)},'precision_recall_f1':'NOT_COMPUTED_NO_GOLD_LABELS'}
 (OUT/'diagnostic_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return report
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
