import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// S-01 공개 메타(수집 시각·버전·면책 문구·구간표). 로그인 없이 연다
export async function GET(req: Request): Promise<Response> {
  return proxyGet("/api/meta", req, []);
}
