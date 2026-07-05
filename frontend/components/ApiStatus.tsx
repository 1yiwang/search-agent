"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export function ApiStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const base = API_BASE || "";
        const res = await fetch(`${base}/api/health`, { cache: "no-store" });
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

  if (online === null) return null;

  return (
    <p
      className={`text-xs ${online ? "text-[var(--verify)]" : "text-amber-700"}`}
      title={online ? "Personal API reachable" : "Run scripts/start-personal.ps1 on your PC"}
    >
      {online ? "● API online" : "○ API offline — start personal API to research"}
    </p>
  );
}
