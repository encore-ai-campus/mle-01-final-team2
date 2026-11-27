#!/usr/bin/env python3
"""그래프 파일(지금 판정 기준으로 만든 것)과 Neo4j(Aura)를 맞춘다.

빈 DB에 처음 올리기와 이미 적재된 DB 갱신을 이 도구 하나로 한다(2026-11-27, 옛 `load_graph_neo4j.py`·`load_graph_partial.py`를 합쳤다).
"파일이 정답"이라는 원칙으로 동작한다. 저장소에서 다시 만든 `data/graph/*.jsonl`을 기준으로 DB를 비교하고,
승인받은 경우에만 DB를 파일과 같게 바꾼다. 판정 규칙이 바뀌면 `build.py`가 파일을 바꾸고, 이 도구가 그 차이를 DB에 옮긴다.

======================================================================================================
1. 준비
======================================================================================================
  - 패키지: `neo4j`, `python-dotenv`(requirements.txt). 사내망 인증서 오류가 나면 `pip install truststore`(있으면 자동으로 쓴다).
  - 접속 정보는 저장소 루트 `.env`에서 읽는다(값을 출력하지 않는다).
        NEO4J_URI=neo4j+s://<id>.databases.neo4j.io   # 반드시 '://' 포함
        NEO4J_USERNAME=...
        NEO4J_PASSWORD=...
        NEO4J_DATABASE=...                             # 비우면 기본 DB
    같은 이름의 환경 변수가 이미 있으면 `.env`보다 그것을 쓴다(python-dotenv 기본 동작). 로컬 시험 DB에 붙일 때 이 점을 쓴다(아래 4-2).
  - 입력: `data/graph/nodes.jsonl`, `edges.jsonl`(.gitignore 대상). 없으면 `--build`를 주거나 `python tools/graphrag/build.py export`.

======================================================================================================
2. 실행법 (운영 절차: 점검 → 비교 → 승인 → 쓰기 → 점검)
======================================================================================================
  # ① 반영 전 상태를 남긴다(읽기 전용)
  python tools/check_graph_neo4j.py --save data/eval/aura_snapshots/before.json --check-definitions

  # ② 파일을 지금 판정 기준으로 다시 만들고 DB와 비교한다(읽기 전용, 아무것도 쓰지 않음)
  python tools/sync_graph_neo4j.py --build --show 10 --report plan.json

  # ③ 비교 결과(새로·바뀜·지울 것 건수)를 팀에 보여 주고 승인을 받는다. 공용 DB라 이 단계를 건너뛰지 않는다.

  # ④ 승인된 만큼만 쓴다. 아래 셋 중 하나
  python tools/sync_graph_neo4j.py --apply --confirm-host <NEO4J_URI의 호스트>                         # 새로·바뀐 것만(지우지 않음)
  python tools/sync_graph_neo4j.py --apply --prune --confirm-host <호스트>                             # + DB에만 있는 요건·조건 삭제
  python tools/sync_graph_neo4j.py --apply --prune --drop-extra-props --confirm-host <호스트>          # + 파일에 없는 속성까지 삭제

  # ⑤ 반영 후 점검과 전후 비교(읽기 전용)
  python tools/check_graph_neo4j.py --compare data/eval/aura_snapshots/before.json --check-definitions

  그 밖의 쓰임
  python tools/sync_graph_neo4j.py --offline                     # DB 없이 파일 검증과 건수만(CI·로컬에서 먼저 확인)
  python tools/sync_graph_neo4j.py --scope laws --show 10        # 법령 층만 비교
  python tools/sync_graph_neo4j.py --with-rules                  # 정의 판정 기준(rule_json)까지 비교

  빈 DB에 처음 올릴 때도 ④의 첫 줄과 같다. DB가 비어 있으면 모두 "새로"로 나오고, 제약부터 건다.
  전체(30,678 노드·57,631 관계) 첫 적재는 로컬에서 약 44초, Aura 비교는 약 30초 걸렸다(2026-11-27).

======================================================================================================
3. 동작 순서
======================================================================================================
  1. (선택 `--build`) `tools/graphrag/build.py export`로 그래프 파일을 다시 만든다. 시작할 때 판정 옵션(DEFAULT_OPTIONS)을 출력한다.
  2. 파일 검증: 알 수 없는 레이블·관계, 키 없음, 중복 노드·관계, 끝점 없는 관계, 관계 시그니처(설계서 5.2) 위반 → 하나라도 있으면 종료 코드 2.
  3. DB를 READ_ACCESS 세션으로 읽어 비교한다. 노드는 (레이블, 키), 관계는 (타입, 시작 키, 끝 키)로 맞춘다.
     결과는 새로 / 속성 바뀜 / 같음 / DB에만 있음(지울 후보) / DB에만 있는 속성.
  4. `--apply`일 때만 쓴다. 순서: 유일 제약 → 노드 MERGE → 관계 MERGE → (`--prune`) 관계 삭제 → 노드 삭제(DETACH DELETE).
     노드를 먼저 올려야 관계가 끝점을 찾을 수 있고, 지우기는 마지막에 해서 중간에 실패해도 "덜 지운" 상태로만 남게 한다.
  5. 다시 읽어 파일과 같아졌는지 보고 `check_graph_neo4j` 점검(V0~V25)을 돌린다.

  범위(--scope, 여러 개 가능. 기본 전부). 범위 밖의 레이블·관계는 읽지도 쓰지도 지우지도 않는다.
    meta          Notice, Organization, SupportCategory, Concept와 ANNOUNCED_BY, EXECUTED_BY, IN_SUPPORT_CATEGORY, WITHIN, MEMBER_OF, SUCCEEDED_BY, IS_A
    laws          ExternalLaw, LawArticle, LawAppendix, Definition과 PART_OF, DEFINED_BY, CITES_LAW
    requirements  Requirement, Condition과 HAS_REQUIREMENT, HAS_CONDITION, ABOUT

  종료 코드
    0  정상(비교만 했거나, 쓴 뒤 파일과 같고 점검 통과, 또는 이미 같아서 쓸 것 없음)
    2  파일 검증 실패(DB에 접속하지 않음)
    3  쓰지 않고 멈춤: DB 노드 키 없음·중복, 같은 키를 다른 레이블이 씀, 지울 것이 --max-delete 초과
    4  --confirm-host가 실제 접속 호스트와 다름
    5  쓴 뒤에도 파일과 다르거나, 0이어야 하는 점검이 실패

======================================================================================================
4. 안전 장치
======================================================================================================
  - 기본은 읽기 전용 비교다. 쓰기에는 `--apply`와 접속 호스트를 다시 적는 `--confirm-host`가 둘 다 있어야 한다.
  - 지우기는 `--prune`을 따로 줘야 하고, 지울 수 있는 노드 레이블은 `--prune-labels`(기본 Requirement·Condition)뿐이다.
    다른 레이블(공고·개념·법령)은 DB에만 있어도 보고만 한다. 사람이 검수한 노드(`reviewed=true` 또는 `status=reviewed_excerpt`)는
    지우지 않고, 그 노드에 붙은 관계도 지우지 않는다(지우면 고아 노드가 된다).
  - 지울 노드·관계 합계가 `--max-delete`(기본 5,000)를 넘거나, 같은 ID가 DB에서 다른 레이블로 쓰이면 쓰지 않는다.
  - DB에 키 없는 노드나 같은 키가 둘인 노드가 있으면 비교를 믿을 수 없으므로 쓰지 않는다(점검 V0과 같은 조건).
  - DB에만 있는 속성(판정 기준이 바뀌어 파일에서 빠진 속성)은 기본으로 남기고 건수만 보고한다.
    `--drop-extra-props`를 주면 바뀌는 노드의 속성을 파일과 똑같이 바꾼다(`SET n = 속성`, 키·레이블은 유지).
  - Cypher에 넣는 레이블·관계·키 이름은 모두 이 파일의 상수에서 오고, `IDENT` 정규식으로 한 번 더 확인한다. 값은 파라미터로만 넘긴다.

======================================================================================================
5. 시험 방법
======================================================================================================
  5-1. 단위 시험(DB 없음, CI에서 자동 실행: .github/workflows/tools-tests.yml)
       python -m unittest tools.test_sync_graph -v
       ruff check tools/sync_graph_neo4j.py tools/test_sync_graph.py --select F,E9
     파일 검증, 비교(새로·바뀜·지울 것·검수 노드 보호·레이블 충돌·키 없는 노드), 쓰기 문장 순서와 Cypher, 가짜 세션으로 read_db,
     CLI 종료 코드(오프라인·잘못된 파일·--apply와 --offline 동시 사용)를 본다.

  5-2. 쓰기 시험(로컬 일회용 Neo4j, Aura를 건드리지 않음. Docker 필요)
       docker run -d --name neo4j-synctest -p 17687:7687 -e NEO4J_AUTH=neo4j/<시험용 비밀번호> neo4j:5.26-community
       # 환경 변수가 .env보다 앞서므로 이 셸에서만 로컬 DB를 가리킨다
       PowerShell: $env:NEO4J_URI="bolt://localhost:17687"; $env:NEO4J_USERNAME="neo4j"; $env:NEO4J_PASSWORD="<시험용 비밀번호>"; $env:NEO4J_DATABASE="neo4j"
       bash:       export NEO4J_URI=bolt://localhost:17687 NEO4J_USERNAME=neo4j NEO4J_PASSWORD=<시험용 비밀번호> NEO4J_DATABASE=neo4j
       python tools/sync_graph_neo4j.py --apply --confirm-host localhost          # 빈 DB 첫 적재 → "다시 비교: 파일과 같음"
       python tools/sync_graph_neo4j.py --apply --confirm-host localhost          # 다시 실행 → "쓸 것이 없다"(멱등)
       # Cypher로 DB에만 있는 요건·조건·속성을 몇 개 만든 뒤(키는 req_id·cond_id)
       python tools/sync_graph_neo4j.py                                            # 지울 대상이 보이는지
       python tools/sync_graph_neo4j.py --apply --confirm-host 다른호스트           # 종료 코드 4
       python tools/sync_graph_neo4j.py --apply --prune --max-delete 1 --confirm-host localhost   # 종료 코드 3
       python tools/sync_graph_neo4j.py --apply --prune --drop-extra-props --confirm-host localhost
       docker rm -f neo4j-synctest                                                 # 끝나면 지운다
     2026-11-27 시험 결과는 docs/LOAD_Neo4j_적재기록_v0.1.md §10에 있다.

  5-3. 실제 Aura: 위 2의 ①②로 읽기 전용 비교까지만 하고, 쓰기(④)는 팀 승인 뒤에 한다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

# ----------------------------------------------------------------------------- 상수
ROOT = Path(__file__).resolve().parents[1]                              # 저장소 루트
GRAPH = ROOT / "data" / "graph"                                         # build.py export가 쓰는 곳
SCHEMA = ROOT / "docs" / "submission" / "ontology" / "schema.cypher"    # 유일 제약(CREATE CONSTRAINT)을 여기서 읽는다
RULES = GRAPH / "definition_rules.json"                                 # 정의 판정 기준(--with-rules)
BATCH_SIZE = 1000   # UNWIND 한 번에 보내는 행 수. 너무 크면 Aura 트랜잭션 메모리 한도에 걸린다
MAX_DELETE = 5000   # 한 번에 지울 수 있는 노드·관계 합계. 판정 기준 실수로 대량 삭제되는 것을 막는다
AURA_FREE_LIMITS = {"nodes": 200_000, "relationships": 400_000}  # Aura Free 한도. 인스턴스 등급이 다르면 달라진다

# 레이블 -> 유일 키 속성. 노드를 맞출 때 이 키만 쓴다(schema.cypher의 유일 제약과 같다).
# Track·Program·Attachment는 설계에만 있고 아직 파일에 없다(본문 요건 단계).
KEY = {"Notice": "notice_id", "Organization": "org_id", "SupportCategory": "category_id", "Concept": "concept_id",
       "Requirement": "req_id", "Condition": "cond_id", "Definition": "def_id", "ExternalLaw": "law_id",
       "LawArticle": "article_id", "LawAppendix": "appendix_id", "Track": "track_id", "Program": "program_id", "Attachment": "attachment_id"}
# --scope 이름 -> 그 범위가 다루는 레이블·관계. 설계서의 세 층(메타·법령·요건)과 같다.
SCOPES = {
    "meta": {"labels": ["Notice", "Organization", "SupportCategory", "Concept"],
             "edges": ["ANNOUNCED_BY", "EXECUTED_BY", "IN_SUPPORT_CATEGORY", "WITHIN", "MEMBER_OF", "SUCCEEDED_BY", "IS_A"]},
    "laws": {"labels": ["ExternalLaw", "LawArticle", "LawAppendix", "Definition"], "edges": ["PART_OF", "DEFINED_BY", "CITES_LAW"]},
    "requirements": {"labels": ["Requirement", "Condition"], "edges": ["HAS_REQUIREMENT", "HAS_CONDITION", "ABOUT"]},
}
# 관계 시그니처(설계서 5.2): 관계 -> [(시작 레이블, 끝 레이블)]
SIGNATURE = {"ANNOUNCED_BY": [("Notice", "Organization")], "EXECUTED_BY": [("Notice", "Organization")],
             "IN_SUPPORT_CATEGORY": [("Notice", "SupportCategory")], "WITHIN": [("Concept", "Concept")], "MEMBER_OF": [("Concept", "Concept")],
             "SUCCEEDED_BY": [("Concept", "Concept")], "IS_A": [("Concept", "Concept")], "HAS_REQUIREMENT": [("Notice", "Requirement")],
             "HAS_CONDITION": [("Requirement", "Condition")], "ABOUT": [("Condition", "Concept")],
             "PART_OF": [("LawArticle", "ExternalLaw"), ("LawAppendix", "ExternalLaw")], "DEFINED_BY": [("Concept", "Definition")],
             "CITES_LAW": [("Definition", "LawArticle"), ("Definition", "LawAppendix")]}
# --prune으로 지울 수 있는 기본 레이블. 판정 기준이 바뀌면 생기고 없어지는 것은 요건·조건뿐이다.
# 공고·개념·법령은 다른 데이터(정답셋·API 응답)가 가리키므로 기본으로 지우지 않는다.
PRUNE_DEFAULT = ("Requirement", "Condition")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # Cypher에 문자열로 넣는 이름 확인용(파라미터로 넘길 수 없는 부분)


# ----------------------------------------------------------------------------- 파일
def read_jsonl(path: Path) -> list[dict]:
    """JSONL 한 줄 = 레코드 하나. 빈 줄은 건너뛴다."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def load_files(graph_dir: Path) -> tuple[list[dict], list[dict]]:
    """노드 레코드: {"label": 레이블, <키>: id, ...속성}. 관계 레코드: {"type": 타입, "from": 시작 id, "to": 끝 id, ...속성}."""
    return read_jsonl(graph_dir / "nodes.jsonl"), read_jsonl(graph_dir / "edges.jsonl")


