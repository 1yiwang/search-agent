import type { Metadata } from "next";
import { headers } from "next/headers";
import { Fraunces, Schibsted_Grotesk } from "next/font/google";
import { isPrivateAppHost } from "@/lib/hosts";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-display",
});

const body = Schibsted_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
});

export async function generateMetadata(): Promise<Metadata> {
  const host = (await headers()).get("host") || "";
  const privateSite = isPrivateAppHost(host);

  return {
    title: "Search Agent",
    description: "Controllable, verifiable deep research agent",
    ...(privateSite
      ? { robots: { index: false, follow: false, nocache: true } }
      : {}),
  };
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-screen antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
