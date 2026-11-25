"""Rule-first condition candidate extraction on the 2-1 DEVELOPMENT split only."""
from __future__ import annotations
import argparse, base64, hashlib, json, re, time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'data/condition_inputs/v1/20261125/extraction_inputs.jsonl'
SAMPLES=ROOT/'data/condition_inputs/v1/20261125/representative_samples.jsonl'
OUT=ROOT/'data/condition_inputs/v1/20261125/extracted/improved'
NUM=r'(\d[\d,]*(?:\.\d+)?)'
PATTERNS=[
 ('EXCLUSION','제외',re.compile(r'제외|불가|참여제한|지원\s*제외')),
 ('PREFERENCE','우대',re.compile(r'가점|우대|우선\s*선정')),
 ('BUSINESS_AGE','BUSINESS_AGE',re.compile(rf'(?:창업|업력)[^\n,;。]{{0,18}}?{NUM}\s*년\s*(이내|이하|미만|초과|이상)')),
 ('REPRESENTATIVE_AGE','REPRESENTATIVE_AGE',re.compile(rf'대표자[^\n,;。]{{0,18}}?{NUM}\s*세\s*(이내|이하|미만|초과|이상)')),
 ('REVENUE_FINANCIAL','REVENUE_FINANCIAL',re.compile(rf'(매출액|매출)[^\n,;。]{{0,16}}?{NUM}\s*(억원|만원|원)\s*(이상|이하|초과|미만|이내)')),
 ('EMPLOYMENT','EMPLOYMENT',re.compile(rf'(?:고용인원|근로자|종업원)[^\n,;。]{{0,16}}?{NUM}\s*명\s*(이상|이하|초과|미만|이내)')),
 ('BUSINESS_TYPE','BUSINESS_TYPE',re.compile(r'중소기업|소상공인|창업기업|예비창업자|개인사업자|법인사업자')),
 ('BUSINESS_LOCATION','BUSINESS_LOCATION',re.compile(r'전국|서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도|서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주')),
]
OP={'이상':'GTE','이하':'LTE','초과':'GT','미만':'LT','이내':'LTE'}
def read(path):
 with Path(path).open(encoding='utf-8') as f:
  for l in f:
   if l.strip(): yield json.loads(l)
def spans(text):
 # Split at hard paragraph/list boundaries only; preserve offsets and connective context.
 for m in re.finditer(r'[^\n]+',text):
  line=m.group()
  for s in re.finditer(r'[^。！？!?]+[。！？!?]?',line):
   a=m.start()+s.start(); b=m.start()+s.end(); raw=text[a:b]
   if raw.strip(): yield a,b,raw
def make_id(nid,a,b,raw,cat):
 v='|'.join((nid,str(a),str(b),cat,raw)); return 'CND:'+base64.b32encode(hashlib.sha256(v.encode()).digest()[:15]).decode('ascii').rstrip('=')
def condition(nid,src,kind,cat,field,op,value,vt,unit,raw,evidence,confidence=None):
 cid=make_id(nid,evidence['start'],evidence['end'],raw,cat)
 return {'schema_version':'1.0','condition_id':cid,'notice_id':nid,'condition_type':kind,'category_id':cat,'field':field,'operator':op,'value':value,'value_type':vt,'unit':unit,'reference_date':{'value':None,'date_type':'UNKNOWN','precision':'UNKNOWN','basis':None,'source_field':None},'raw_text':raw,'source':{'source_system':src['source_system'],'source_kind':'NOTICE_FIELD','source_field':'condition_texts.eligibility.text','normalized_path':'condition_texts.eligibility.text','evidence_id':f'{nid}:eligibility-source','chunk_ids':src.get('chunk_ids',[]),'location':{'start_char':evidence['start'],'end_char':evidence['end']},'observed_value_status':'AVAILABLE','evidence_text':raw},'availability_status':'AVAILABLE','completeness_status':'UNKNOWN','review_status':'NEEDS_REVIEW' if kind=='UNCLASSIFIED' else 'UNREVIEWED','confidence':confidence,'search_eligible':bool(src.get('chunk_ids')),'search_reason':'SOURCE_CHUNK_AVAILABLE' if src.get('chunk_ids') else 'SOURCE_FIELD_ONLY','decision_eligible':False,'logic_relation_status':'UNRESOLVED','qualifiers':[],'benefit':None}
