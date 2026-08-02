"use client";

import { useEffect, useState } from "react";
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

export function SettingsPanel() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<LLMSettings>(loadSettings);
  const [saved, setSaved] = useState(false);
  const [hasSaved, setHasSaved] = useState(false);

  useEffect(() => {
    const s = loadSettings();
    setSettings(s);
    setHasSaved(Boolean(s.llmApiKey || s.tavilyApiKey));
  }, [open]);

  function handleSave() {
    saveSettings(settings);
    setHasSaved(Boolean(settings.llmApiKey || settings.tavilyApiKey));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleClear() {
    if (!confirm("Clear all saved API keys from this browser?")) return;
    clearSettings();
    setSettings({ ...EMPTY });
    setHasSaved(false);
    setSaved(false);
  }

  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-[var(--link)] hover:underline"
      >
        {open ? "Hide settings" : "LLM & API settings"}
        {!open && hasSaved ? " (saved)" : ""}
      </button>
      {open && (
        <div className="mt-4 space-y-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-xs text-[var(--muted)]">
            Fill once → click <strong>Save</strong>. Stored in this browser only
            (localStorage). You can edit anytime; keys are sent to your local API
            when you research.
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
              placeholder="deepseek-v4-pro"
            />
            <p className="mt-1 text-[10px] text-[var(--muted)]">
              研究计划生成会自动避开 deepseek-chat / mini 等弱模型，改用服务端最强模型。
            </p>          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Tavily API Key (optional)</span>
            <input
              type="password"
              value={settings.tavilyApiKey}
              onChange={(e) => setSettings({ ...settings, tavilyApiKey: e.target.value })}
              className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2 font-mono text-xs"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSave}
              className="rounded bg-[var(--ink)] px-4 py-2 text-[var(--surface)]"
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
        </div>
      )}
    </div>
  );
}
