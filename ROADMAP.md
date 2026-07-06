# Search Agent — Roadmap

> **Single source of truth** for implementation progress. Update this file at the end of each Step.

**Current phase:** Wave 3b — deploy Mode B (local API + BYOK)  
**Next step:** Cloudflare DNS for `search-demo` + run `setup-cloudflare-tunnel.ps1`

## Usability timeline

| When | What you can do |
|------|-----------------|
| **Now (local)** | Full stack: quick + deep search, `/plan` wizard, citations, event logs |
| **After Step 29–34** | `search.yiwang.dev` (password, BYOK settings) + local API on demand; `search-demo` static gallery — see [DEPLOY.md](DEPLOY.md) |

## Frontend roadmap

| Step | UI work |
|------|---------|
| 18 (done) | Dossier theme (Instrument Serif + DM Sans), human-readable progress feed |
| 26 (done) | Meta 5-step wizard at `/plan` + deep mode on homepage |
| 27 (done) | Production deploy — Vercel frontend + Render/Docker API ([DEPLOY.md](DEPLOY.md)) |
| Future | Report page full redesign, research history list, mobile polish |

## Phase overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1-alpha | Done | FastAPI + Next.js pipeline: search → extract → dedup → report + SSE |
| Wave 1 (Step 13–19) | Done | Search reliability: Tavily, fetch fallback, per-source extract, eval |
| Wave 2 (Step 20–24) | Done | Deep research: planner, parallel sections, verifier, multihop, event log |
| Wave 3 (Step 25–34) | In progress | Meta UI, deploy Mode B (local API + BYOK) |

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
| 18 | Report persistence via `data.json` | Done |
| 19 | `eval/golden_cases.yaml` + eval runner | Done |

**Wave 1 done when:** 3/3 golden eval cases pass consistently. **Status: 3/3 passed (2026-07-05).**

## Wave 2 — Deep research intelligence

| Step | Task | Status |
|------|------|--------|
| 20 | Initial broad research + Planner JSON sections | Done |
| 21 | Parallel section research (`asyncio.gather`) | Done |
| 22 | Review-revise loop + `verifier.py` cross-validation | Done |
| 23 | Deep research v1 (multi-hop, max 2 hops) | Done |
| 24 | Event log JSONL + extended SSE events | Done |

## Wave 3 — Product experience

| Step | Task | Status |
|------|------|--------|
| 25 | Meta API + human-in-the-loop (SSE) | Done |
| 26 | Meta 5-step wizard UI | Done |
| 27 | Vercel deployment (interim URL live) | Done |
| 28 | LangGraph sub-graph for review loop (optional) | Pending |

## Wave 3b — Deploy Mode B (local API, $0)

> **Approved plan:** Website always on Vercel; LLM runs only when `start-personal.ps1` is active on your PC.  
> Settings (model, API key) editable in browser; keys stay on your machine (自用).

| Step | Task | Status |
|------|------|--------|
| 29 | `scripts/start-personal.ps1` — API + Cloudflare Tunnel | Done |
| 30 | Site password middleware (`search.yiwang.dev`) | Done |
| 31 | API token after login (anti-abuse when tunnel up) | Done |
| 32 | Settings UI — LLM model / base URL / API key (BYOK, localStorage) | Done |
| 33 | `search-demo.yiwang.dev` static demo gallery | Done |
| 34 | DNS aliases + Vercel cleanup (remove temp tunnel env) | In progress |

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
- Reports in-memory only until Step 18 — fixed: `reports/<slug>/data.json`
- Batch LLM extraction until Step 17 — fixed: per-source extraction with concurrency limit
