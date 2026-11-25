"""지역 개념 계층과 묶음 사전.

- 간선은 하위 -> 상위 방향이다(성동구 -> 서울 -> 전국, H1).
- 행정 계층은 `WITHIN`(N:1, 일반구 -> 시 -> 시도 -> 전국)만 쓴다. 묶음·권역 소속은 `MEMBER_OF`(N:M, 구성 지역 -> 묶음)로 나눈다(H13).
  행정개편으로 사라진 명칭과 공고가 정의한 권역은 '중간 묶음 개념'으로 둔다(H11, H12).
  묶음 구성원은 data/ref/region_groups.json에 있고 reviewed=false이면 미검수 값이다.
- 지역 코드표는 data/사전/지역_코드표.csv(318행: 팀 234 + 누락 12 + 일반구 39 + 폐지 33)를 쓴다. 파일의 ID는 `KR:REGION:{코드}`이므로
  팀 형식 `REGION:{코드}`로 바꿔 읽는다. 폐지 지역은 계층·이름 조회에 쓰지 않고 `retired`와 `successors`(SUCCEEDED_BY 후보)로만 둔다(H14).
- 예전 팀 코드표(data/ref/regions_jscode20260701.json, 234개)도 경로를 직접 주면 읽을 수 있다.
"""
from __future__ import annotations

import csv
import json
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "data" / "ref"
TABLE = REPO / "data" / "사전" / "지역_코드표.csv"
NATIONWIDE = "REGION:NATIONWIDE"
MAX_HOPS = 3  # H2. WITHIN과 MEMBER_OF를 합쳐 센다
ADMIN, MEMBER = "WITHIN", "MEMBER_OF"


def _norm_id(value: str | None) -> str:
    value = (value or "").strip()
    value = value[3:] if value.startswith("KR:") else value
    return NATIONWIDE if value == "NATIONWIDE" else value  # 표의 전국 행은 `KR:NATIONWIDE`


def _read_table(path: Path) -> tuple[list[dict], list[dict]]:
    """CSV 코드표 -> (존재하는 지역, 폐지 지역). ID는 팀 형식으로 바꾼다."""
    active, retired = [], []
    for row in csv.DictReader(path.open(encoding="utf-8-sig")):
        rec = {"region_id": _norm_id(row["region_id"]), "region_code": row["region_code"] or None, "level": row["level"],
               "name": row["name"], "parent_region_id": _norm_id(row["parent_region_id"]) or None,
               "code_source": row["code_source"], "code_version": row["code_version"], "status": row["status"] or "존재"}
        if row.get("full_name"):
            rec["full_name"] = row["full_name"]
        if row.get("note"):
            rec["note"] = row["note"]
        if rec["level"] == "SIDO" and not rec["parent_region_id"] and rec["status"] != "폐지":
            rec["parent_region_id"] = NATIONWIDE  # 시도의 상위는 전국(표에는 비어 있음)
        if rec["status"] == "폐지":
            # 후계 값은 코드 목록이거나 `MERGED_INTO:{코드}`(통합)이다
            rec["successor_ids"] = [f"REGION:{c.strip().removeprefix('MERGED_INTO:')}" for c in (row.get("successor_ids") or "").split(";") if c.strip()]
            retired.append(rec)
        else:
            active.append(rec)
    return active, retired


