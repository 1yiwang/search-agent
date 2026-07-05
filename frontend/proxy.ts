import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const COOKIE_NAME = "sa_site_auth";

function isDemoHost(host: string): boolean {
  return host.startsWith("search-demo.") || host.includes("search-demo-");
}

function isProtectedAppHost(host: string): boolean {
  if (isDemoHost(host)) return false;
  if (host.includes("localhost") || host.startsWith("127.0.0.1")) return false;
  return host.includes("search.") || host.includes("search-agent");
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

  if (!isProtectedAppHost(host)) {
    return NextResponse.next();
  }

  const publicPaths = ["/login", "/api/auth/login", "/demo"];
  if (publicPaths.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  if (!process.env.SITE_PASSWORD) {
    return NextResponse.next();
  }

  const authed = request.cookies.get(COOKIE_NAME)?.value === "1";
  if (!authed) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
