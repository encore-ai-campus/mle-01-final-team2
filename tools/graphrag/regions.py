"""지역 개념 계층(WITHIN)과 묶음 사전.

- 간선은 하위 -> 상위 방향이다(성동구 -> 서울 -> 전국, H1).
- 행정개편으로 사라진 명칭과 공고가 정의한 권역은 '중간 묶음 개념'으로 둔다(H11, H12).
  묶음 구성원은 data/ref/region_groups.json에 있고 reviewed=false이면 미검수 값이다.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "data" / "ref"
NATIONWIDE = "REGION:NATIONWIDE"
MAX_HOPS = 3  # H2


class RegionGraph:
    def __init__(self, regions_path: Path | None = None, groups_path: Path | None = None):
        regions = json.loads((regions_path or REF / "regions_jscode20260701.json").read_text(encoding="utf-8"))["regions"]
        groups = json.loads((groups_path or REF / "region_groups.json").read_text(encoding="utf-8"))
        self.nodes: dict[str, dict] = {r["region_id"]: dict(r) for r in regions}
        self.parents: dict[str, list[tuple[str, str]]] = {}  # child -> [(parent, basis)]
        for r in regions:
            if r["parent_region_id"]:
                self.parents.setdefault(r["region_id"], []).append((r["parent_region_id"], "MOIS_KIKcd_B"))
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
            self.parents.setdefault(gid, []).append((g["parent"], "GROUP_PARENT"))
            for m in members:
                self.parents.setdefault(m, []).append((gid, "GROUP_MEMBER"))
        self.sido_abbr: dict[str, str] = groups["sido_abbreviations"]
        self.legacy_abbr: dict[str, str] = groups["legacy_abbreviations"]
        self._closure: dict[str, dict[str, int]] = {}

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
        """이름이 정확히 같은 개념(동명 시군구가 여럿일 수 있다)."""
        return [rid for rid, n in self.nodes.items() if n.get("name") == name and (level is None or n.get("level") == level)]
