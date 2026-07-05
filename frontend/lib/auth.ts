const TOKEN_KEY = "search-agent-api-token";

export function getApiToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setApiToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearApiToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
