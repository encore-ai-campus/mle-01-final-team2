import { proxyGet } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  return proxyGet(`/api/notices/${encodeURIComponent(decodeURIComponent(id))}`, req, []);
}
