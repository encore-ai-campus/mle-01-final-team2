import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// 로그인 화면용 공개 설정(Supabase 주소·publishable 키). 비밀 키는 API가 내보내지 않는다
export async function GET(req: Request): Promise<Response> {
  return proxyGet("/api/auth/config", req, []);
}
