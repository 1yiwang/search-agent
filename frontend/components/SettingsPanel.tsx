"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { useSettingsUi } from "@/lib/settingsUi";
import {
  clearSettings,
  loadSettings,
  saveSettings,
  type LLMSettings,
} from "@/lib/settings";

const EMPTY: LLMSettings = {
  llmApiKey: "",
  llmBaseUrl: "https://api.deepseek.com",
  llmModel: "deepseek-v4-pro",
  tavilyApiKey: "",
};

/** Right-side settings sheet — opened via AppChrome / useSettingsUi. */
export function SettingsSheet() {
  const { open, closeSettings } = useSettingsUi();
  const [settings, setSettings] = useState<LLMSettings>(EMPTY);
  const [saved, setSaved] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    if (!open) return;
    setSettings(loadSettings());
    setSaved(false);
    let cancelled = false;
    fetch(`${getApiBase()}/api/health`, { cache: "no-store" })
      .then((res) => {
        if (!cancelled) setApiOnline(res.ok);
      })
      .catch(() => {
        if (!cancelled) setApiOnline(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  function handleSave() {
    saveSettings(settings);
    setSaved(true);
    window.dispatchEvent(new Event("search-agent-settings-saved"));
    setTimeout(() => setSaved(false), 2000);
  }

  function handleClear() {
    if (!confirm("Clear all saved API keys from this browser?")) return;
    clearSettings();
    setSettings({ ...EMPTY });
    setSaved(false);
  }

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" role="dialog" aria-modal="true">
      <button
        type="button"
        className="absolute inset-0 bg-black/45"
        aria-label="Close settings"
        onClick={closeSettings}
      />
      <aside className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-none">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <h2 className="font-display text-xl text-[var(--ink)]">Settings</h2>
          <button
            type="button"
            onClick={closeSettings}
            className="text-sm text-[var(--muted)] hover:text-[var(--ink)]"
          >
            Close
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 text-sm">
          <p className="text-xs text-[var(--muted)]">
            Stored in this browser only. Keys are sent to your personal API when you research.
            Shortcut: Ctrl/⌘ + ,
          </p>
          <p
            className={`text-xs ${
              apiOnline === null
                ? "text-[var(--muted)]"
                : apiOnline
                  ? "text-[var(--verify)]"
                  : "text-amber-700"
            }`}
          >
            {apiOnline === null
              ? "Checking API…"
              : apiOnline
                ? "● API online"
                : "○ API offline — run .\\scripts\\start-personal.ps1"}
          </p>
          <label className="block">
            <span className="text-[var(--muted)]">LLM API Key</span>
            <input
              type="password"
              value={settings.llmApiKey}
              onChange={(e) => setSettings({ ...settings, llmApiKey: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs text-[var(--ink)]"
              placeholder="sk-..."
              autoComplete="off"
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Base URL</span>
            <input
              type="text"
              value={settings.llmBaseUrl}
              onChange={(e) => setSettings({ ...settings, llmBaseUrl: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs text-[var(--ink)]"
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Model</span>
            <input
              type="text"
              value={settings.llmModel}
              onChange={(e) => setSettings({ ...settings, llmModel: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs text-[var(--ink)]"
              placeholder="deepseek-v4-pro"
            />
            <p className="mt-1 text-[10px] text-[var(--muted)]">
              Research-plan writing upgrades weak models (chat / mini) to the server strongest model.
            </p>
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Tavily API Key (optional)</span>
            <input
              type="password"
              value={settings.tavilyApiKey}
              onChange={(e) => setSettings({ ...settings, tavilyApiKey: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs text-[var(--ink)]"
              autoComplete="off"
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2 border-t border-[var(--border)] px-5 py-4">
          <button
            type="button"
            onClick={handleSave}
            className="rounded bg-[var(--ink)] px-4 py-2 text-[var(--bg)]"
          >
            {saved ? "Saved ✓" : "Save settings"}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="rounded border border-[var(--border)] px-4 py-2 text-[var(--muted)] hover:text-[var(--ink)]"
          >
            Clear all keys
          </button>
        </div>
      </aside>
    </div>
  );
}

/** @deprecated Use SettingsSheet via AppShell; kept as no-op for any stray imports. */
export function SettingsPanel() {
  return null;
}
