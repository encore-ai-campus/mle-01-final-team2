# R2 선행 공고 연결 오류 단일 재시도 준비

기존 R2 실행의 합성 사전 확인은 성공했고 선행 공고는 `APIConnectionError`로 실패했다. 원래 `lead/` 기록과 manifest fingerprint를 그대로 보존한다. `retry_code_change.json`은 수정 전후 실행기·추출기 해시, 기존 요청 장부 해시, 변경 범위와 이 작업을 요청한 승인 기록을 별도로 담는다. 현재 장부는 2/12이며, 이 문서 작성 중 API 호출은 없었다.

## 오프라인 확인

프로젝트 루트의 PowerShell에서 실행한다.

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --check
& '.\.venv\Scripts\python.exe' -c "from tools import run_condition_llm_openai_pilot_r2 as r; from tools import extract_condition_candidates_llm as l; ids=r.prior.read_json(r.prior.PREPARATION / 'pilot_notice_ids.json'); fp=r.fingerprint(ids,l.load_env_safely().get('OPENAI_CHAT_MODEL','')); m=r.assert_same_run(r.OUT / 'manifest.json',fp); print('RETRY_PREPARED',m['status'],m['requests_used'])"
```

첫 명령은 고정 데이터와 파일 읽기 가능 여부를 확인한다. 두 번째 명령은 기존 fingerprint와 별도 변경 이력의 전후 코드 해시를 대조한다. 정상 출력은 `RETRY_PREPARED LEAD_BLOCKED 2`이다. 둘 다 API를 호출하지 않는다.

## 명시적 단일 재시도

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --retry-lead
```

이 명령은 기존 합성 요청을 다시 보내지 않는다. 요청 3번을 호출 전에 기존 `request_ledger.json`에 기록하고 고정 선행 공고 1건만 호출한다. 결과는 별도 `lead_retry/` 및 `lead_retry_gate.json`에 저장한다. 원래 `lead/` 및 `lead_gate.json`은 보존한다. 연결 오류 외 실패, 설정·입력 변경, 기존 성공 응답, 이미 사용된 재시도, 장부 이상 또는 잔여 10회 미만이면 호출 전에 차단한다. 실패 시 `LEAD_BLOCKED`를 유지하고 다시 호출하지 않는다.

## 결과 확인 및 후속 실행

```powershell
& '.\.venv\Scripts\python.exe' -c "import json; from pathlib import Path; p=Path('data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2'); print(json.dumps({name:json.loads((p/name).read_text(encoding='utf-8')) for name in ['lead_retry_gate.json','request_ledger.json']},ensure_ascii=False,indent=2))"
```

`lead_retry_gate.json`이 `PASS`인 경우에만 이어서 실행한다. 재시도 성공 후 남은 예산은 9회이며, 이는 미처리 공고 9건에만 배정된다. 추가 예비 요청은 없다.

```powershell
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --continue
& '.\.venv\Scripts\python.exe' tools/run_condition_llm_openai_pilot_r2.py --evaluate
```

평가는 재시도에 성공한 `lead_retry/`의 예측을 사용한다. 기존 실패 시도는 요청 통계와 오류 기록에만 남으며 동일 공고를 두 번 평가하지 않는다. 모델, 프롬프트, 생성 설정, 골든셋 및 기존 평가 정책은 유지한다.
