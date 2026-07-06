import { createHmac } from "crypto";
import { NextResponse } from "next/server";

const TTL = parseInt(process.env.API_TOKEN_TTL_SECONDS || "86400", 10);

function issueToken(secret: string): string {
  const exp = Math.floor(Date.now() / 1000) + TTL;
  const payload = String(exp);
  const sig = createHmac("sha256", secret).update(payload).digest("hex");
  return `${payload}.${sig}`;
}

function personalApiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    "http://localhost:8000"
  ).replace(/\/$/, "");
}

/** Server-side proxy to the personal FastAPI (mint API token from API_AUTH_SECRET). */
export async function proxyToPersonalApi(
  path: string,
  request?: Request,
): Promise<NextResponse> {
  const clientAuth = request?.headers.get("authorization") ?? "";
  const bearer = clientAuth.startsWith("Bearer ")
    ? clientAuth.slice("Bearer ".length).trim()
    : "";

  const apiSecret = process.env.API_AUTH_SECRET;
  if (!apiSecret && !bearer) {
    return NextResponse.json(
      { error: "API_AUTH_SECRET not configured on server" },
      { status: 503 },
    );
  }

  const token = bearer || issueToken(apiSecret!);
  const url = `${personalApiBase()}${path}`;
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        error:
          "Personal API offline. Start backend (python main.py) and tunnel (scripts/start-tunnel.ps1).",
      },
      { status: 503 },
    );
  }
}
