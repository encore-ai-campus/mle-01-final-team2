// 운영 화면용 상태 확인 중계. 허용한 종류만 넘긴다(임의 경로 중계 금지).
import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

const PATHS: Record<string, string> = { app: "/health", llm: "/health/llm", graph: "/health/graph", index: "/health/index" };

export async function GET(req: Request, { params }: { params: Promise<{ kind: string }> }): Promise<Response> {
  const { kind } = await params;
  const path = PATHS[kind];
  if (!path) return Response.json({ error: { code: "NOT_FOUND", message: "알 수 없는 상태 항목입니다." } }, { status: 404 });
  return proxyGet(path, req, []);
}
