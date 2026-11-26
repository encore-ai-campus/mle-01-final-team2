import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export function GET(req: Request): Promise<Response> {
  return proxyGet("/api/graph/path", req, ["notice_id", "region"]);
}
