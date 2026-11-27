# 속성·값·논리 계약 연결

## 의미 계약

schemas/conditions/contracts/draft-v1/attribute_semantic_contract_v1.json의 기존22 항목을 읽어 prompt에 canonical_field, 한국어 의미, entity_scope, 허용 operator/value_type/unit, 합성 사용 예와 혼동 반례를 삽입한다. 전체 계약을 운영 승인한 것은 아니며 신규 속성 후보는 conditions enum에 없다. UNCLASSIFIED는 기존 목록에 존재하지만 표준 후보 생성용으로 허용하지 않고 미해결 큐 사용을 요구한다.

EXACT_ALIAS는 기존 normalize_condition_attribute 경로를 재사용한다. provider는 대문자 표준 출력을 요구하며 category 일치는 내부 schema의 if/then으로 검증한다. 신청 주체/사업체, 개인 주소/사업장, 대표자/팀원, 자격 사실/증빙 제출, 등록 사건/등록 상태의 전역 치환은 없다. 문맥 기반 매핑을 모델이 제안해도 표준화 근거가 불충분하면 큐에 넣어야 한다. 검증기는 모델의 모든 의미 분류를 완전하게 판정하는 것이 아니므로 사람 검수가 필요하다.

## Provider와 내부 schema

provider_output_schema.json은 required 전체·additionalProperties=false·enum·typed anyOf·$defs를 사용한다. 값은 scalar/array/명시적 range로 제한하고 자유 OBJECT는 이 실험에서 제외한다. nullable 필드는 null union으로 표현한다. 표준 조건 operator는 기존 허용 enum만, 미해결 항목 operator는 null이다.

internal_output_schema.json은 같은 wire에 date format, nonempty evidence, range shape, value_type 연동, field/category 일치 등 내부 제약을 추가한다. 기존 intermediate enum이나 v1.1 조건 schema는 변경하지 않았다. 내부 검증 후 기존 INTERMEDIATE_VALIDATOR와 _response_to_artifacts, 최종 condition-v1.1 검증을 재사용한다.

실험 경로의 N1은 source quote가 확인된 같은 차원의 단위만 변환한다. 이 옵션을 끄면 비표준 단위는 내부 검증에서 거절된다. 의미가 확정되지 않은 금액·범주·지역·필드 치환은 추가하지 않았다. 숫자/값이 형식상 맞아도 원문의 의미가 참임을 보장하지 않으며 schema adherence와 추출 품질을 구분한다.

## 조건 분해 및 유형

원자 술어를 조건으로 생성하되 AND/OR·양화·예외·시점의 범위를 잃지 않도록 지시한다. ELIGIBILITY/EXCLUSION/PREFERENCE를 독립 확인하고 우대를 필수조건으로 만들지 않는다. 선정 이후 의무는 condition의 phase/temporal/requirement_kind 및 section의 명시적 phase에 보존한다. 조건의 부재·NOT_STATED·불명확·미지원·명시적 무제한·검수 필요를 같은 UNKNOWN으로 합치지 않는다.

최소 충분 근거는 주체·부정·기준값·시점·분기 범위가 남는 원문 구절이다. 첫 evidence quote를 primary로 유지하고 필요하면 supporting quotes를 추가한다. offset은 모델이 쓰지 않고 기존 Python 검증이 계산한다. gold span을 참조하지 않는다. 실제 모델이 적절한 최소 구절을 선택하는 성능은 측정하지 않았다.

## 그래프 및 미해결 계약

logic_groups는 group_id/operator/children, logic_sections는 최상위 root_ref와 phase를 갖는다. children은 CONDITION_REF(condition_index), GROUP_REF(group_id), UNRESOLVED_REF(unresolved_index) 중 하나다. 그래프의 정의와 참조는 분리돼 임의 depth의 명시적 중첩을 표현하고 cycle/orphan/중복·없는 참조를 내부에서 차단한다. 표준 condition 인덱스와 미해결 discovery 인덱스는 별도 namespace라 혼동하지 않는다.

기존 조건 검증기에 투영하는 projection은 표준 조건 검증용이며 logic_sections/exceptions/relations를 빈 목록으로 둔다. **그 과정에서 기존 builder가 만드는 fallback AST는 출력하지 않는다.** 실제 그래프는 새 응답이 명시한 refs만 사용해 구성한다. 유효한 전체 그룹은 기존 평가 adapter에 전달할 수 있는 AST가 되고, 미검증/미해결 자식이 하나라도 있는 그룹은 원본 그래프·held_refs·INCOMPLETE와 함께 보류한다. 자식을 조용히 제거해 완전한 그룹으로 만들지 않는다.

이는 기존 P10의 원본 인덱스·미해결·예외 적용 차단 원칙을 유지하면서 새로운 그래프에 적용하는 보수적 실험 정책이다. 일부 자식만 남은 실행 그룹을 만들지 않으므로 기존 P10의 부분 AST와 출력 모양은 다를 수 있다. 기존 산출물을 소급 변경하지 않는다.

예외에는 원본 target_refs, 유형·범위·전제·replacement를 보존하고 application_allowed=false로 둔다. 미해결 대상은 BLOCKED_UNRESOLVED_TARGET으로 기록한다. unresolved_relations는 원래 member refs와 reason/evidence를 보존한다. 유효 후보로 만들지 못한 조건 인덱스, 미지원 발견, 실행용 AST에서 제외된 refs가 별도 출력에 남는다.

표준 조건이 없고 미지원 발견만 있는 경우에도 발견 큐와 source_state를 보존한다. 조건을 확인한 것과 검증된 표준 후보를 생성한 것을 구분하며 자동 자격 판정은 항상 false다. 그래프의 원문상 의미를 검증하는 새 평가 기준은 만들지 않았다.
