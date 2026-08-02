"use client";

import type { ReactNode } from "react";
import { AppChrome } from "@/components/AppChrome";
import { OfflineBanner } from "@/components/ApiStatus";
import { SettingsSheet } from "@/components/SettingsPanel";
import { SettingsUiProvider } from "@/lib/settingsUi";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <SettingsUiProvider>
      <OfflineBanner />
      <AppChrome />
      {children}
      <SettingsSheet />
    </SettingsUiProvider>
  );
}
