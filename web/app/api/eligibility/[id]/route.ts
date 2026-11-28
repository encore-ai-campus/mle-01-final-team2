// 브라우저 → Next /api/eligibility/{id} → Python API POST /api/eligibility/{id}(E-02 조건별 검증표, 모델 없음).
import { API_BASE_URL, authHeader, degraded } from "@/lib/upstream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY = 16_000;

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  const body = await req.text();
  if (body.length > MAX_BODY) return Response.json({ error: { code: "TOO_LARGE", message: "요청이 너무 깁니다." } }, { status: 413 });
  try {
    const r = await fetch(`${API_BASE_URL}/api/eligibility/${encodeURIComponent(decodeURIComponent(id))}`, {
      method: "POST",
      headers: { ...authHeader(req), "content-type": "application/json" },
      body,
      cache: "no-store",
      signal: req.signal,
    });
    return new Response(r.body, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return degraded();
  }
}
