"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";

/** Full-width banner only when personal API is offline. Healthy = silent. */
export function OfflineBanner() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch(`${getApiBase()}/api/health`, { cache: "no-store" });
        if (!cancelled) setOnline(res.ok);
      } catch {
        if (!cancelled) setOnline(false);
      }
    }
    check();
    const id = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (online !== false) return null;

  return (
    <div
      className="border-b border-[var(--signal)]/30 bg-[var(--accent)]/35 px-4 py-2 text-center text-xs text-[var(--ink)]"
      role="status"
    >
      API offline — run{" "}
      <code className="font-mono text-[11px]">.\scripts\start-personal.ps1</code> on your PC to
      research.
    </div>
  );
}

/** @deprecated Prefer OfflineBanner in AppShell. Healthy state renders nothing. */
export function ApiStatus() {
  return <OfflineBanner />;
}
