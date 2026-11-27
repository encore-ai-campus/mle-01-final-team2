# 차기 실험 제안 — 승인 전 실행 불가

기존 장부 13/13·잔여0을 그대로 둔다. 이 문서는 요청 제안이며 새 예산의 할당·승인·예약을 의미하지 않는다. 현재 실행 모듈은 MockTransport 전용이다.

| 실험 | 정책 | 전송 | 제안 요청 |
|---|---|---|---:|
| P0 | 기존 P12/N1 및 논리 기준선 재사용 | 신규 호출 없음 | 0 |
| P1 | 표준 속성·값/불확실성 의미 계약 + 공통 새 wire | JSON mode | 10 |
| P2 | P1과 같은 prompt/wire, schema 강제 방식 비교 | Structured Outputs | 10 |
| P3 | P1 + 원자 분해·최소 근거·중첩/예외 지시 | JSON mode | 10 |
| P4 | P3과 같은 prompt + 구조화 출력 | Structured Outputs | 10 |

P1/P2는 같은 의미 prompt, P3/P4는 같은 통합 prompt다. 출력 schema는 네 arm에서 동일하다. JSON mode arm은 schema를 system 메시지에 덧붙이고 Structured arm은 response_format으로 전달하므로 실제 토큰 수·제약 방식이 다르다. P0→P1에는 신규 wire/미해결 큐 도입이 함께 포함돼 속성 설명만의 순수한 ablation이 아니다. P1↔P2 및 P3↔P4는 전송 제약 차이, P1↔P3 및 P2↔P4는 논리/분해 지시 차이를 비교하는 2×2 구성이다.

## 최소 권장 구성

첫 실험은 P4만 10공고로 제안한다. 서로 다른 출처의 선행2건을 먼저 검사하고 나머지8건을 진행하는 staged gate를 둔다. schema·근거·참조·자원 정리 실패 시 즉시 차단하며 자동 재시도나 신규 예비 요청은 두지 않는다. 전체10건 평가에는 명시적 실패·빈 예측을 포함하는 기존 기준을 유지해야 한다. 실제로 실행하거나 선택 공고 ID를 확정하지 않았다.

P4만 실행하면 개별 요인의 인과 효과는 분리할 수 없다. 전체 정책의 유효성을 먼저 확인하고 필요 시 같은 승인 절차로 P1/P2/P3을 추가한다. 요인 효과가 처음부터 필요하면 40요청의 2×2 설계를 별도로 승인받아야 한다. 전체 arm의 실행은 의무가 아니다.

모델·low reasoning·8192 completion cap·180초·SDK retry0을 유지하는 계획이다. 표준 단위는 prompt에서 요청하고 N1은 실험 브리지의 별도 flag로만 적용한다. 비교 시 raw와 N1 결과를 구분하고 운영 자동 반영은 하지 않는다. 신규 output/adapter fingerprint로 기존 P12 및 N1 평가 결과를 보존한다.

## 비용 계획

[공식 모델 요금](https://developers.openai.com/api/docs/models/gpt-5.6-luna)을 2026-11-27 확인했다. uncached input $0.20/1M, output $1.20/1M을 사용하고 cache/batch 할인은 가정하지 않았다. 실제 계정 접근은 확인하지 않았다.

tiktoken이 없어 토큰은 측정값이 아니다. UTF-8 bytes를 2–6bytes/token으로 근사하고 공고 본문을 요청당1,000tokens로 가정했다. 출력은 reasoning을 포함한 3,000tokens 시나리오와 cap8,192 시나리오를 비교했다. 서버 프레이밍·실제 본문/토큰화·사용량에 따라 달라지므로 비용 보장 상한이 아니다.

| 구성 | 제안 호출 수 | 예시 비용 범위(USD) |
|---|---:|---:|
| P0 재사용 | 0 | 0 |
| P1 | 10 | 약0.0453–0.1221 |
| P2 | 10 | 약0.0453–0.1221 |
| P3 | 10 | 약0.0458–0.1237 |
| P4 권장 | 10 | 약0.0458–0.1237 |
| P1–P4 전체 | 40 | 약0.1821–0.4916 |

실제 계산식·토큰 가정은 request_budget_and_cost_estimate.json에 기록했다. output cap은 유지하지만 입력을 포함한 엄밀한 지출 상한을 계산한 것은 아니다. 승인 전에는 기존 장부를 변경하거나 별도 활성 예산을 생성하지 않는다.

## 검증과 다음 단계

새 합성 테스트30개, 기존 평가·정규화·논리·추출을 포함한 회귀163개가 통과했다. Mock 응답이 기존 condition intermediate/v1.1 검증 및 평가 adapter로 연결됨을 확인했다. 실제 LLM의 개선 성능·새 F1·AST 정확도를 산출하지 않았다.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_condition_llm_next_policy -q
```

실제 요청 명령은 제공하지 않는다. 승인된 새 예산·실행기·Provider schema 수락 검사·추적 장부 설계가 선행돼야 한다. 운영 추출기 기본 동작, 기존 카탈로그, strict 평가 기준, 골든셋과 독립 평가20건은 변경/사용하지 않았다.
