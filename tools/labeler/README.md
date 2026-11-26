# 수기 정규화 도우미 (labeler)

파일럿 10건의 라벨 A(요건·조건)와 라벨 B(프로필별 판정)를 JSON을 직접 고치지 않고 브라우저에서 쓰는 단일 HTML 도구다.

- 열기: `tools/labeler/labeler.html`을 Chrome/Edge로 연다. 인터넷이 필요 없고, 입력한 내용은 컴퓨터 밖으로 나가지 않는다.
- 사용 순서와 규칙: [docs/PILOT_수기정규화_작업안내_v0.1.md](../../docs/PILOT_수기정규화_작업안내_v0.1.md) §4-1
- 점검 규칙은 `tools/goldset_check.py`의 `validate_a`·`validate_b`와 같다(`python -m unittest tools.test_labeler_core`가 같은 입력에 같은 오류가 나오는지 비교한다. Node 필요, 없으면 건너뜀).
- 수정은 `labeler.template.html`에서 하고 `python tools/make_labeler.py`로 `labeler.html`을 다시 만든다(공통 프로필 8종이 안에 들어간다).
- 자동 저장은 브라우저(localStorage) 안에만 남는다. ②·③ 탭의 [이 공고 라벨 A/B 저장(JSON)]으로 공고마다 백업하고, 파일로 저장하지 않은 변경이 15분 넘거나 공고를 바꾸면 알림이 뜬다(창을 닫을 때도 묻는다).
- 공고 원문(패킷)은 첨부 추출 텍스트라 저장소에 올리지 않는다. 이 도구도 원문을 서버로 보내지 않도록 네트워크 호출이 없다.
