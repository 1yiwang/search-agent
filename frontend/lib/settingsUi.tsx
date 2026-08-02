"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type SettingsUiContextValue = {
  open: boolean;
  openSettings: () => void;
  closeSettings: () => void;
  toggleSettings: () => void;
};

const SettingsUiContext = createContext<SettingsUiContextValue | null>(null);

export function SettingsUiProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  const openSettings = useCallback(() => setOpen(true), []);
  const closeSettings = useCallback(() => setOpen(false), []);
  const toggleSettings = useCallback(() => setOpen((v) => !v), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo(
    () => ({ open, openSettings, closeSettings, toggleSettings }),
    [open, openSettings, closeSettings, toggleSettings],
  );

  return (
    <SettingsUiContext.Provider value={value}>{children}</SettingsUiContext.Provider>
  );
}

export function useSettingsUi(): SettingsUiContextValue {
  const ctx = useContext(SettingsUiContext);
  if (!ctx) {
    throw new Error("useSettingsUi must be used within SettingsUiProvider");
  }
  return ctx;
}
