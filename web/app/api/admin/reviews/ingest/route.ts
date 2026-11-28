import { proxyAdmin } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<Response> {
  return proxyAdmin("/api/admin/reviews/ingest", req);
}
