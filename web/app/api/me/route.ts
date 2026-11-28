import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// A-01: 로그인 사용자·역할. 토큰(Authorization)을 그대로 넘긴다
export async function GET(req: Request): Promise<Response> {
  return proxyGet("/api/me", req, []);
}
