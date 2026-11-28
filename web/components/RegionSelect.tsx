"use client";
// 사업장 소재지 선택. 목록은 GET /api/concepts?scheme=region(그래프가 없으면 내장 지역 사전).
import { useEffect, useState } from "react";

type Region = { id: string; name: string; full_name: string | null; level: string | null };

export default function RegionSelect({ value, onChange }: { value: string; onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void }) {
  const [regions, setRegions] = useState<Region[]>([]);
  const [source, setSource] = useState("");

  useEffect(() => {
    fetch("/api/concepts?scheme=region")
      .then((r) => r.json())
      .then((d) => {
        setRegions((d.items ?? []).filter((r: Region) => r.level !== "GROUP"));
        setSource(d.source ?? "");
      })
      .catch(() => setSource("unavailable"));
  }, []);

  return (
    <label>
      사업장 소재지 {source && <span>({source === "neo4j" ? "그래프" : source === "local" ? "내장 사전" : "불러오기 실패"})</span>}
      <select value={value} onChange={onChange}>
        <option value="">모름</option>
        {regions.map((r) => (
          <option key={r.id} value={r.id}>
            {r.full_name ?? r.name}
          </option>
        ))}
      </select>
    </label>
  );
}
