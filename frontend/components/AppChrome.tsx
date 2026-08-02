"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSettingsUi } from "@/lib/settingsUi";

export function AppChrome() {
  const pathname = usePathname();
  const { openSettings } = useSettingsUi();
  const isHome = pathname === "/";
  const isLogin = pathname === "/login";
  const libraryActive =
    pathname.startsWith("/library") ||
    pathname.startsWith("/history") ||
    pathname.startsWith("/watchlist");

  if (isLogin) return null;

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/92 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2.5">
        <div className="min-w-0">
          {!isHome ? (
            <Link
              href="/"
              className="font-display brand-title text-lg text-[var(--ink)] hover:opacity-90 transition-opacity"
            >
              Search Agent
            </Link>
          ) : (
            <span className="block h-7" aria-hidden />
          )}
        </div>
        <nav className="flex items-center gap-5 text-sm text-[var(--muted)]">
          <Link
            href="/library"
            className={`hover:text-[var(--ink)] transition-colors ${
              libraryActive ? "text-[var(--ink)]" : ""
            }`}
          >
            Library
          </Link>
          <button
            type="button"
            onClick={openSettings}
            className="hover:text-[var(--ink)] transition-colors"
            aria-label="Open settings"
            title="Settings (Ctrl/⌘ +,)"
          >
            <span className="inline-flex h-7 w-7 items-center justify-center rounded border border-transparent hover:border-[var(--border)]">
              <GearIcon />
            </span>
          </button>
        </nav>
      </div>
    </header>
  );
}

function GearIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}