def props(record: dict, drop: Iterable[str]) -> dict[str, Any]:
    """Neo4j 속성으로 쓸 수 있는 값만 남긴다. None은 속성을 만들지 않고, 맵·중첩 목록은 JSON 문자열로 바꾼다.

    Neo4j 속성은 원시값과 원시값 목록만 받는다. 비교도 이 함수의 결과로 하므로, DB에서 읽은 값(JSON 문자열)과
    파일 값이 같은 모양이 되어 "바뀜"으로 잘못 잡히지 않는다. `_`로 시작하는 키는 빌드 내부용이라 올리지 않는다.
    """
    out: dict[str, Any] = {}
    for k, v in record.items():
        if k in drop or v is None or k.startswith("_"):
            continue
        if isinstance(v, dict) or (isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v)):
            v = json.dumps(v, ensure_ascii=False)
        out[k] = v
    return out


def node_id(n: dict) -> str | None:
    """노드 레코드의 키 값(레이블마다 키 이름이 다르다). 모르는 레이블이면 None."""
    return n.get(KEY.get(n.get("label", ""), ""))


def node_props(n: dict) -> dict[str, Any]:
    """DB에 쓸 노드 속성. 레이블과 키는 MERGE 패턴에 들어가므로 속성에서 뺀다."""
    return props(n, {"label", KEY[n["label"]]})


