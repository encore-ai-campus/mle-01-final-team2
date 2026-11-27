// 브라우저 → Next /api/eligibility → Python API POST /api/eligibility(규칙 판정, 모델 없음). JSON을 그대로 중계한다.
import { API_BASE_URL, degraded } from "@/lib/upstream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY = 16_000;

export async function POST(req: Request): Promise<Response> {
  const body = await req.text();
  if (body.length > MAX_BODY) return Response.json({ error: { code: "TOO_LARGE", message: "요청이 너무 깁니다." } }, { status: 413 });
  try {
    const r = await fetch(`${API_BASE_URL}/api/eligibility`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      cache: "no-store",
      signal: req.signal,
    });
    return new Response(r.body, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return degraded();
  }
}
