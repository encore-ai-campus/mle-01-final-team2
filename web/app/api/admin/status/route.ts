import { proxyAdmin } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// M-01 운영 현황(관리자). SCR-06이 쓴다.
export async function GET(req: Request): Promise<Response> {
  return proxyAdmin("/api/admin/status", req);
}
