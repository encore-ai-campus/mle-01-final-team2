import { proxyAdmin } from "@/lib/upstream";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };
const path = async ({ params }: Ctx) => `/api/admin/reviews/${encodeURIComponent(decodeURIComponent((await params).id))}`;

export async function GET(req: Request, ctx: Ctx): Promise<Response> {
  return proxyAdmin(await path(ctx), req);
}

export async function PUT(req: Request, ctx: Ctx): Promise<Response> {
  return proxyAdmin(await path(ctx), req);
}
