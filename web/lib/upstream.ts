// Next 서버(Route Handler)에서만 쓴다. Python API 주소는 브라우저로 내보내지 않는다(기초 설계서 §8 데이터 접근 원칙).
export const API_BASE_URL = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export function degraded(message = "API 서버에 닿지 않습니다.", status = 502): Response {
  return Response.json({ error: { code: "SERVICE_DEGRADED", message } }, { status });
}

/** 브라우저가 보낸 로그인 토큰만 넘긴다(다른 헤더·쿠키는 넘기지 않는다). */
export function authHeader(req: Request): Record<string, string> {
  const auth = req.headers.get("authorization");
  return auth ? { authorization: auth } : {};
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
    // 로그인 토큰이 있으면 그대로 넘긴다(공고 상세 등 로그인 필요 API). 다른 헤더는 넘기지 않는다
    const auth = req.headers.get("authorization");
    const r = await fetch(`${API_BASE_URL}${path}${qs.size ? `?${qs}` : ""}`, {
      cache: "no-store",
      signal: req.signal,
      headers: auth ? { authorization: auth } : undefined,
    });
    return new Response(r.body, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return degraded();
  }
}

/**
 * 관리자 API 중계(검수 큐). 메서드·본문을 그대로 넘긴다.
 * 로컬 개발(DEV_ADMIN=1)에서만 `x-dev-role: admin`을 붙인다. API는 APP_ENV=local + APP_DEV_AUTH=1일 때만 이 헤더를 본다.
 * 관리자 로그인(A-01)이 붙으면 이 헤더 대신 토큰만 넘긴다.
 */
export async function proxyAdmin(path: string, req: Request, allow: string[] = []): Promise<Response> {
  const src = new URL(req.url).searchParams;
  const qs = new URLSearchParams();
  for (const k of allow) {
    const v = src.get(k);
    if (v) qs.set(k, v);
  }
  const headers: Record<string, string> = {};
  const auth = req.headers.get("authorization");
  if (auth) headers.authorization = auth;
  if (process.env.DEV_ADMIN === "1") headers["x-dev-role"] = "admin";
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  if (hasBody) headers["content-type"] = "application/json";
  try {
    const r = await fetch(`${API_BASE_URL}${path}${qs.size ? `?${qs}` : ""}`, {
      method: req.method,
      cache: "no-store",
      signal: req.signal,
      headers,
      body: hasBody ? await req.text() : undefined,
    });
    return new Response(r.body, { status: r.status, headers: { "content-type": r.headers.get("content-type") ?? "application/json" } });
  } catch {
    return degraded();
  }
}
