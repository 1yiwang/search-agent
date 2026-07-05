import Link from "next/link";
import manifest from "@/public/demos/manifest.json";

interface DemoEntry {
  slug: string;
  title: string;
  topic: string;
  fact_count: number;
  source_count: number;
  summary: string;
}

export default function DemoGalleryPage() {
  const demos = manifest as DemoEntry[];

  return (
    <main className="mx-auto max-w-3xl px-4 py-16">
      <header className="mb-10 text-center">
        <p className="mb-2 text-xs uppercase tracking-[0.2em] text-[var(--muted)]">
          Static showcase
        </p>
        <h1 className="font-display text-4xl text-[var(--ink)]">Search Agent Demos</h1>
        <p className="mt-3 text-sm text-[var(--muted)] max-w-md mx-auto">
          Pre-built research reports with clickable citations. No API or API keys required.
        </p>
      </header>

      <ul className="space-y-4">
        {demos.map((demo) => (
          <li key={demo.slug}>
            <Link
              href={`/demo/${demo.slug}`}
              className="block rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 hover:border-[var(--accent-dim)] transition-colors"
            >
              <h2 className="font-display text-xl text-[var(--ink)]">{demo.title}</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">{demo.summary}</p>
              <p className="mt-3 text-xs text-[var(--muted)]">
                {demo.fact_count} facts · {demo.source_count} sources
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
