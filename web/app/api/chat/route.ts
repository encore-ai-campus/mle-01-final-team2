// 브라우저 → Next /api/chat → Python API POST /api/chat(SSE). 응답 본문을 버퍼링 없이 그대로 흘려보낸다.
import { API_BASE_URL, authHeader, degraded } from "@/lib/upstream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY = 16_000;

export async function POST(req: Request): Promise<Response> {
  const body = await req.text();
  if (body.length > MAX_BODY) return Response.json({ error: { code: "TOO_LARGE", message: "요청이 너무 깁니다." } }, { status: 413 });
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { ...authHeader(req), "content-type": "application/json", accept: "text/event-stream" },
      body,
      cache: "no-store",
      signal: req.signal, // 사용자가 화면을 떠나면 API 호출도 끊는다
    });
  } catch {
    return degraded();
  }
  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }
  return new Response(upstream.body, {
    headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-cache, no-transform", "x-accel-buffering": "no" },
  });
}
