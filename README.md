# Search Agent

> **"Not faster search — verified, structured, traceable answers."**

A controllable deep research agent. You confirm the research plan, the agent executes
it end-to-end, and **every claim in the report is backed by a clickable source with a
highlighted quote and a confidence level**.

ChatGPT and Gemini can search, but their search is a black box — you don't know what
they read, what they missed, or which conclusion is trustworthy. Search Agent makes the
strategy explicit, cross-checks multiple sources, and writes a structured report where
you can verify every sentence yourself.

---

## How it works

```
topic
  │
  ▼  clarify → confirm a research plan (Brief)      you stay in control
  ▼  coverage-driven multi-hop search               Tavily (primary) + DuckDuckGo (fallback)
  ▼  LLM fact extraction → dedup → cross-verify      structured, cited facts with confidence
  ▼  two-pass synthesis (evidence draft → prose)     strong model, deterministic gates
  ▼  report: thesis → arguments → sources            bilingual skeleton, clickable citations
```

**Design principle: the deterministic engine is the brain, the LLM works at the edges.**
Code owns search strategy, budget, stopping conditions, fact attribution, and citation
checking. The LLM only reads web pages and writes prose — it never decides *what counts*.
This keeps the agent predictable, reproducible, and auditable.

---

## Features

- **Plan-first, you approve** — clarifying questions → a research brief you can edit → the
  agent only searches what you confirmed.
- **Coverage-driven multi-hop** — search → extract → cross-check → find gaps → search again,
  until coverage is met (not a single-shot query).
- **Every claim is verifiable** — each fact carries a source URL, an original quote, and a
  confidence level; click `[n]` to open the source with the quote highlighted.
- **Two contracts keep it honest** — approved directions map 1:1 to report sections; a
  citation gate enforces that `[n]` belongs to the section's evidence and that numbers appear
  in the cited source.
- **Bilingual reports** — Chinese topics render a Chinese report skeleton; process metrics
  stay out of the conclusion.
- **Watchlist** — re-run a topic and diff against the last report to track what changed.
- **BYOK + local-first** — bring your own LLM / Tavily keys; runs on your machine at $0.

---

## Quick start

**Prerequisites:** Python 3.12+, Node.js 20+, pnpm

### Backend → http://localhost:8000

```bash
cd backend
cp .env.example .env          # then edit: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, TAVILY_API_KEY
pip install -r requirements.txt
python main.py
```

### Frontend → http://localhost:3000

```bash
cd frontend
pnpm install
pnpm dev
```

`.env` keys (in `backend/`, git-ignored):

```
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1   # any OpenAI-compatible endpoint
LLM_MODEL=deepseek-v4-pro
TAVILY_API_KEY=tvly-...                     # optional; falls back to DuckDuckGo
```

---

## API (selected)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/brief/clarify` | POST | Clarifying questions for a topic |
| `/api/brief/generate` | POST | Skeleton + answers → research brief |
| `/api/brief/research/stream` | POST | Execute a confirmed brief (SSE) |
| `/api/research/stream` | POST | Run research with live progress (SSE) |
| `/api/research/{slug}` | GET | Fetch a completed report |
| `/api/watchlist` | GET/POST | List / create topic subscriptions |
| `/api/watchlist/{id}/run/stream` | POST | Re-run + delta (SSE) |

Full route list and the SSE event schema are in [`AGENTS.md`](AGENTS.md).

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 16 + React 19 + Tailwind v4 + TypeScript |
| Search | Tavily (primary) + DuckDuckGo (fallback) |
| Fetch | httpx → Jina → Tavily Extract (layered fallback) |
| LLM | OpenAI-compatible (currently DeepSeek) |
| Storage | Files — reports, watchlists, JSONL event logs |
| Deploy | Static HTML per report |

---

## Documentation

| Doc | For |
|-----|-----|
| [`README_DEV.md`](README_DEV.md) | Architecture, module dependencies, core function map, TODOs |
| [`AGENTS.md`](AGENTS.md) | 2-minute onboarding, API routes, SSE events, data models |
| [`product-description.md`](product-description.md) | Product vision + design trade-offs (planned vs built) |
| [`ROADMAP.md`](ROADMAP.md) | Step-by-step progress (single source of truth) |
| [`DEPLOY.md`](DEPLOY.md) | Deployment guide |

**Status:** daily-usable personal research tool. Phases 1–2 (multi-hop, cross-verification,
confidence) done; Phase 3 shipped Web UI + Watchlist. Latest work: Wave 12h Direction &
Report contracts + a deterministic citation-integrity gate. See [ROADMAP.md](ROADMAP.md).

---

> Building "an AI that can search" is easy — ChatGPT already did it. Building "an AI whose
> search results you trust" is the real moat.
