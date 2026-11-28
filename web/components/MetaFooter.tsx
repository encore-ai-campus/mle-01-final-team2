"use client";
// 바닥글: 면책 문구와 출처별 수집 시각(S-01 /api/meta). API에 닿지 않으면 화면에 박힌 문구만 보인다.
import { useEffect, useState } from "react";

import { DISCLAIMER, SOURCE } from "@/lib/labels";

type Meta = { data_as_of: Record<string, string>; stale: boolean; disclaimer: string };

const SOURCE_ALL: Record<string, string> = { ...SOURCE, G2B: "나라장터" };

export default function MetaFooter() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    fetch("/api/meta", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);
  const asOf = Object.entries(meta?.data_as_of ?? {});
  return (
    <footer className="site-foot" role="contentinfo">
      <div>※ {meta?.disclaimer ?? DISCLAIMER} 선정을 보장하지 않습니다. 교육용 프로젝트(팀 근거 it).</div>
      {asOf.length > 0 && (
        <div className="data-asof">
          수집 기준: {asOf.map(([s, t]) => `${SOURCE_ALL[s] ?? s} ${t.slice(0, 10)}`).join(" · ")}
          {meta?.stale && <strong className="stale"> · 수집이 늦어지고 있습니다. 최신 공고와 다를 수 있습니다.</strong>}
        </div>
      )}
    </footer>
  );
}