def edge_props(e: dict) -> dict[str, Any]:
    """DB에 쓸 관계 속성(evidence·source·option 등). 타입·끝점은 패턴에 들어가므로 뺀다."""
    return props(e, {"type", "from", "to"})


def validate(nodes: list[dict], edges: list[dict]) -> list[str]:
    """파일 자체의 문제. 비어 있어야 비교·적재한다.

    DB에 접속하기 전에 막아야 하는 것들이다. 파일이 틀리면 비교 결과도 틀리고, 잘못된 관계가 DB에 생긴다.
    - 알 수 없는 레이블·관계 타입(KEY·SIGNATURE에 없음)
    - 키가 없는 노드, 같은 (레이블, 키)가 두 번 나오는 노드
    - 끝점 노드가 파일에 없는 관계, 설계서 5.2 시그니처에 없는 (시작, 끝) 레이블 조합
    - 같은 (타입, 시작, 끝) 관계가 두 번(MERGE하면 하나로 합쳐져 건수가 어긋난다)
    문제는 앞 50개까지만 돌려준다(출력이 너무 길어지지 않게).
    """
    errors: list[str] = []
    by_id: dict[str, str] = {}
    seen: Counter = Counter()
    for n in nodes:
        label = n.get("label")
        if label not in KEY:
            errors.append(f"알 수 없는 레이블: {label}")
            continue
        nid = node_id(n)
        if not nid:
            errors.append(f"{label} 노드에 {KEY[label]}가 없음")
            continue
        seen[(label, nid)] += 1
        by_id[nid] = label
    errors += [f"중복 노드 {label}:{nid}" for (label, nid), c in seen.items() if c > 1][:20]
    pairs: Counter = Counter()
    for e in edges:
        sig = SIGNATURE.get(e.get("type"))
        if not sig:
            errors.append(f"알 수 없는 관계 타입: {e.get('type')}")
            continue
        pairs[(e["type"], e["from"], e["to"])] += 1
        a, b = by_id.get(e["from"]), by_id.get(e["to"])
        if a is None or b is None:
            errors.append(f"끝점이 없는 관계 {e['type']}: {e['from']} -> {e['to']}")
        elif (a, b) not in sig:
            errors.append(f"시그니처 위반 {e['type']}: {a} -> {b} (허용 {', '.join(f'{x} -> {y}' for x, y in sig)})")
    errors += [f"중복 관계 {t}: {f} -> {to}" for (t, f, to), c in pairs.items() if c > 1][:20]
    return errors[:50]


