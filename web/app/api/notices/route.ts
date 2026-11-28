import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export function GET(req: Request): Promise<Response> {
  return proxyGet("/api/notices", req, ["q", "source", "include_closed", "page", "size"]);
}
