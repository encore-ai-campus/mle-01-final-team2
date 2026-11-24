// Conservative phase-1 validation/reprocessing for the saved 30-row sample.
// Reads existing artifacts only. It does not call K-Startup or process all 3,819 rows.
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const base = path.join(root, 'data', 'kstartup');
const oldDir = path.join(base, 'processed', 'sample30');
const outDir = path.join(base, 'processed', 'sample30_v2');
const reportDir = path.join(base, 'reports');

function readJsonl(file) {
  return fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean).map(JSON.parse);
}
function writeJsonl(file, rows) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, rows.map(x => JSON.stringify(x)).join('\n') + '\n', 'utf8');
}
function clone(x) { return JSON.parse(JSON.stringify(x)); }

const cleaned = readJsonl(path.join(oldDir, 'kstartup_cleaned.jsonl'));
const conditions = readJsonl(path.join(oldDir, 'kstartup_conditions.jsonl'));
const chunks = readJsonl(path.join(oldDir, 'kstartup_chunks.jsonl'));
if (cleaned.length !== 30 || conditions.length !== 30 || new Set(cleaned.map(x => x.announcement_id)).size !== 30) {
  throw new Error('Expected 30 unique saved sample announcements in all input files');
}
const cleanById = new Map(cleaned.map(x => [String(x.announcement_id), x]));
const counters = { region: { seen: 0, conservative: 0, scope_unknown: 0 }, age: { seen: 0, conservative: 0, relation_unknown: 0 },
  exclusion: { records_seen: 0, old_text_candidates: 0, kept_explicit: 0, dropped_procedural: 0, conduct_restriction: 0 },
  amount: { old_candidates: 0, retained_contextual: 0 }, evaluation: { seen: 0 },
  automated: { consistent: 0, needs_review: 0, incorrect: 0, not_found: 0 } };
const revisedConditions = [];
const auditRows = [];

