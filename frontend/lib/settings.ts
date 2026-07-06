export interface LLMSettings {
  llmApiKey: string;
  llmBaseUrl: string;
  llmModel: string;
  tavilyApiKey: string;
}

const STORAGE_KEY = "search-agent-settings";

const DEFAULTS: LLMSettings = {
  llmApiKey: "",
  llmBaseUrl: "https://api.deepseek.com",
  llmModel: "deepseek-chat",
  tavilyApiKey: "",
};

export function loadSettings(): LLMSettings {
  if (typeof window === "undefined") return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings: LLMSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function clearSettings(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function settingsHeaders(settings: LLMSettings): Record<string, string> {
  const h: Record<string, string> = {};
  if (settings.llmApiKey) h["X-LLM-API-Key"] = settings.llmApiKey;
  if (settings.llmBaseUrl) h["X-LLM-Base-URL"] = settings.llmBaseUrl;
  if (settings.llmModel) h["X-LLM-Model"] = settings.llmModel;
  if (settings.tavilyApiKey) h["X-Tavily-API-Key"] = settings.tavilyApiKey;
  return h;
}
