import { createHmac } from "crypto";
import { NextResponse } from "next/server";

const COOKIE_NAME = "sa_site_auth";
const TTL = parseInt(process.env.API_TOKEN_TTL_SECONDS || "86400", 10);

function issueToken(secret: string): string {
  const exp = Math.floor(Date.now() / 1000) + TTL;
  const payload = String(exp);
  const sig = createHmac("sha256", secret).update(payload).digest("hex");
  return `${payload}.${sig}`;
}

export async function POST(request: Request) {
  const sitePassword = process.env.SITE_PASSWORD;
  const apiSecret = process.env.API_AUTH_SECRET;

  if (!sitePassword) {
    return NextResponse.json(
      { error: "SITE_PASSWORD not configured on server" },
      { status: 503 },
    );
  }

  const body = await request.json();
  const password = String(body.password || "");

  if (password !== sitePassword) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const response = NextResponse.json({
    ok: true,
    token: apiSecret ? issueToken(apiSecret) : null,
    expires_in_seconds: TTL,
  });

  response.cookies.set(COOKIE_NAME, "1", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: TTL,
    path: "/",
  });

  return response;
}
