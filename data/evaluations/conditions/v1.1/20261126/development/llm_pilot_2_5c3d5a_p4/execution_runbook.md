# P4 파일럿 실행 순서

아래 API 실행 명령은 별도 사용자 승인 후에만 사용합니다. 현재 신규 요청 장부는 비활성 상태입니다.

```powershell
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --preflight
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --offline-self-test
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --prepare
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --approve-budget --approval-token APPROVE_P4_10_REQUESTS --approval-reference '사용자 승인 날짜와 근거'
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --run-first --authorize-api
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --check-first
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --run-remaining --authorize-api
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --evaluate
```

첫 응답에서 기술 Gate가 PASS가 아니면 나머지 9건은 차단됩니다. `--run-first`와 `--run-remaining`은 실제 API를 호출합니다.
