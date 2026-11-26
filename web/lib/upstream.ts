// Next 서버(Route Handler)에서만 쓴다. Python API 주소는 브라우저로 내보내지 않는다(기초 설계서 §8 데이터 접근 원칙).
export const API_BASE_URL = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export function degraded(message = "API 서버에 닿지 않습니다.", status = 502): Response {
  return Response.json({ error: { code: "SERVICE_DEGRADED", message } }, { status });
}

/** 허용한 쿼리 파라미터만 넘겨 GET을 중계한다. */
export async function proxyGet(path: string, req: Request, allow: string[]): Promise<Response> {
  const src = new URL(req.url).searchParams;
  const qs = new URLSearchParams();
  for (const k of allow) {
    const v = src.get(k);
    if (v) qs.set(k, v);
  }
  try {
    const r = await fetch(`${API_BASE_URL}${path}${qs.size ? `?${qs}` : ""}`, { cache: "no-store", signal: req.signal });
    return new Response(r.body, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return degraded();
  }
}
