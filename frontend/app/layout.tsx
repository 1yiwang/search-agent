import type { Metadata } from "next";
import { headers } from "next/headers";
import { DM_Sans, Instrument_Serif } from "next/font/google";
import { isPrivateAppHost } from "@/lib/hosts";
import "./globals.css";

const display = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
});

const body = DM_Sans({
  subsets: ["latin"],
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
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
