"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  briefClarify,
  briefConfirm,
  briefGenerate,
  briefRevise,
  streamBriefResearch,
  type ClarifyingQuestion,
  type ResearchBrief,
} from "@/lib/api";
import { formatProgressEvent } from "@/lib/formatProgress";
import { researchReportPath, slugFromReportReady } from "@/lib/researchNav";

type WizardStep = 1 | 2 | 3 | 4 | 5;
type Depth = "fast" | "standard" | "deep";

const STEP_LABELS = ["Topic", "Clarify", "Directions", "Confirm", "Execute"];

function BriefWizardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<WizardStep>(1);
  const [topic, setTopic] = useState("");
  const [depth, setDepth] = useState<Depth>("deep");
  const [sessionId, setSessionId] = useState("");
  const [frameworkId, setFrameworkId] = useState("");
  const [questions, setQuestions] = useState<ClarifyingQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [brief, setBrief] = useState<ResearchBrief | null>(null);
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<string[]>([]);

  useEffect(() => {
    const t = searchParams.get("topic");
    const d = searchParams.get("depth");
    if (t) setTopic(t);
    if (d === "fast" || d === "standard" || d === "deep") setDepth(d);
  }, [searchParams]);

  async function handleClarify() {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await briefClarify(topic.trim());
      setSessionId(res.session_id);
      setQuestions(res.questions);
      setFrameworkId(res.suggested_framework_id);
      setAnswers({});
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clarify");
    } finally {
      setLoading(false);
    }
  }

  async function handleSkipClarify() {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await briefClarify(topic.trim());
      setSessionId(res.session_id);
      setQuestions(res.questions);
      setFrameworkId(res.suggested_framework_id);
      const generated = await briefGenerate({
        session_id: res.session_id,
        answers: {},
        framework_id: res.suggested_framework_id,
      });
      setBrief(generated);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate brief");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateBrief() {
    setLoading(true);
    setError("");
    try {
      const generated = await briefGenerate({
        session_id: sessionId,
        answers,
        framework_id: frameworkId || undefined,
      });
      setBrief(generated);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate brief");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevise() {
    if (!feedback.trim()) {
      setStep(4);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const revised = await briefRevise({
        session_id: sessionId,
        feedback: feedback.trim(),
      });
      setBrief(revised);
      setFeedback("");
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revise brief");
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute() {
    setLoading(true);
    setError("");
    setProgress([]);
    setStep(5);
    try {
      await briefConfirm(sessionId);
      for await (const event of streamBriefResearch({
        session_id: sessionId,
        depth,
      })) {
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
        <h1 className="font-display text-3xl md:text-4xl text-[var(--ink)]">
          Industry research brief
        </h1>
        <p className="mt-2 text-[var(--muted)] text-sm">
          Clarify boundary → review search overview → execute cited research.
        </p>
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
            placeholder="e.g. 中国联通进入瑞士电信市场的机会"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
            disabled={loading}
          />
          <div className="flex flex-wrap gap-4 text-sm">
            {(
              [
                ["standard", "Standard"],
                ["deep", "Deep"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="depth"
                  checked={depth === value}
                  onChange={() => setDepth(value)}
                  className="accent-[var(--accent)]"
                />
                {label}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleClarify}
              disabled={loading || !topic.trim()}
              className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[var(--cta-ink)] disabled:opacity-40"
            >
              {loading ? "Thinking…" : "Continue → clarify"}
            </button>
            <button
              type="button"
              onClick={handleSkipClarify}
              disabled={loading || !topic.trim()}
              className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm disabled:opacity-40"
            >
              Skip clarify → directions
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-5">
          {frameworkId && (
            <p className="text-xs text-[var(--muted)]">
              Suggested framework: <span className="text-[var(--ink)]">{frameworkId}</span>
            </p>
          )}
          {questions.map((q) => (
            <div key={q.id}>
              <label className="block text-sm font-medium text-[var(--ink)] mb-1">
                {q.category ? (
                  <span className="mr-2 text-xs uppercase tracking-wide text-[var(--muted)]">
                    {q.category}
                  </span>
                ) : null}
                {q.question}
              </label>
              {q.options && q.options.length > 0 ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {q.options.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() =>
                        setAnswers((prev) => ({ ...prev, [q.id]: opt }))
                      }
                      className={`rounded border px-3 py-1 text-xs ${
                        answers[q.id] === opt
                          ? "border-[var(--accent)] text-[var(--ink)]"
                          : "border-[var(--border)] text-[var(--muted)]"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              ) : null}
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
              onClick={handleGenerateBrief}
              disabled={loading}
              className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[var(--cta-ink)] disabled:opacity-40"
            >
              {loading ? "Building directions…" : "Generate directions →"}
            </button>
          </div>
        </section>
      )}

      {step === 3 && brief && (
        <section className="space-y-4">
          <h2 className="font-display text-xl text-[var(--ink)]">
            {brief.problem_restatement || brief.topic}
          </h2>
          <p className="text-xs text-[var(--muted)]">
            Framework: {brief.framework_id} · {brief.dimensions.length} 条研究指令
          </p>
          {brief.success_criteria?.length ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">
                Report must answer
              </p>
              <ul className="text-sm text-[var(--ink)]/85 list-disc pl-5 space-y-1">
                {brief.success_criteria.slice(0, 6).map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {brief.deprioritize.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">
                Deprioritize
              </p>
              <ul className="text-sm text-[var(--muted)] list-disc pl-5">
                {brief.deprioritize.slice(0, 6).map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">
            研究计划 / Research plan
          </p>
          <ol className="space-y-4 list-none">
            {brief.dimensions.map((dim, i) => {
              const instruction =
                (dim.direction_detail || "").trim() ||
                (dim.research_goal || "").trim() ||
                dim.title;
              return (
              <li
                key={i}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <p className="text-[var(--ink)] leading-relaxed">
                  <span className="text-[var(--signal)] font-medium mr-1">
                    ({i + 1})
                  </span>
                  {instruction}
                </p>
                {dim.title &&
                dim.title !== instruction &&
                !(dim.direction_detail || "").startsWith(dim.title) ? (
                  <p className="mt-1 text-xs text-[var(--muted)]">{dim.title}</p>
                ) : null}
                {dim.queries.length > 0 ? (
                  <details className="mt-2 text-xs text-[var(--muted)]">
                    <summary className="cursor-pointer select-none">
                      检索词（{dim.queries.length}）
                    </summary>
                    <p className="mt-1 leading-relaxed">{dim.queries.join(" · ")}</p>
                  </details>
                ) : null}
              </li>
              );
            })}
          </ol>
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
              className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[var(--cta-ink)]"
            >
              Review & confirm →
            </button>
          </div>
        </section>
      )}

      {step === 4 && brief && (
        <section className="space-y-4">
          <p className="text-sm text-[var(--muted)]">
            Approve the brief or describe changes. Leave blank to execute as-is.
          </p>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="e.g. Drop GDP entirely; add MVNO / wholesale angle; focus on B2B"
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
                onClick={handleRevise}
                disabled={loading}
                className="rounded-lg bg-[var(--accent)] px-6 py-2.5 font-semibold text-[var(--cta-ink)] disabled:opacity-40"
              >
                {loading ? "Revising…" : "Revise brief"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleExecute}
              disabled={loading}
              className="rounded-lg bg-[var(--ink)] px-6 py-2.5 font-semibold text-[var(--surface)] disabled:opacity-40"
            >
              Confirm & research →
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
        </section>
      )}
    </main>
  );
}

export default function BriefWizardPage() {
  return (
    <Suspense fallback={<main className="p-8 text-[var(--muted)]">Loading…</main>}>
      <BriefWizardInner />
    </Suspense>
  );
}
