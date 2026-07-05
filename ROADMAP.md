# Search Agent — Roadmap

> **Single source of truth** for implementation progress. Update this file at the end of each Step.

**Current phase:** Phase 1-alpha (skeleton complete) → Wave 1 in progress  
**Last updated:** 2026-07-05  
**Next step:** Step 18 — Report persistence via `data.json`

## Phase overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1-alpha | Done | FastAPI + Next.js pipeline: search → extract → dedup → report + SSE |
| Wave 1 (Step 13–19) | In progress | Search reliability: Tavily, fetch fallback, per-source extract, eval |
| Wave 2 (Step 20–24) | Planned | Deep research: planner, parallel sections, verifier (GPT Researcher patterns) |
| Wave 3 (Step 25–28) | Planned | Meta UI, human-in-the-loop, Vercel deploy |

## Phase 1-alpha checklist (complete)

- [x] FastAPI backend + Next.js frontend
- [x] DuckDuckGo search + httpx fetch + LLM extraction
- [x] URL + fact deduplication
- [x] Markdown report with `[^n]` citations + sidebar verification UI
- [x] SSE streaming progress
- [x] Static HTML deploy to `reports/<slug>/`
- [x] `AGENTS.md` onboarding doc

## Wave 1 — Search reliability

| Step | Task | Status |
|------|------|--------|
| 13 | GitHub public repo + ROADMAP + progress baseline | Done |
| 14 | Provider abstraction (`backend/providers/`) | Done |
| 15 | Tavily default search + DDG fallback | Done |
| 16 | Fetch chain: httpx → Jina → Tavily extract | Done |
| 17 | Per-source LLM extraction + Semaphore(3) | Done |
| 18 | Report persistence via `data.json` | Pending |
| 19 | `eval/golden_cases.yaml` + eval runner | Pending |

**Wave 1 done when:** 3/3 golden eval cases pass consistently.

## Wave 2 — Deep research intelligence

| Step | Task | Status |
|------|------|--------|
| 20 | Initial broad research + Planner JSON sections | Pending |
| 21 | Parallel section research (`asyncio.gather`) | Pending |
| 22 | Review-revise loop + `verifier.py` cross-validation | Pending |
| 23 | Deep research v1 (multi-hop, max 2 hops) | Pending |
| 24 | Event log JSONL + extended SSE events | Pending |

## Wave 3 — Product experience

| Step | Task | Status |
|------|------|--------|
| 25 | Meta API + human-in-the-loop (SSE) | Pending |
| 26 | Meta 5-step wizard UI | Pending |
| 27 | Vercel deployment (requires GitHub) | Pending |
| 28 | LangGraph sub-graph for review loop (optional) | Pending |

## Progress ritual

1. Complete one Step → focused `git commit`
2. Check off the Step in this file
3. Append to `.superpowers/sdd/progress.md`
4. Run `python -m eval.run` after Step 19+

## References

| Doc | Path |
|-----|------|
| AI onboarding | [AGENTS.md](AGENTS.md) |
| Product vision | [product-description.md](product-description.md) |
| Design (Obsidian) | `D:\My Second Brain\10-PROJECTS\deep-search-agent\design.md` |
| DeerFlow (reference) | `D:\Agent-self-education\deer-flow` |
| GPT Researcher (reference) | `D:\Agent-self-education\gpt-researcher` |

## Known issues

- DuckDuckGo rate limiting — mitigated by Tavily primary + DDG fallback (Step 15)
- Reports in-memory only until Step 18
- Batch LLM extraction until Step 17 — fixed: per-source extraction with concurrency limit
