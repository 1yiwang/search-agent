import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isDemoHost, isPrivateAppHost } from "@/lib/hosts";

const COOKIE_NAME = "sa_site_auth";

function withRobotsTag(response: NextResponse, host: string): NextResponse {
  if (isPrivateAppHost(host)) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}

export function proxy(request: NextRequest) {
  const host = request.headers.get("host") || "";
  const { pathname } = request.nextUrl;

  if (isDemoHost(host)) {
    if (pathname === "/") {
      return NextResponse.redirect(new URL("/demo", request.url));
    }
    if (!pathname.startsWith("/demo") && !pathname.startsWith("/_next")) {
      return NextResponse.redirect(new URL("/demo", request.url));
    }
    return NextResponse.next();
  }

  if (!isPrivateAppHost(host)) {
    return NextResponse.next();
  }

  const publicPaths = ["/login", "/api/auth/login", "/demo", "/robots.txt"];
  if (publicPaths.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return withRobotsTag(NextResponse.next(), host);
  }

  if (!process.env.SITE_PASSWORD) {
    return withRobotsTag(NextResponse.next(), host);
  }

  const authed = request.cookies.get(COOKIE_NAME)?.value === "1";
  if (!authed) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return withRobotsTag(NextResponse.redirect(login), host);
  }

  return withRobotsTag(NextResponse.next(), host);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
