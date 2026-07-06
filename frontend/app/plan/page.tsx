"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  metaClarify,
  metaPlan,
  streamMetaResearch,
  type ClarifyingQuestion,
  type ResearchPlan,
  type SSEEvent,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { researchReportPath, slugFromReportReady } from "@/lib/researchNav";
import { ApiStatus } from "@/components/ApiStatus";
import { SettingsPanel } from "@/components/SettingsPanel";

type WizardStep = 1 | 2 | 3 | 4 | 5;

const STEP_LABELS = ["Topic", "Clarify", "Plan", "Review", "Execute"];

export default function PlanWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(1);
  const [topic, setTopic] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [questions, setQuestions] = useState<ClarifyingQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<{
    slug: string;
    markdown: string;
    fact_count: number;
  } | null>(null);

  async function handleClarify() {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await metaClarify(topic.trim());
      setSessionId(res.session_id);
      setQuestions(res.questions);
      setAnswers({});
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clarify");
    } finally {
      setLoading(false);
    }
  }

  async function handleGeneratePlan() {
    setLoading(true);
    setError("");
    try {
      const generated = await metaPlan({
        session_id: sessionId,
        answers,
        max_sections: 4,
        initial_sources: 5,
      });
      setPlan(generated);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevisePlan() {
    if (!feedback.trim()) {
      setStep(4);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const revised = await metaPlan({
        session_id: sessionId,
        answers,
        feedback: feedback.trim(),
        max_sections: 4,
        initial_sources: 5,
      });
      setPlan(revised);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revise plan");
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute() {
    setLoading(true);
    setError("");
    setProgress([]);
    setResult(null);
    setStep(5);

    const events: SSEEvent[] = [];
    try {
      for await (const event of streamMetaResearch({ session_id: sessionId })) {
        events.push(event);
        setProgress((prev) => [...prev, formatProgressEvent(event)]);

        const slug = slugFromReportReady(event);
        if (slug) {
          router.push(researchReportPath(slug));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 md:py-20">
      <header className="mb-8">
        <Link href="/" className="text-sm text-[var(--link)] hover:underline">
          ← Back to quick search
        </Link>
        <h1 className="font-display text-3xl md:text-4xl text-[var(--ink)] mt-4">
          Deep planning wizard
        </h1>
        <p className="mt-2 text-[var(--muted)] text-sm">
          Clarify scope → review dimensions → execute verified research.
        </p>
        <div className="mt-3 flex flex-col gap-2">
          <ApiStatus />
          <SettingsPanel />
        </div>
      </header>

      <nav className="mb-8 flex gap-1 text-xs uppercase tracking-wide">
        {STEP_LABELS.map((label, i) => {
          const n = (i + 1) as WizardStep;
          const active = step === n;
          const done = step > n;
          return (
            <div
              key={label}
              className={`flex-1 rounded px-2 py-2 text-center border ${
                active
                  ? "border-[var(--accent)] bg-[var(--surface-raised)] text-[var(--ink)]"
                  : done
                    ? "border-[var(--border)] text-[var(--muted)]"
                    : "border-transparent text-[var(--muted)] opacity-50"
              }`}
            >
              {label}
            </div>
          );
        })}
      </nav>

      {error && (
        <p className="mb-4 rounded-lg border border-red-300/40 bg-red-50/10 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {step === 1 && (
        <section className="space-y-4">
          <label className="block text-sm font-medium text-[var(--ink)]">
            Research topic
          </label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. EU AI Act compliance for SaaS startups"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
            disabled={loading}
          />
          <button
            type="button"
            onClick={handleClarify}
            disabled={loading || !topic.trim()}
            className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[#1a1408] disabled:opacity-40"
          >
            {loading ? "Thinking…" : "Continue → clarify"}
          </button>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-5">
          {questions.map((q) => (
            <div key={q.id}>
              <label className="block text-sm font-medium text-[var(--ink)] mb-1">
                {q.question}
              </label>
              <input
                type="text"
                value={answers[q.id] || ""}
                onChange={(e) =>
                  setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                }
                placeholder={q.hint || "Your answer (optional)"}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm"
                disabled={loading}
              />
            </div>
          ))}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleGeneratePlan}
              disabled={loading}
              className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[#1a1408] disabled:opacity-40"
            >
              {loading ? "Researching & planning…" : "Generate plan →"}
            </button>
          </div>
        </section>
      )}

      {step === 3 && plan && (
        <section className="space-y-4">
          <h2 className="font-display text-xl text-[var(--ink)]">{plan.title}</h2>
          <p className="text-sm text-[var(--muted)] line-clamp-4">
            {plan.initial_research_summary.slice(0, 400)}
            {plan.initial_research_summary.length > 400 && "…"}
          </p>
          <ul className="space-y-3">
            {plan.dimensions.map((dim, i) => (
              <li
                key={i}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <p className="font-medium text-[var(--ink)]">{dim.title}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  {dim.queries.join(" · ")}
                </p>
              </li>
            ))}
          </ul>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => setStep(4)}
              className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[#1a1408]"
            >
              Review plan →
            </button>
          </div>
        </section>
      )}

      {step === 4 && plan && (
        <section className="space-y-4">
          <p className="text-sm text-[var(--muted)]">
            Approve the plan or describe changes. Leave blank to proceed as-is.
          </p>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="e.g. Add a dimension on enforcement penalties; focus on 2025–2026"
            rows={4}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm"
            disabled={loading}
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setStep(3)}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
            >
              Back
            </button>
            {feedback.trim() ? (
              <button
                type="button"
                onClick={handleRevisePlan}
                disabled={loading}
                className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[#1a1408] disabled:opacity-40"
              >
                {loading ? "Revising…" : "Revise plan"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleExecute}
              disabled={loading}
              className="rounded-lg bg-[var(--ink)] px-6 py-2.5 font-semibold text-[var(--surface)] disabled:opacity-40"
            >
              Approve & execute →
            </button>
          </div>
        </section>
      )}

      {step === 5 && (
        <section className="space-y-4">
          {progress.length > 0 && (
            <ol className="max-h-56 overflow-y-auto space-y-2 text-sm rounded-lg border border-[var(--border)] p-4">
              {progress.map((line, i) => (
                <li
                  key={i}
                  className={
                    i === progress.length - 1 && loading
                      ? "text-[var(--ink)]"
                      : "text-[var(--muted)]"
                  }
                >
                  {line}
                </li>
              ))}
            </ol>
          )}
          {result && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
              <p className="text-sm text-[var(--muted)] mb-2">
                {result.fact_count} facts ·{" "}
                <Link
                  href={`/research/${result.slug}`}
                  className="text-[var(--link)] hover:underline"
                >
                  Open report →
                </Link>
              </p>
              <pre className="whitespace-pre-wrap text-sm text-[var(--muted)] font-mono max-h-48 overflow-y-auto">
                {result.markdown.slice(0, 1500)}
                {result.markdown.length > 1500 && "\n\n…"}
              </pre>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