def with_rules(nodes: list[dict], path: Path = RULES) -> tuple[list[dict], list[str]]:
    """정의 판정 기준(`definition_rules.json`)을 같은 ID의 Definition 노드 속성으로 붙인다. 없는 정의는 문제로 돌려준다.

    판정 기준은 검수 상태가 따로 있어 기본 적재에 넣지 않는다. `--with-rules`를 줄 때만 붙이며,
    기준을 JSON 문자열(`rule_json`, 키 정렬)로 넣어 같은 기준이면 비교에서 "같음"이 되게 한다.
    """
    rules = json.loads(path.read_text(encoding="utf-8"))
    by_def = {n["def_id"]: n for n in nodes if n["label"] == "Definition"}
    missing = [f"판정 기준의 정의가 파일에 없음: {d}" for d in rules if d not in by_def]
    for def_id, rule in rules.items():
        if def_id in by_def:
            by_def[def_id].update({"rule_json": json.dumps(rule, ensure_ascii=False, sort_keys=True), "rule_id": rule["rule_id"],
                                   "rule_status": rule["status"], "rule_needs_review": rule["needs_review"]})
    return nodes, missing


def scope_sets(scopes: Iterable[str]) -> tuple[set[str], set[str]]:
    """--scope 이름들 -> (다룰 레이블 집합, 다룰 관계 타입 집합)."""
    return ({l for s in scopes for l in SCOPES[s]["labels"]}, {t for s in scopes for t in SCOPES[s]["edges"]})


def in_scope(nodes: list[dict], edges: list[dict], scopes: Iterable[str]) -> tuple[list[dict], list[dict]]:
    """범위 안의 노드·관계만 남긴다. 범위 밖 노드는 관계 끝점 레이블을 찾는 데만 쓴다(write_plan의 all_nodes)."""
    labels, types = scope_sets(scopes)
    return [n for n in nodes if n["label"] in labels], [e for e in edges if e["type"] in types]


def constraints_for(labels: set[str]) -> list[str]:
    """schema.cypher의 CREATE CONSTRAINT 중 해당 레이블 것.

    제약은 제출 문서(schema.cypher) 한 곳에만 두고 여기서 읽는다. `IF NOT EXISTS`라 여러 번 걸어도 된다.
    유일 제약은 MERGE를 빠르게 하는 인덱스 역할도 하므로 노드보다 먼저 건다.
    """
    out = []
    if SCHEMA.exists():
        for line in SCHEMA.read_text(encoding="utf-8").split("\n"):
            m = re.match(r"CREATE CONSTRAINT\s+\w+\s+IF NOT EXISTS FOR \(\w+:(\w+)\)", line.strip())
            if m and m.group(1) in labels:
                out.append(line.strip())
    return out


# ----------------------------------------------------------------------------- 비교
def is_protected(p: dict) -> bool:
    """사람이 검수한 노드. DB에만 있어도 지우지 않는다."""
    return p.get("reviewed") is True or p.get("status") == "reviewed_excerpt"


def diff_graph(nodes: list[dict], edges: list[dict], db: dict, prune_labels: Iterable[str] = PRUNE_DEFAULT,
               drop_extra: bool = False) -> dict:
    """파일(범위 안)과 DB 스냅숏을 비교한다. DB에 접속하지 않는 순수 함수라 단위 시험이 이것을 주로 본다.

    db = read_db()의 결과: {"nodes": {(레이블, id): 속성}, "labels": {id: [레이블]}, "edges": {(타입, from, to): 속성},
                           "edge_labels": {(타입, from, to): (시작 레이블, 끝 레이블)}, "bad_keys": {레이블: 건수}}

    돌려주는 것
      nodes/edges.new·changed·same  파일 기준 분류. changed는 (노드, [바뀐 속성 이름]) 목록. 지울 속성은 이름 앞에 '-'
      stale_nodes      DB에만 있고 지울 수 있는 노드(prune_labels 안, 검수 안 됨)
      kept_stale_nodes DB에만 있지만 prune_labels 밖이라 남기는 노드
      protected        DB에만 있지만 사람이 검수해 남기는 노드
      stale_edges      DB에만 있고 따로 지울 관계(지울 노드에 붙은 관계는 detached_edges로 센다)
      kept_edges       남기는 노드에 붙어 있어 지우지 않는 관계
      extra_props      DB에만 있는 속성 이름별 건수
      conflicts        하나라도 있으면 쓰지 않는다(키 없는 DB 노드, 같은 키의 다른 레이블)
    """
    prune_labels = set(prune_labels)
    out: dict[str, Any] = {"nodes": {"new": [], "changed": [], "same": 0}, "edges": {"new": [], "changed": [], "same": 0},
                           "stale_nodes": [], "kept_stale_nodes": [], "protected": [], "stale_edges": [], "detached_edges": 0, "kept_edges": 0,
                           "extra_props": Counter(), "conflicts": [
                               f"DB {label} 노드 {c}개: 키({KEY[label]})가 없거나 중복이다(V0)" if label in KEY
                               else f"DB {label} {c}개: 끝 노드에 키가 없다" for label, c in sorted(db.get("bad_keys", {}).items())]}
    # 1) 파일의 노드를 하나씩 DB와 맞춘다
    file_keys = set()
    for n in nodes:
        k = (n["label"], node_id(n))
        file_keys.add(k)
        # 같은 id가 DB에서 다른 주 레이블(KEY에 있는 레이블)로 쓰이면 MERGE가 새 노드를 만들어 id가 둘이 된다 → 멈춘다.
        # 보조 레이블(Region)은 KEY에 없으므로 충돌로 보지 않는다.
        other = [x for x in db["labels"].get(k[1], []) if x in KEY and x != n["label"]]
        if other:
            out["conflicts"].append(f"{k[1]}: 파일은 {n['label']}, DB에는 {'·'.join(sorted(set(other)))}")
        cur = db["nodes"].get(k)
        if cur is None:
            out["nodes"]["new"].append(n)
            continue
        want = node_props(n)
        keys = sorted(x for x, v in want.items() if cur.get(x) != v)              # 값이 다르거나 DB에 없는 속성
        extra = sorted(x for x in cur if x not in want and x != KEY[n["label"]])  # DB에만 있는 속성(옛 판정 기준의 흔적)
        out["extra_props"].update(f"{n['label']}.{x}" for x in extra)
        if drop_extra:
            keys += [f"-{x}" for x in extra]  # 지울 속성은 앞에 '-'
        if keys:
            out["nodes"]["changed"].append((n, keys))
        else:
            out["nodes"]["same"] += 1
    # 2) DB에만 있는 노드를 지울 것 / 남길 것으로 나눈다
    deleted_ids = set()
    for (label, nid), p in sorted(db["nodes"].items()):
        if (label, nid) in file_keys:
            continue
        if is_protected(p):
            out["protected"].append((label, nid))
        elif label in prune_labels:
            out["stale_nodes"].append((label, nid))
            deleted_ids.add(nid)
        else:
            out["kept_stale_nodes"].append((label, nid))
    kept_ids = {nid for _, nid in out["protected"] + out["kept_stale_nodes"]}
    # 3) 파일의 관계를 DB와 맞춘다. 관계는 (타입, 시작 id, 끝 id)가 같으면 같은 관계로 본다
    file_edges = {}
    for e in edges:
        file_edges[(e["type"], e["from"], e["to"])] = e
        cur = db["edges"].get((e["type"], e["from"], e["to"]))
        if cur is None:
            out["edges"]["new"].append(e)
        elif any(cur.get(x) != v for x, v in edge_props(e).items()):
            out["edges"]["changed"].append(e)
        else:
            out["edges"]["same"] += 1
    # 4) DB에만 있는 관계: 지울 노드에 붙은 것 / 남길 노드에 붙은 것 / 따로 지울 것
    for k in sorted(db["edges"]):
        if k in file_edges:
            continue
        if k[1] in deleted_ids or k[2] in deleted_ids:
            out["detached_edges"] += 1  # 노드를 지우면(DETACH DELETE) 함께 없어진다
        elif k[1] in kept_ids or k[2] in kept_ids:
            out["kept_edges"] += 1  # 남기는 노드(검수·범위 밖)의 관계는 지우지 않는다. 지우면 고아가 된다
        else:
            out["stale_edges"].append(k)
    return out