class RegionGraph:
    def __init__(self, regions_path: Path | None = None, groups_path: Path | None = None):
        path = Path(regions_path) if regions_path else TABLE
        if path.suffix == ".json":
            regions, retired = json.loads(path.read_text(encoding="utf-8"))["regions"], []
        else:
            regions, retired = _read_table(path)
        groups = json.loads((groups_path or REF / "region_groups.json").read_text(encoding="utf-8"))
        self.nodes: dict[str, dict] = {r["region_id"]: dict(r) for r in regions}
        self.retired: dict[str, dict] = {r["region_id"]: r for r in retired}
        self.successors: dict[str, list[str]] = {rid: r["successor_ids"] for rid, r in self.retired.items() if r["successor_ids"]}
        self.parents: dict[str, list[tuple[str, str]]] = {}  # child -> [(parent, relation)] relation은 WITHIN 또는 MEMBER_OF
        self.edge_basis: dict[tuple[str, str, str], str] = {}  # (child, parent, relation) -> 근거
        for r in regions:
            if r["parent_region_id"]:
                self._link(r["region_id"], r["parent_region_id"], ADMIN, r["code_source"])
        self.groups = {g["group_id"]: g for g in groups["groups"]}
        children_of_parent: dict[str, list[str]] = {}
        for rid, r in self.nodes.items():
            if r["parent_region_id"]:
                children_of_parent.setdefault(r["parent_region_id"], []).append(rid)
        for gid, g in self.groups.items():
            members = g["members"]
            if members == "__REST__":
                taken = {m for o in self.groups.values() if o["members"] != "__REST__" and o["parent"] == g["parent"] for m in o["members"]}
                members = [c for c in children_of_parent.get(g["parent"], []) if c not in taken]
                g["members"] = members
            self.nodes[gid] = {"region_id": gid, "level": "GROUP", "name": g["label"], "reviewed": g["reviewed"], "kind": g["kind"]}
            self._link(gid, g["parent"], MEMBER, "GROUP_PARENT")
            for m in members:
                self._link(m, gid, MEMBER, "GROUP_MEMBER")
        self.sido_abbr: dict[str, str] = groups["sido_abbreviations"]
        self.legacy_abbr: dict[str, str] = groups["legacy_abbreviations"]
        self._closure: dict[str, dict[str, int]] = {}

    def _link(self, child: str, parent: str, relation: str, basis: str) -> None:
        self.parents.setdefault(child, []).append((parent, relation))
        self.edge_basis[(child, parent, relation)] = basis

    def admin_parents(self, rid: str) -> list[str]:
        """행정 상위(WITHIN). 하나여야 한다(점검 V8)."""
        return [p for p, rel in self.parents.get(rid, []) if rel == ADMIN]

    def ancestors(self, rid: str, max_hops: int = MAX_HOPS) -> dict[str, int]:
        """자기 자신(0 hop)과 위로 max_hops 이내의 모든 조상 -> 최소 hop 수."""
        key = f"{rid}|{max_hops}"
        if key in self._closure:
            return self._closure[key]
        seen = {rid: 0}
        q = deque([rid])
        while q:
            cur = q.popleft()
            if seen[cur] >= max_hops:
                continue
            for p, _ in self.parents.get(cur, []):
                if p not in seen:
                    seen[p] = seen[cur] + 1
                    q.append(p)
        self._closure[key] = seen
        return seen

    def path(self, rid: str, target: str, max_hops: int = MAX_HOPS) -> list[str] | None:
        """rid에서 target까지의 최단 경로(이름 목록). 없으면 None."""
        prev = {rid: None}
        q = deque([(rid, 0)])
        while q:
            cur, h = q.popleft()
            if cur == target:
                out = []
                while cur is not None:
                    out.append(self.nodes[cur]["name"] if cur in self.nodes else cur)
                    cur = prev[cur]
                return out[::-1]
            if h >= max_hops:
                continue
            for p, _ in self.parents.get(cur, []):
                if p not in prev:
                    prev[p] = cur
                    q.append((p, h + 1))
        return None

    def resolve_abbr(self, raw: str | None) -> str | None:
        """K-Startup 지역 약칭 -> 개념 ID. 모르면 None(판정에 쓰지 않는다)."""
        if not raw:
            return None
        raw = raw.strip()
        return self.sido_abbr.get(raw) or self.legacy_abbr.get(raw)

    def is_unreviewed(self, rid: str) -> bool:
        n = self.nodes.get(rid)
        return bool(n and n.get("level") == "GROUP" and not n.get("reviewed"))

    def name(self, rid: str) -> str:
        return self.nodes.get(rid, {}).get("name", rid)

    def find_by_name(self, name: str, level: str | None = None) -> list[str]:
        """이름이 정확히 같은 개념(동명 시군구가 여럿일 수 있다). 폐지 지역은 찾지 않는다."""
        return [rid for rid, n in self.nodes.items() if n.get("name") == name and (level is None or n.get("level") == level)]