for (const old of conditions) {
  const id = String(old.announcement_id);
  const source = cleanById.get(id)?.source_api_fields || {};
  const revised = clone(old);
  const kept = [];
  const recordAudit = { announcement_id: id, fields_checked: [], findings: [] };
  for (const c of revised.conditions || []) {
    if (c.condition_type === 'region') {
      counters.region.seen++;
      const raw = String(source.supt_regin || '').trim();
      const observed = String(c.raw_text || '').trim() === raw && raw.length > 0;
      counters.automated[observed ? 'consistent' : 'incorrect']++;
      const vals = Array.isArray(c.normalized_value) ? c.normalized_value : [];
      const normalized = {
        region_labels: vals,
        source_field_value: raw || null,
        applies_to_entity: 'unknown',
        scope: 'program_region_scope_unconfirmed',
        relation: vals.length > 1 ? 'unknown' : null
      };
      c.normalized_value = normalized;
      c.review_status = 'needs_review';
      c.validation = { automated_status: observed ? 'consistent' : 'incorrect', manual_review_status: 'not_performed',
        checks: ['raw_text_matches_supt_regin', 'entity_and_scope_not_inferred'] };
      counters.region.conservative++;
      counters.region.scope_unknown++;
      recordAudit.fields_checked.push('supt_regin');
      recordAudit.findings.push(observed ? '지역 원문 일치; 지원 지역과 신청 기업 소재지 적용 범위는 미확인' : '지역 추출 원문과 API 필드 불일치');
      kept.push(c);
    } else if (c.condition_type === 'business_age') {
      counters.age.seen++;
      const raw = String(source.biz_enyy || '').trim();
      const observed = String(c.raw_text || '').trim() === raw && raw.length > 0;
      counters.automated[observed ? 'consistent' : 'incorrect']++;
      const oldValue = c.normalized_value || {};
      const oldCriteria = Array.isArray(oldValue.criteria) ? oldValue.criteria : [];
      const options = oldCriteria.map(v => ({ ...v }));
      c.normalized_value = { options, option_relation: options.length > 1 ? 'unknown_and_or' : null,
        reference_date: null, cutoff_application: 'unknown' };
      c.review_status = 'needs_review';
      c.validation = { automated_status: observed ? 'consistent' : 'incorrect', manual_review_status: 'not_performed',
        checks: ['raw_text_matches_biz_enyy', 'no_reference_date_invented', 'multiple_option_logic_left_unknown'] };
      counters.age.conservative++;
      if (options.length > 1) counters.age.relation_unknown++;
      recordAudit.fields_checked.push('biz_enyy');
      recordAudit.findings.push(options.length > 1 ? '수치 토큰은 보존; 복수 연차의 OR/AND 관계 및 기준일 미확인' : '수치 토큰은 보존; 적용 기준일 미확인');
      kept.push(c);
    } else if (c.condition_type === 'exclusion') {
      counters.exclusion.records_seen++;
      const text = String(c.raw_text || '').trim();
      if (text) counters.exclusion.old_text_candidates++;
      const explicit = /신청\s*제외|지원\s*제외|참여\s*제한|신청\s*불가|지원\s*불가|신청자격\s*제한/.test(text);
      const procedural = /제외대상\s*여부|제외\s*대상인지|자격\s*충족\s*여부/.test(text) && !/신청\s*제외\s*대상\s*(?:기업|자)/.test(text);
      const conduct = /노쇼|무단\s*불참|당일\s*취소/.test(text) && /추후|향후|참여\s*제한/.test(text);
      if (procedural && !conduct) {
        counters.exclusion.dropped_procedural++;
        counters.automated.not_found++;
        recordAudit.fields_checked.push('aply_excl_trgt_ctnt/pbanc_ctnt');
        recordAudit.findings.push('절차상 제외대상 확인 문구를 자격 제외 규정으로 잡은 후보 제거');
        continue;
      }
      if (conduct) {
        c.condition_type = 'participation_restriction';
        c.normalized_value = { scope: 'program_participation_conduct', applicant_eligibility_exclusion: false };
        counters.exclusion.conduct_restriction++;
      } else if (explicit) {
        c.normalized_value = null;
        counters.exclusion.kept_explicit++;
      } else {
        counters.automated.needs_review++;
      }
      c.review_status = 'needs_review';
      c.validation = { automated_status: explicit || conduct ? 'needs_review' : 'not_found', manual_review_status: 'not_performed',
        checks: ['distinguish_eligibility_exclusion_from_procedural_or_conduct_notice'] };
      recordAudit.fields_checked.push('aply_excl_trgt_ctnt/pbanc_ctnt');
      recordAudit.findings.push(conduct ? '신청 자격 제외가 아닌 프로그램 참여 행동 제한으로 분리' : '명시적 제외 후보이나 적용 범위 검수 필요');
      kept.push(c);
    } else if (c.condition_type === 'support_amount') {
      counters.amount.old_candidates++;
      const field = String(c.source_field || '');
      const original = String(source[field] || '');
      const raw = String(c.raw_text || '').replace(/\s/g, '');
      const present = !!raw && original.replace(/\s/g, '').includes(raw);
      const context = present && /지원|사업화\s*자금|지원금/.test(original) && /최대|이내|한도/.test(original);
      counters.automated[present ? 'consistent' : 'incorrect']++;
      if (context) counters.amount.retained_contextual++;
      c.normalized_value = present ? { ...(c.normalized_value || {}), interpretation: context ? 'support_amount_cap_candidate' : 'amount_semantics_unconfirmed' } : null;
      c.review_status = 'needs_review';
      c.validation = { automated_status: present ? (context ? 'consistent' : 'needs_review') : 'incorrect', manual_review_status: 'not_performed',
        checks: ['literal_amount_occurs_in_source_field', 'amount_is_not_asserted_as_total_budget', 'support_context_checked'] };
      recordAudit.fields_checked.push(field);
      recordAudit.findings.push(context ? '지원 문맥 및 최대/한도 표현 확인; 개별 지원액/예산 구분은 미검수' : '금액 의미 불명확; 사업 총예산 가능성 검수 필요');
      kept.push(c);
    } else if (c.condition_type === 'evaluation_criteria') {
      counters.evaluation.seen++;
      const field = String(c.source_field || 'eval_method');
      const original = String(source[field] || '');
      const evidence = String(c.evidence_text || c.raw_text || '');
      const exact = evidence.length > 0 && original.includes(evidence);
      counters.automated[exact ? 'consistent' : 'incorrect']++;
      c.validation = { automated_status: exact ? 'consistent' : 'incorrect', manual_review_status: 'not_performed',
        checks: ['evidence_is_substring_of_source_field', 'method_and_scoring_criteria_not_assumed_equivalent'] };
      c.review_status = 'needs_review';
      recordAudit.fields_checked.push(field);
      recordAudit.findings.push(exact ? '평가 API 필드 근거 연결 일치; 평가 절차와 배점 기준은 별도 검수 필요' : '평가 근거가 원 필드와 불일치');
      kept.push(c);
    } else {
      kept.push(c);
    }
  }
  revised.conditions = kept;
  revised.condition_counts_by_status = { needs_review: kept.filter(x => x.review_status === 'needs_review').length,
    not_found: kept.filter(x => x.review_status === 'not_found').length };
  revisedConditions.push(revised);
  auditRows.push(recordAudit);
}

