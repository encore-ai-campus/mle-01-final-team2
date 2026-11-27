# kordoc 설치·사용 안내 v0.1

| 항목 | 내용 |
|---|---|
| 언제 필요한가 | 첨부 공고문(HWP·HWPX·배포용 HWP·스캔 PDF·이미지)을 **새로 추출할 때만** 필요하다. API 서버·웹·판정 시험에는 필요 없다 |
| 무엇인가 | 한국어 문서 파서 [kordoc](https://github.com/chrisryugj/kordoc)(MIT, Node 패키지). 표 구조와 OCR이 기존 추출기보다 낫다 |
| 근거 | [kordoc 첨부 추출 비교 시범](data/PILOT_kordoc_첨부추출_비교_v0.1.md). 기존 추출은 덮어쓰지 않고 새 스냅숏으로 병행한다(채택 범위는 팀 결정) |
| 버전 | `kordoc@4.25.24`로 고정한다. 올릴 때는 시범 표본 30건으로 다시 비교한다 |

## 1. 설치

Node 20 이상이 필요하다(`node -v`로 확인).

kordoc은 설치 용량이 커서(약 392 MB) **저장소 밖 폴더**에 설치한다. 저장소에는 넣지 않는다.

```powershell
mkdir $HOME\kordoc-work
cd $HOME\kordoc-work
npm init -y
npm install kordoc@4.25.24 --save-exact
npx kordoc --help
```

`npx kordoc`이 안 되면 `node node_modules/kordoc/dist/cli.js --help`로 직접 부른다.

## 2. 변환

```powershell
$env:KORDOC_OFFLINE = "1"   # 외부 다운로드를 막는다. OCR 모델은 3절로 미리 넣어 둔다
npx kordoc "<첨부 파일>" -o "<출력>.md"
```

- 출력은 Markdown이다. 병합 칸이 있는 표는 HTML `<table>`(`rowspan`)로 나온다.
- 출력 위치는 `data/bizinfo/extracted/<날짜>_kordoc/`처럼 **새 스냅숏 폴더**로 한다. 기존 스냅숏(`extracted/20261124_101546/`)은 정답 근거 위치가 가리키므로 덮어쓰지 않는다.
- 첨부 원본과 추출 글은 git에 올리지 않는다(`.gitignore`가 `data/bizinfo/files/`, `data/bizinfo/extracted/`를 막는다).

## 3. OCR 모델(스캔 PDF·이미지를 읽을 때만)

OCR은 PP-OCRv5 모델(약 19 MB)이 있어야 한다. 사용자 홈의 `.cache/kordoc/models/ppocr`에 들어간다.

| 방법 | 명령 |
|---|---|
| 모델이 있는 PC에서 내보내기 | `npx kordoc models --export <폴더>` |
| 내 PC로 가져오기 | `npx kordoc models --import <폴더>` |
| 상태 확인 | `npx kordoc models --status` (모두 `verified`여야 한다) |

직접 내려받으려면 `KORDOC_OFFLINE`을 끄고 OCR 파일 하나를 변환하면 kordoc이 받는다. 공용 PC라면 받기 전에 팀에 알린다.

## 4. 주의

- OCR 결과는 띄어쓰기가 빠지거나(예: "최소6개월이상고용하는기업") 여러 단 포스터의 읽는 순서가 섞일 수 있다. 문자열 규칙은 공백을 무시하고 비교하고, OCR 근거는 `OCR_LOW_TRUST`를 유지한다.
- kordoc은 오프라인 일괄 추출에만 쓴다. API 서버(FastAPI)와 Docker 이미지에는 넣지 않는다. 파이썬 쪽은 출력 Markdown만 읽는다.
