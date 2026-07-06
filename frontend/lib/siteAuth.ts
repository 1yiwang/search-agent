import { cookies } from "next/headers";

export const SITE_AUTH_COOKIE = "sa_site_auth";

/** Site gate passed via httpOnly cookie (login) or client sessionStorage Bearer token. */
export async function isSiteAuthorized(request: Request): Promise<boolean> {
  if (!process.env.SITE_PASSWORD) return true;

  const cookieStore = await cookies();
  if (cookieStore.get(SITE_AUTH_COOKIE)?.value === "1") return true;

  const auth = request.headers.get("authorization") ?? "";
  return auth.startsWith("Bearer ") && auth.length > "Bearer ".length + 8;
}