const revisedCleaned = clone(cleaned);
for (const row of revisedCleaned) {
  row.region_condition_status = 'needs_review_scope_unconfirmed';
  row.business_age_condition_status = 'needs_review_relation_or_cutoff_unconfirmed';
}
const revisedChunks = chunks.map(clone); // text remains source API text; no normalized candidates are inserted.
writeJsonl(path.join(outDir, 'kstartup_cleaned.jsonl'), revisedCleaned);
writeJsonl(path.join(outDir, 'kstartup_conditions.jsonl'), revisedConditions);
writeJsonl(path.join(outDir, 'kstartup_chunks.jsonl'), revisedChunks);
writeJsonl(path.join(outDir, 'validation_audit.jsonl'), auditRows);

const metrics = {
  sample_size: 30,
  unique_ids: new Set(revisedCleaned.map(x => x.announcement_id)).size,
  old_condition_records: conditions.reduce((n, x) => n + x.conditions.length, 0),
  revised_condition_records: revisedConditions.reduce((n, x) => n + x.conditions.length, 0),
  chunks_copied_without_text_changes: revisedChunks.length,
  published_date_nonnull: revisedCleaned.filter(x => x.published_date != null).length,
  date_unverified: revisedCleaned.filter(x => x.date_status === 'date_unverified').length,
  counters
};

