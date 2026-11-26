import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export function GET(req: Request): Promise<Response> {
  return proxyGet("/api/concepts", req, ["scheme"]);
}