def summary(d: dict) -> dict:
    """diff_graph 결과를 건수로 줄인다(출력과 --report JSON에 쓴다)."""
    return {"nodes_new": len(d["nodes"]["new"]), "nodes_changed": len(d["nodes"]["changed"]), "nodes_same": d["nodes"]["same"],
            "edges_new": len(d["edges"]["new"]), "edges_changed": len(d["edges"]["changed"]), "edges_same": d["edges"]["same"],
            "delete_nodes": dict(Counter(l for l, _ in d["stale_nodes"])), "delete_edges": dict(Counter(t for t, _, _ in d["stale_edges"])),
            "detached_edges": d["detached_edges"], "kept_stale_nodes": dict(Counter(l for l, _ in d["kept_stale_nodes"])),
            "protected": len(d["protected"]), "kept_edges": d["kept_edges"], "conflicts": len(d["conflicts"]),
            "changed_props": dict(Counter(f"{n['label']}.{k}" for n, ks in d["nodes"]["changed"] for k in ks).most_common()),
            "extra_props_in_db": dict(d["extra_props"].most_common())}


def delete_count(d: dict) -> int:
    """--prune일 때 없어지는 노드·관계 합계(--max-delete와 비교한다). 노드와 함께 없어지는 관계도 센다."""
    return len(d["stale_nodes"]) + len(d["stale_edges"]) + d["detached_edges"]


def is_synced(d: dict, prune: bool) -> bool:
    """쓸 것이 없는가. prune=False면 DB에만 있는 노드·관계는 따지지 않는다(지우지 않기로 했으므로).
    남기기로 한 노드(검수·범위 밖)와 그 관계는 어느 쪽이든 따지지 않는다."""
    s = summary(d)
    clean = not (s["nodes_new"] or s["nodes_changed"] or s["edges_new"] or s["edges_changed"])
    return clean and (not prune or not (d["stale_nodes"] or d["stale_edges"]))


# ----------------------------------------------------------------------------- Cypher
def node_upserts(nodes: list[dict], replace: bool = False) -> list[tuple[str, str, list[dict]]]:
    """새로·바뀐 노드를 쓰는 문장. 반환은 (설명, cypher, 행) 목록이고 레이블별로 한 문장씩이다.

    MERGE (n:레이블 {키: row.id})  — 키로 찾고 없으면 만든다. 같은 파일을 몇 번 넣어도 결과가 같다(멱등).
    SET n += row.props           — 파일의 속성을 덮어쓰고, DB에만 있는 속성은 그대로 둔다(기본).
    SET n = row.props            — replace=True(--drop-extra-props). 속성을 파일과 똑같이 바꾼다. 이때 키도 지워지지 않게 행에 넣는다.
    REGION 개념에는 보조 레이블 Region을 붙인다(설계서 D-2, 지역 조회용).
    """
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for n in nodes:
        label, key = n["label"], KEY[n["label"]]
        suffix = ":Region" if label == "Concept" and n.get("scheme") == "REGION" else ""
        groups[(label + suffix, key)].append({"id": n[key], "props": {key: n[key], **node_props(n)} if replace else node_props(n)})
    out = []
    for (labels, key), rows in sorted(groups.items()):
        assert all(IDENT.match(x) for x in labels.split(":") + [key])
        op = "=" if replace else "+="
        out.append((f"노드 {labels} {len(rows)}개", f"UNWIND $rows AS row MERGE (n:{labels} {{{key}: row.id}}) SET n {op} row.props", rows))
    return out


def edge_upserts(edges: list[dict], label_of: dict[str, str]) -> list[tuple[str, str, list[dict]]]:
    """새로·바뀐 관계를 쓰는 문장. (타입, 시작 레이블, 끝 레이블)별로 한 문장씩이다.

    끝점을 레이블+키로 MATCH해야 유일 제약 인덱스를 탄다. 레이블 없이 찾으면 전체 노드를 훑어 느려진다.
    label_of는 id -> 레이블. 범위 밖 노드(예: requirements 범위의 ABOUT 끝점 Concept)도 찾을 수 있게 전체 파일과 DB에서 만든다.
    끝점이 DB에 없으면 MATCH가 실패해 그 행은 조용히 빠진다. 그래서 쓴 뒤 다시 비교해 "아직 다름"을 잡는다.
    """
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for e in edges:
        groups[(e["type"], label_of[e["from"]], label_of[e["to"]])].append({"from": e["from"], "to": e["to"], "props": edge_props(e)})
    out = []
    for (t, a, b), rows in sorted(groups.items()):
        assert all(IDENT.match(x) for x in (t, a, b))
        out.append((f"관계 {t} ({a}->{b}) {len(rows)}개",
                    f"UNWIND $rows AS row MATCH (a:{a} {{{KEY[a]}: row.from}}) MATCH (b:{b} {{{KEY[b]}: row.to}}) "
                    f"MERGE (a)-[r:{t}]->(b) SET r += row.props", rows))
    return out