def extract_one(row):
 text=row['raw_text']; found=[]
 for a,b,raw in spans(text):
  s=raw.strip(); offset=raw.find(s); a+=offset; b=a+len(s)
  matches=[]
  for cat,field,rx in PATTERNS:
   for m in rx.finditer(s): matches.append((m.start(),m.end(),cat,field,m))
  # Prefer explicit exclusion/preference markers; otherwise preserve ambiguous cross-patterns separately.
  for x,y,cat,field,m in matches:
   typ=cat if cat in {'EXCLUSION','PREFERENCE'} else 'ELIGIBILITY'
   op=value=vt=unit=None; conf=.72
   if cat in {'EXCLUSION','PREFERENCE'}:
    cat='UNCLASSIFIED'; field=None; conf=None
   elif field in {'BUSINESS_AGE','REPRESENTATIVE_AGE','REVENUE_FINANCIAL','EMPLOYMENT'}:
    if field in {'BUSINESS_AGE','REPRESENTATIVE_AGE'}: raw_amount,quant=m.group(1),m.group(2); unit='YEAR'
    elif field=='REVENUE_FINANCIAL': raw_amount,quant=m.group(2),m.group(4); unit=m.group(3)
    else: raw_amount,quant=m.group(1),m.group(2); unit='PERSON'
    op=OP.get(quant); value=float(raw_amount.replace(',','')); vt='NUMBER'
   elif field=='BUSINESS_LOCATION': op='EQ'; value=m.group(); vt='STRING'
   elif field=='BUSINESS_TYPE': op='EQ'; value=m.group(); vt='STRING'
   else: typ='UNCLASSIFIED'; field='UNCLASSIFIED'; cat='UNCLASSIFIED'; conf=None
   ev={'start':a+x,'end':a+y}
   found.append(condition(row['notice_id'],row,typ,cat,field if field!='UNCLASSIFIED' else None,op,value,vt or 'UNKNOWN',unit,s[ x:y ],{**ev,'chunk_ids':next((e['chunk_ids'] for e in row['evidence']),[])},conf))
 # Exact semantic dupes collapse only within this input; keep all evidence references.
 unique={}
 for c in found:
  key=(c['condition_type'],c['category_id'],c['field'],c['operator'],json.dumps(c['value'],sort_keys=True),c['raw_text'])
  unique.setdefault(key,c)
 return list(unique.values())
class LLMProvider:
 def extract(self, text: str, *, model: str, prompt_version: str) -> dict[str,Any]:
  return {'status':'NOT_CONFIGURED','model':model,'prompt_version':prompt_version,'conditions':[],'error':'No approved LLM client configured'}
def run(input_path=INPUT,sample_path=SAMPLES,out=OUT):
 start=time.perf_counter(); byid={r['notice_id']:r for r in read(input_path)}
 dev=[s for s in read(sample_path) if s['split']=='DEVELOPMENT']
 legacy={}
 for c in read(ROOT/'data/condition_inputs/v1/20261125/candidate_refs.jsonl'):
  legacy.setdefault((c['notice_id'],c['evidence_text']),[]).append(c)
 rows=[]; review=[]; seen=set(); provenance=[]
 for s in dev:
  r=byid[s['notice_id']]; cs=extract_one(r)
  for c in cs:
   if c['condition_id'] in seen: raise ValueError('duplicate generated condition_id')
   seen.add(c['condition_id']); rows.append(c)
   attr={'BUSINESS_AGE':'business_age','REPRESENTATIVE_AGE':'founder_age','BUSINESS_LOCATION':'region','BUSINESS_TYPE':'company_size','EXCLUSION':'exclusion','PREFERENCE':'preference'}.get(c['field'] or c['condition_type'])
   ev=c['source']['evidence_text']; prov=sorted({x['candidate_ref'] for (lnid,lev),refs in legacy.items() if lnid==s['notice_id'] and (ev in lev or lev in ev) for x in refs if attr is None or x.get('attribute')==attr})
   provenance.append({'condition_id':c['condition_id'],'notice_id':s['notice_id'],'legacy_candidate_refs':prov,'reuse_status':'REUSED_MATCHED_EVIDENCE' if prov else 'NEW_RULE_CANDIDATE','review_status':'UNREVIEWED','decision_eligible':False})
  if not cs: review.append({'notice_id':s['notice_id'],'status':'NO_RULE_MATCH','review_status':'NEEDS_REVIEW','decision_eligible':False})
 out=Path(out); out.mkdir(parents=True,exist_ok=True)
 (out/'development_conditions.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in rows),encoding='utf-8')
 (out/'candidate_provenance.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in provenance),encoding='utf-8')
 (out/'review_queue.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in review),encoding='utf-8')
 report={'input_development_notices':len(dev),'processed':len(dev),'failed':0,'condition_candidates':len(rows),'review_queue':len(review),'by_source':{},'by_type':{},'by_category':{},'extraction_mode':'RULE_BASED','llm_status':'INTERFACE_ONLY_NOT_CONFIGURED','evaluation_records_used':False,'elapsed_seconds':round(time.perf_counter()-start,3),'decision_eligible_count':sum(c['decision_eligible'] for c in rows)}
 for c in rows:
  report['by_source'][c['source']['source_system']]=report['by_source'].get(c['source']['source_system'],0)+1; report['by_type'][c['condition_type']]=report['by_type'].get(c['condition_type'],0)+1; report['by_category'][c['category_id']]=report['by_category'].get(c['category_id'],0)+1
 (out/'run_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return rows,review,report
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--output-dir',type=Path,default=OUT); a=p.parse_args(); print(json.dumps(run(out=a.output_dir)[2],ensure_ascii=False,indent=2))
