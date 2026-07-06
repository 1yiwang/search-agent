import { NextResponse } from "next/server";
import { isSiteAuthorized } from "@/lib/siteAuth";
import { proxyToPersonalApi } from "@/lib/serverApiProxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ slug: string }> },
) {
  if (!(await isSiteAuthorized(request))) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const { slug } = await context.params;
  return proxyToPersonalApi(
    `/api/research/${encodeURIComponent(slug)}`,
    request,
  );
}
