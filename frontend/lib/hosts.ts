/** Host-based routing for private app vs public demo (shared by proxy, robots, metadata). */

export function isDemoHost(host: string): boolean {
  return host.startsWith("search-demo.") || host.includes("search-demo-");
}

export function isPrivateAppHost(host: string): boolean {
  if (isDemoHost(host)) return false;
  if (host.includes("localhost") || host.startsWith("127.0.0.1")) return false;
  return host.includes("search.") || host.includes("search-agent");
}
