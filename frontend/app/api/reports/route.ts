import { NextResponse } from "next/server";
import { isSiteAuthorized } from "@/lib/siteAuth";
import { proxyToPersonalApi } from "@/lib/serverApiProxy";

export async function GET(request: Request) {
  if (!(await isSiteAuthorized(request))) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit") || "30";
  return proxyToPersonalApi(
    `/api/reports?limit=${encodeURIComponent(limit)}`,
    request,
  );
}