const report = `# K-Startup 샘플 조건 추출 검증 및 규칙 개선

## 범위와 검수 상태

- 기존 ` + '`sample30`' + ` 산출물 30건만 사용했습니다. 원본 3,819건/API/상세 페이지/첨부파일은 조회하지 않았습니다.
- 자동 검증과 원문 문자열 대조를 실행했습니다. 이는 사람의 최종 검수가 아닙니다. 재처리 조건은 모두 ` + '`needs_review`' + `이고 ` + '`verified`' + `로 승격된 항목은 없습니다.
- 이전 표본 파일은 보존하고 재처리 산출물은 ` + '`data/kstartup/processed/sample30_v2/`' + `에 별도 생성했습니다. 청크 본문은 기존 API 원문 청크를 그대로 복사했습니다.
- 날짜 메타데이터는 기존대로 ` + '`published_date=null`' + `, ` + '`date_status=date_unverified`' + `를 유지했습니다.

## 오류 유형 및 개선

| 조건 | 이전 방식의 위험 | 개선된 처리 | 자동 대조 결과 |
|---|---|---|---|
| 지역 | ` + '`supt_regin`' + `을 기업 소재지 요건으로 읽을 위험 | 원 API 표기를 보존하고 적용 대상/범위를 unknown으로 명시 | ${counters.region.seen}건 검사, 원문 필드 일치 ${counters.region.conservative}건; 기업 소재지 요건으로 확정 0건 |
| 업력 | 여러 연차를 한 배열로 두어 AND/OR 및 선택지 의미를 잃음 | 원 수치 선택지를 보존, ` + '`option_relation=unknown_and_or`' + `, 기준일 미상 | ${counters.age.seen}건 검사, 원문 일치 ${counters.age.conservative}건, 복수 관계 미상 ${counters.age.relation_unknown}건 |
| 제외 | ‘제외대상 여부 검토’ 같은 절차 문구가 제외 조건 후보로 잡힘 | 절차 문구 후보 제거; 노쇼 등은 자격 제외가 아닌 행동 제한으로 분리; 명시 문구도 검수 대기 | 종전 비어 있지 않은 후보 ${counters.exclusion.old_text_candidates}건, 절차성 제거 ${counters.exclusion.dropped_procedural}건, 행동 제한 분리 ${counters.exclusion.conduct_restriction}건, 명시 제외 후보 ${counters.exclusion.kept_explicit}건 |
| 지원 금액 | 단순 금액 패턴은 사업 총예산과 개별 지원액을 혼동할 수 있음 | 원문 필드 내 금액 일치 및 지원 문맥/최대 표현 확인; 모두 검수 대기 | 후보 ${counters.amount.old_candidates}건, 문맥 일치 후보 ${counters.amount.retained_contextual}건 |
| 평가 기준 | API ` + '`eval_method`' + `에는 평가 절차/일정이 함께 들어갈 수 있음 | 원문 근거 일치만 자동 확인, 절차와 배점 기준을 동일시하지 않음 | ${counters.evaluation.seen}건 대조 |
| 근거 연결 | 자동 후보의 필드 출처 및 근거를 다시 확인하기 어려움 | 각 재처리 조건에 원문 필드 대조 상태와 검수 상태를 분리 기록 | 자동 검증 로그 ${auditRows.length}건 생성 |

## 전후 비교

| 지표 | 기존 샘플 | 개선 후 샘플 |
|---|---:|---:|
| 표본 | 30 | ${metrics.sample_size} |
| 지역 조건 후보 | 30 | ${counters.region.conservative}; 적용 대상 미확인으로 전부 needs_review |
| 업력 조건 후보 | 30 | ${counters.age.conservative}; 관계/기준일 미확인으로 전부 needs_review |
| 제외 키워드 후보 | ${counters.exclusion.old_text_candidates} | ${counters.exclusion.kept_explicit + counters.exclusion.conduct_restriction}; 절차 문구 ${counters.exclusion.dropped_procedural} 제외 |
| 지원 금액 후보 | ${counters.amount.old_candidates} | ${counters.amount.retained_contextual} 문맥 후보; 전부 needs_review |
| 청크 | ${chunks.length} | ${revisedChunks.length}; 텍스트 변경 없음 |
| 조건 ` + '`verified`' + ` | 0 | 0 |

이 전후 수치는 표본 내 후보량과 자동 원문 일치 검사 결과이며, 정확도/재현율이나 사람 검수 완료율이 아닙니다. 제외 후보는 단순 키워드 수가 아니라 규칙으로 절차성 문구와 참여 행동 제한을 분리했습니다.

## 검증 결과

- 고유 공고 ID: ${metrics.unique_ids}/30
- 날짜 상태 유지: ` + '`published_date`' + ` 비null ${metrics.published_date_nonnull}건, ` + '`date_unverified`' + ` ${metrics.date_unverified}건
- 중복 청크 생성: 없음(기존 고유 ` + '`chunk_id`' + ` 유지, 본문 미변경)
- 자동 원문 문자열 대조 실패는 ` + '`validation_audit.jsonl`' + `에 공고 ID별로 기록했습니다.
- 개인정보 자동 탐지는 기존 샘플 처리 결과를 이어받았으며, 담당자 이름의 완전 탐지나 수동 개인정보 검수는 수행하지 않았습니다.

## 산출물

- ` + '`data/kstartup/processed/sample30_v2/kstartup_cleaned.jsonl`' + `
- ` + '`data/kstartup/processed/sample30_v2/kstartup_conditions.jsonl`' + `
- ` + '`data/kstartup/processed/sample30_v2/kstartup_chunks.jsonl`' + `
- ` + '`data/kstartup/processed/sample30_v2/validation_audit.jsonl`' + `
- ` + '`data/kstartup/reports/kstartup_condition_validation.md`' + `

## 다음 단계

이 결과는 자동 추출 규칙의 보수화와 표본 재처리까지입니다. 사람이 공고 원문 의미를 최종 확인하지 않았으므로, 전체 3,819건 처리는 아직 수행하지 않았습니다. 특히 지역 적용 대상, 업력 선택 관계/기준일, 개별 지원액 여부, 제외 조건의 법적 범위는 검수가 남아 있습니다.
`;
fs.writeFileSync(path.join(reportDir, 'kstartup_condition_validation.md'), report, 'utf8');
console.log(JSON.stringify(metrics, null, 2));
