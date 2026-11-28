import { proxyAdmin } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function GET(req: Request): Promise<Response> {
  return proxyAdmin("/api/admin/reviews", req, ["status", "source", "open_only", "q", "offset", "limit"]);
}
