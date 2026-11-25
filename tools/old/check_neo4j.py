#!/usr/bin/env python
"""Neo4j Aura 접속 점검 (읽기 전용).

프로젝트 루트의 .env 에서 접속 정보를 읽어 연결을 확인하고, 서버 버전·노드/관계 수·인덱스·APOC·벡터/전문 프로시저를 출력한다.
데이터를 쓰지 않고, 비밀번호는 출력하지 않는다.

필요한 .env 키: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, (선택) NEO4J_DATABASE

사용법:
    pip install -r tools/requirements.txt
    python tools/check_neo4j.py

참고: Windows·일부 환경의 인증서 저장소에는 Aura 루트 인증서가 없는 경우가 있어,
      검증을 끄지 않고 certifi CA 로 검증한다(neo4j+s:// 스킴).
종료 코드: 0 = 성공, 1 = 실패
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> int:
    env = load_env(ROOT / ".env")
    uri = env.get("NEO4J_URI")
    user = env.get("NEO4J_USERNAME")
    password = env.get("NEO4J_PASSWORD")
    database = env.get("NEO4J_DATABASE") or None
    missing = [k for k, v in (("NEO4J_URI", uri), ("NEO4J_USERNAME", user), ("NEO4J_PASSWORD", password)) if not v]
    if missing:
        print(f"[실패] .env 에 없는 키: {', '.join(missing)}")
        return 1

    try:
        import certifi
        import neo4j
    except ImportError:
        print("[실패] neo4j, certifi 가 없습니다: pip install -r tools/requirements.txt")
        return 1

    print(f"URI 스킴: {uri.split('://')[0]} | 데이터베이스: {database or '(기본)'} | 드라이버: neo4j {neo4j.__version__}")

    kwargs: dict = {}
    connect_uri = uri
    if uri.startswith(("neo4j+s://", "bolt+s://")):
        connect_uri = uri.replace("neo4j+s://", "neo4j://").replace("bolt+s://", "bolt://")
        kwargs = dict(encrypted=True, trusted_certificates=neo4j.TrustCustomCAs(certifi.where()))

    start = time.time()
    try:
        with neo4j.GraphDatabase.driver(connect_uri, auth=(user, password), **kwargs) as driver:
            driver.verify_connectivity()
            print(f"[성공] 연결 확인 ({time.time() - start:.1f}초)")
            with driver.session(database=database, default_access_mode=neo4j.READ_ACCESS) as session:
                print("RETURN 1 ->", session.run("RETURN 1 AS ok").single()["ok"])
                comp = next(iter(session.run(
                    "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS v, edition")))
                print(f"서버: {comp['name']} {comp['v']} ({comp['edition']})")
                nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                print(f"노드: {nodes:,} | 관계: {rels:,}")
                labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label")]
                print("레이블:", labels or "(없음)")
                indexes = [(r["name"], r["type"], r["state"]) for r in session.run(
                    "SHOW INDEXES YIELD name, type, state RETURN name, type, state")]
                print("인덱스:", indexes)
                for name, query in (("APOC", "RETURN apoc.version() AS v"), ("GDS", "RETURN gds.version() AS v")):
                    try:
                        print(f"{name}:", session.run(query).single()["v"])
                    except Exception as exc:  # noqa: BLE001 - 사용 불가도 정보다
                        print(f"{name}: 사용 불가 ({str(exc).splitlines()[0][:100]})")
                procs = [r["name"] for r in session.run(
                    "SHOW PROCEDURES YIELD name "
                    "WHERE name STARTS WITH 'db.index.vector' OR name STARTS WITH 'db.index.fulltext' RETURN name")]
                print("벡터·전문 프로시저:", len(procs), "개", "(있음)" if procs else "(없음)")
        return 0
    except Exception as exc:  # noqa: BLE001
        message = str(exc).replace(password, "<hidden>")
        print(f"[실패] {type(exc).__name__}: {message[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
