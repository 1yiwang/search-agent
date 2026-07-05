import Link from "next/link";
import { notFound } from "next/navigation";
import { readFile } from "fs/promises";
import path from "path";
import { DemoReportView } from "@/components/DemoReportView";
import type { ResearchReport } from "@/lib/api";
import manifest from "@/public/demos/manifest.json";

interface DemoEntry {
  slug: string;
  title: string;
}

async function loadDemoReport(slug: string): Promise<ResearchReport | null> {
  const allowed = (manifest as DemoEntry[]).some((d) => d.slug === slug);
  if (!allowed) return null;

  try {
    const file = path.join(process.cwd(), "public", "demos", slug, "data.json");
    const raw = await readFile(file, "utf-8");
    return JSON.parse(raw) as ResearchReport;
  } catch {
    return null;
  }
}

export default async function DemoReportPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const report = await loadDemoReport(slug);
  if (!report) notFound();

  return (
    <>
      <div className="mx-auto max-w-6xl px-4 pt-8">
        <Link href="/demo" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← All demos
        </Link>
      </div>
      <DemoReportView report={report} />
    </>
  );
}