def edge_deletes(stale: list[tuple[str, str, str]], edge_labels: dict[tuple[str, str, str], tuple[str, str]]) -> list[tuple[str, str, list[dict]]]:
    """DB에만 있는 관계를 지우는 문장(--prune). 노드는 남기고 관계만 지운다.

    끝점 레이블은 DB에서 읽을 때 기록한 것(edge_labels)을 쓴다. 끝점이 파일에 없거나 범위 밖이어도 지울 수 있다.
    """
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for t, f, to in stale:
        a, b = edge_labels[(t, f, to)]
        groups[(t, a, b)].append({"from": f, "to": to})
    out = []
    for (t, a, b), rows in sorted(groups.items()):
        assert all(IDENT.match(x) for x in (t, a, b))
        out.append((f"관계 삭제 {t} ({a}->{b}) {len(rows)}개",
                    f"UNWIND $rows AS row MATCH (a:{a} {{{KEY[a]}: row.from}})-[r:{t}]->(b:{b} {{{KEY[b]}: row.to}}) DELETE r", rows))
    return out


def node_deletes(stale: list[tuple[str, str]]) -> list[tuple[str, str, list[dict]]]:
    """DB에만 있는 노드를 지우는 문장(--prune). DETACH DELETE라 붙은 관계도 함께 없어진다(detached_edges로 미리 센 것)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for label, nid in stale:
        groups[label].append({"id": nid})
    out = []
    for label, rows in sorted(groups.items()):
        assert IDENT.match(label)
        out.append((f"노드 삭제 {label} {len(rows)}개", f"UNWIND $rows AS row MATCH (n:{label} {{{KEY[label]}: row.id}}) DETACH DELETE n", rows))
    return out


def write_plan(d: dict, all_nodes: list[dict], db: dict, prune: bool, scope_labels: set[str],
               replace_props: bool = False) -> list[tuple[str, str, list[dict]]]:
    """쓰는 순서대로 문장 목록: 제약 → 노드 → 관계 → (prune) 관계 삭제 → 노드 삭제.

    노드가 먼저 있어야 관계가 끝점을 찾는다. 지우기를 마지막에 두면 중간에 실패해도 "추가는 됐고 덜 지운" 상태로만 남아,
    같은 명령을 다시 돌리면 이어서 맞출 수 있다.
    """
    # id -> 주 레이블. DB 값을 먼저 넣고 파일 값으로 덮는다(둘 다 있으면 파일이 기준)
    label_of = {i: next(x for x in ls if x in KEY) for i, ls in db["labels"].items() if any(x in KEY for x in ls)}
    label_of.update({node_id(n): n["label"] for n in all_nodes})
    out = [("제약", c, []) for c in constraints_for(scope_labels)]
    out += node_upserts(d["nodes"]["new"] + [n for n, _ in d["nodes"]["changed"]], replace_props)
    out += edge_upserts(d["edges"]["new"] + d["edges"]["changed"], label_of)
    if prune:
        out += edge_deletes(d["stale_edges"], db["edge_labels"]) + node_deletes(d["stale_nodes"])
    return out


def batches(rows: list, size: int = BATCH_SIZE) -> Iterable[list]:
    """행을 BATCH_SIZE씩 나눈다. 묶음마다 별도 트랜잭션이다."""
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


# ----------------------------------------------------------------------------- DB
def connect():
    """.env(또는 같은 이름의 환경 변수)로 접속한다. (드라이버, DB 이름, 호스트)를 돌려준다.

    호스트는 --confirm-host와 비교하는 값이다(예: 4fcaaade.databases.neo4j.io, 로컬은 localhost).
    비밀번호 등 접속 정보는 출력하지 않는다.
    """
    try:
        import truststore  # Windows 인증서 저장소를 쓴다. 없으면 Python 기본 번들로 검증한다(사내망에서 실패할 수 있음)
        truststore.inject_into_ssl()
    except ImportError:
        print("참고: truststore가 없어 기본 인증서 번들을 쓴다. 인증서 오류가 나면 `pip install truststore`", file=sys.stderr)
    from dotenv import load_dotenv
    from neo4j import GraphDatabase
    load_dotenv(ROOT / ".env")
    uri, user, pw, db = os.getenv("NEO4J_URI") or "", os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"), os.getenv("NEO4J_DATABASE") or None
    if "://" not in uri:
        raise SystemExit("NEO4J_URI에 '://'가 없다. 예: neo4j+s://<id>.databases.neo4j.io")
    if not (user and pw):
        raise SystemExit("NEO4J_USERNAME, NEO4J_PASSWORD가 .env에 없다")
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    driver.verify_connectivity()
    return driver, db, uri.split("://", 1)[1].split("/")[0].split(":")[0]


def read_db(session, scopes: Iterable[str]) -> dict:
    """범위 안의 노드·관계를 모두 읽는다(읽기 전용 세션). 관계는 시그니처별로 읽고, 시그니처 밖 관계는 건수만 센다.

    3만 노드 규모라 한 번에 모두 읽어 메모리에서 비교한다(Aura에서 약 30초).
    - 노드: (레이블, 키) -> 속성. labels에는 id별 모든 레이블(보조 레이블 Region 포함)을 모아 레이블 충돌을 찾는다.
    - 관계: (타입, 시작 키, 끝 키) -> 속성. 끝점 레이블도 기록해 삭제 문장에서 쓴다.
    - 키가 없거나 중복인 노드, 그런 노드에 붙은 관계는 비교에서 빼고 bad_keys로 센다(있으면 diff_graph가 쓰기를 막는다).
    - 시그니처 밖 관계(설계에 없는 조합)는 건드리지 않고 off_signature로 건수만 보고한다.
    """
    labels, types = scope_sets(scopes)
    nodes: dict[tuple[str, str], dict] = {}
    by_id: dict[str, list[str]] = {}
    bad_keys: dict[str, int] = {}  # 키가 없거나 같은 키가 두 번 이상인 노드 수(레이블별)
    for label in sorted(labels):
        key = KEY[label]
        for r in session.run(f"MATCH (n:{label}) RETURN n.{key} AS i, properties(n) AS p, labels(n) AS ls"):
            if r["i"] is None or (label, r["i"]) in nodes:
                bad_keys[label] = bad_keys.get(label, 0) + 1
                continue
            nodes[(label, r["i"])] = r["p"]
            by_id.setdefault(r["i"], [])
            by_id[r["i"]] += [x for x in r["ls"] if x not in by_id[r["i"]]]
    edges: dict[tuple[str, str, str], dict] = {}
    edge_labels: dict[tuple[str, str, str], tuple[str, str]] = {}
    duplicates = 0
    off_signature: dict[str, int] = {}
    for t in sorted(types):
        n_sig = 0
        for a, b in SIGNATURE[t]:
            for r in session.run(f"MATCH (a:{a})-[r:{t}]->(b:{b}) RETURN a.{KEY[a]} AS f, b.{KEY[b]} AS t, properties(r) AS p"):
                n_sig += 1
                if r["f"] is None or r["t"] is None:  # 키 없는 노드에 붙은 관계는 비교할 수 없다
                    bad_keys[f"{t} 관계"] = bad_keys.get(f"{t} 관계", 0) + 1
                    continue
                k = (t, r["f"], r["t"])
                if k in edges:
                    duplicates += 1
                edges[k] = r["p"]
                edge_labels[k] = (a, b)
        total = session.run(f"MATCH ()-[r:{t}]->() RETURN count(r) AS c").single()["c"]
        if total != n_sig:
            off_signature[t] = total - n_sig
    return {"nodes": nodes, "labels": by_id, "edges": edges, "edge_labels": edge_labels, "duplicates": duplicates,
            "off_signature": off_signature, "bad_keys": bad_keys}


def run_writes(driver, db, stmts: list[tuple[str, str, list[dict]]]) -> None:
    """문장을 순서대로 실행한다. 행이 없는 문장(제약)은 한 번, 행이 있으면 묶음마다 한 번. 실패하면 예외로 멈춘다."""
    with driver.session(database=db) as s:
        for desc, cypher, rows in stmts:
            if not rows:
                s.run(cypher).consume()
                continue
            for chunk in batches(rows):
                s.run(cypher, rows=chunk).consume()
            print(f"  {desc}")


# ----------------------------------------------------------------------------- 출력
def print_options() -> dict:
    """그래프 파일을 만든 판정 기준(선택지)을 출력한다. 실행 기록에 "어느 기준으로 올렸는지"가 남게 하려는 것이다.
    graphrag를 읽을 수 없으면 빈 dict."""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from graphrag.evaluator import DEFAULT_OPTIONS
        opts = dict(DEFAULT_OPTIONS.__dict__)
    except Exception as exc:  # noqa: BLE001  판정 기준 표시는 부가 정보라 실패해도 진행한다
        print(f"참고: 판정 기준을 읽지 못했다({exc})")
        return {}
    print("판정 기준(tools/graphrag/evaluator.py DEFAULT_OPTIONS):", ", ".join(f"{k}={v}" for k, v in opts.items()))
    return opts


def print_diff(d: dict, db: dict, show: int) -> None:
    """비교 결과를 사람이 읽게 출력한다. show개씩 예시 id도 보인다(승인 받을 때 이 출력을 그대로 보여 준다)."""
    s = summary(d)
    print(f"  노드: 새로 {s['nodes_new']:,}, 속성 바뀜 {s['nodes_changed']:,}, 같음 {s['nodes_same']:,}")
    print(f"  관계: 새로 {s['edges_new']:,}, 속성 바뀜 {s['edges_changed']:,}, 같음 {s['edges_same']:,}")
    print(f"  DB에만 있음(지울 대상): 노드 {s['delete_nodes'] or 0}, 관계 {s['delete_edges'] or 0}, 노드와 함께 없어질 관계 {s['detached_edges']:,}")
    if s["kept_stale_nodes"]:
        print(f"  DB에만 있지만 지우지 않는 노드(--prune-labels 밖): {s['kept_stale_nodes']}")
    if s["protected"]:
        print(f"  DB에만 있지만 사람이 검수해 지우지 않는 노드: {s['protected']}")
    if s["kept_edges"]:
        print(f"  남기는 노드에 붙어 있어 지우지 않는 관계: {s['kept_edges']}")
    if s["changed_props"]:
        print(f"  바뀌는 속성: {s['changed_props']}")
    if s["extra_props_in_db"]:
        print(f"  DB에만 있는 속성(--drop-extra-props일 때만 지운다): {s['extra_props_in_db']}")
    if db.get("duplicates"):
        print(f"  DB의 중복 관계(같은 타입·끝점): {db['duplicates']:,}")
    if db.get("off_signature"):
        print(f"  시그니처 밖 관계(읽지도 지우지도 않음): {db['off_signature']}")
    if show:
        for name, rows in (("새 노드", [node_id(n) for n in d["nodes"]["new"]]),
                           ("바뀐 노드", [f"{node_id(n)} {ks}" for n, ks in d["nodes"]["changed"]]),
                           ("지울 노드", [f"{l}:{i}" for l, i in d["stale_nodes"]]),
                           ("지울 관계", [f"{t} {f} -> {to}" for t, f, to in d["stale_edges"]])):
            if rows:
                print(f"  {name} 예: " + "; ".join(rows[:show]))


# ----------------------------------------------------------------------------- 실행
def main(argv: list[str] | None = None) -> int:
    """명령행 진입점. 반환값이 종료 코드다(모듈 설명 3의 표)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="먼저 build.py export로 그래프 파일을 다시 만든다")
    ap.add_argument("--graph-dir", type=Path, default=GRAPH, help="nodes.jsonl·edges.jsonl이 있는 폴더(기본 data/graph)")
    ap.add_argument("--scope", nargs="+", choices=list(SCOPES), default=list(SCOPES), help="다룰 층(기본 전부). 범위 밖은 읽지도 쓰지도 않는다")
    ap.add_argument("--with-rules", action="store_true", help="definition_rules.json의 판정 기준을 Definition 속성으로 함께 올린다(승인 후)")
    ap.add_argument("--offline", action="store_true", help="DB에 접속하지 않고 파일 검증과 건수만 본다")
    ap.add_argument("--show", type=int, default=5, help="비교 예시를 몇 개씩 보일지")
    ap.add_argument("--report", type=Path, help="비교 결과 요약을 JSON으로 저장한다")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다")
    ap.add_argument("--confirm-host", help="--apply 때 접속 대상 호스트를 다시 적는다(오적재 방지)")
    ap.add_argument("--prune", action="store_true", help="--apply 때 DB에만 있는 관계와 --prune-labels 노드를 지운다")
    ap.add_argument("--prune-labels", nargs="+", choices=sorted(KEY), default=list(PRUNE_DEFAULT))
    ap.add_argument("--max-delete", type=int, default=MAX_DELETE, help="지울 노드·관계 합계 상한")
    ap.add_argument("--drop-extra-props", action="store_true", help="파일에 없는 노드 속성을 DB에서 지운다(속성을 파일과 똑같이)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서 한글이 깨지지 않게
    if a.apply and a.offline:
        ap.error("--apply와 --offline은 함께 쓸 수 없다")
    if a.prune and not a.apply:
        print("참고: --prune은 --apply와 함께일 때만 지운다. 지금은 지울 대상을 보여 주기만 한다.")

    # ---- 1. (선택) 파일 다시 만들기와 판정 기준 표시
    if a.build:
        sys.path.insert(0, str(ROOT / "tools"))
        from graphrag.build import export
        from graphrag.engine import Engine
        if a.graph_dir.resolve() != GRAPH.resolve():
            ap.error("--build는 기본 --graph-dir(data/graph)에만 쓴다")
        print("그래프 파일 다시 만들기(build.py export)")
        export(Engine())
    options = print_options()

    # ---- 2. 파일 읽기와 검증(DB 접속 전)
    all_nodes, all_edges = load_files(a.graph_dir)
    problems = validate(all_nodes, all_edges)
    if a.with_rules:
        all_nodes, missing = with_rules(all_nodes)
        problems += missing
    print(f"입력: 노드 {len(all_nodes):,}개, 관계 {len(all_edges):,}개 ({a.graph_dir})")
    if problems:
        print("파일 검증 실패(DB에 접속하지 않는다):", *problems, sep="\n  - ")
        return 2
    print("파일 검증: 중복 노드·관계 0, 끝점 없는 관계 0, 시그니처 위반 0")
    nodes, edges = in_scope(all_nodes, all_edges, a.scope)
    scope_labels, _ = scope_sets(a.scope)
    print(f"범위 {'+'.join(a.scope)}: 노드 {len(nodes):,} {dict(sorted(Counter(n['label'] for n in nodes).items()))}")
    print(f"  관계 {len(edges):,} {dict(sorted(Counter(e['type'] for e in edges).items()))}")
    for limit, name in (("nodes", "노드"), ("relationships", "관계")):
        used = len(all_nodes) if limit == "nodes" else len(all_edges)
        print(f"  Aura Free 한도 {name}: {used:,} / {AURA_FREE_LIMITS[limit]:,} ({used / AURA_FREE_LIMITS[limit]:.1%})")
    report: dict[str, Any] = {"scope": a.scope, "options": options, "file": {"nodes": len(nodes), "relationships": len(edges)}}
    if a.offline:
        if a.report:
            a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n오프라인 확인 끝. DB에 접속하지 않았다.")
        return 0

    # ---- 3. DB를 읽기 전용으로 읽고 비교. 점검 스냅숏(before)도 같은 세션에서 떠서 쓰기 전후를 비교한다
    import check_graph_neo4j as CHK
    from neo4j import READ_ACCESS
    driver, db_name, host = connect()
    try:
        with driver.session(database=db_name, default_access_mode=READ_ACCESS, notifications_min_severity="OFF") as s:
            db = read_db(s, a.scope)
            before = CHK.collect(s)
        d = diff_graph(nodes, edges, db, a.prune_labels, a.drop_extra_props)
        report["diff"] = summary(d)
        report["host"] = host
        print(f"\nDB 비교({host}, 읽기 전용): DB 범위 안 노드 {len(db['nodes']):,}, 관계 {len(db['edges']):,}")
        print_diff(d, db, a.show)
        # ---- 4. 멈출 조건(충돌·삭제 한도) → 이미 같음 → 비교만 → 호스트 확인 순서로 본다
        stop = list(d["conflicts"])
        n_delete = delete_count(d) if a.prune else 0
        if n_delete > a.max_delete:
            stop.append(f"지울 노드·관계 {n_delete:,}개가 --max-delete {a.max_delete:,}를 넘는다")
        if a.report:
            a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=list) + "\n", encoding="utf-8")
            print(f"비교 요약 저장: {a.report}")
        if stop:
            print("\n문제(쓰지 않는다):", *stop[:30], sep="\n  - ")
            return 3
        # 비교만 할 때(--apply 없음)는 지울 것까지 따져 "같다"고 말한다. --apply만 줬으면 지울 것은 따지지 않는다
        if is_synced(d, a.prune or not a.apply):
            print("\nDB가 이미 파일과 같다. 쓸 것이 없다.")
            return 0
        if a.apply and not a.prune and (d["stale_nodes"] or d["stale_edges"]):
            print("참고: DB에만 있는 노드·관계는 이번에 지우지 않는다(--prune을 주면 지운다).")
        if not a.apply:
            print("\n비교 끝. 아무것도 쓰지 않았다. 쓰려면 --apply --confirm-host <호스트> (지우기까지는 --prune).")
            return 0
        if a.confirm_host != host:
            print(f"중단: --confirm-host가 접속 대상 호스트({host})와 같아야 한다.")
            return 4
        # ---- 5. 쓰기. 쓴 뒤 같은 방식으로 다시 읽는다
        print("\n쓰기 시작")
        run_writes(driver, db_name, write_plan(d, all_nodes, db, a.prune, scope_labels, a.drop_extra_props))
        with driver.session(database=db_name, default_access_mode=READ_ACCESS, notifications_min_severity="OFF") as s:
            after_db = read_db(s, a.scope)
            after = CHK.collect(s)
    finally:
        driver.close()
    # ---- 6. 확인: 파일과 같아졌는가, 점검(V0~V25)이 통과하는가. 알려진 값이 바뀌면 경고만 한다
    d2 = diff_graph(nodes, edges, after_db, a.prune_labels, a.drop_extra_props)
    synced = is_synced(d2, a.prune)
    print("\n다시 비교:", "파일과 같음" if synced else "아직 다름")
    if not synced:
        print_diff(d2, after_db, a.show)
    print("적재 전후 차이:", *(CHK.diff(before, after) or ["없음"]), sep="\n  ")
    fails, warns = CHK.judge(after)
    for w in warns:
        print("경고:", w)
    for f in fails:
        print("실패:", f)
    return 5 if fails or not synced else 0


if __name__ == "__main__":
    raise SystemExit(main())
