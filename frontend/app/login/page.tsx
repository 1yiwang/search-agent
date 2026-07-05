"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setApiToken } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Login failed");
        return;
      }
      if (data.token) {
        setApiToken(data.token);
      }
      const next = searchParams.get("next") || "/";
      router.replace(next);
    } catch {
      setError("Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Site password"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
        autoFocus
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={loading || !password}
        className="w-full rounded-lg bg-[var(--accent)] py-3 font-semibold text-[#1a1408] disabled:opacity-40"
      >
        {loading ? "…" : "Enter"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <h1 className="font-display text-3xl text-[var(--ink)] mb-2">Search Agent</h1>
      <p className="text-sm text-[var(--muted)] mb-8">Personal research — enter site password</p>
      <Suspense fallback={<p className="text-sm text-[var(--muted)]">Loading…</p>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
