"use client";

import { useEffect, useState } from "react";
import { loadSettings, saveSettings, type LLMSettings } from "@/lib/settings";

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<LLMSettings>(loadSettings);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
  }, [open]);

  function handleSave() {
    saveSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-[var(--link)] hover:underline"
      >
        {open ? "Hide settings" : "LLM & API settings"}
      </button>
      {open && (
        <div className="mt-4 space-y-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-xs text-[var(--muted)]">
            Stored in your browser only. Required when personal API is running.
          </p>
          <label className="block">
            <span className="text-[var(--muted)]">LLM API Key</span>
            <input
              type="password"
              value={settings.llmApiKey}
              onChange={(e) => setSettings({ ...settings, llmApiKey: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2 font-mono text-xs"
              placeholder="sk-..."
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Base URL</span>
            <input
              type="text"
              value={settings.llmBaseUrl}
              onChange={(e) => setSettings({ ...settings, llmBaseUrl: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2 font-mono text-xs"
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Model</span>
            <input
              type="text"
              value={settings.llmModel}
              onChange={(e) => setSettings({ ...settings, llmModel: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2 font-mono text-xs"
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Tavily API Key (optional)</span>
            <input
              type="password"
              value={settings.tavilyApiKey}
              onChange={(e) => setSettings({ ...settings, tavilyApiKey: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2 font-mono text-xs"
            />
          </label>
          <button
            type="button"
            onClick={handleSave}
            className="rounded bg-[var(--ink)] px-4 py-2 text-[var(--surface)]"
          >
            {saved ? "Saved" : "Save settings"}
          </button>
        </div>
      )}
    </div>
  );
}
