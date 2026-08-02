# Search Agent — Roadmap

> **Single source of truth** for implementation progress. Update this file at the end of each Step.

**Current phase:** Wave 12g Signal Flag UI (red / white / yellow)  
**Next step:** Wave 12e — second search provider failover + early-stop eval

## Product constraints (personal use)

- **Deploy default: Mode B** — local FastAPI + optional tunnel; **$0**, PC off = API off  
- **Always-on cloud (Fly) is optional / deferred** — conflicts with free + minimal-attack-surface preference  
- **Priority order:** find all useful sources → extract/verify → write brief → (UI polish last)

| When | What you can do |
|------|-----------------|
| **Now (local)** | Full stack: quick + deep search, `/plan`, `/watchlist`, citations, event logs |
| **Now (production)** | `search.yiwang.dev` — password gate, BYOK settings, research + **Saved reports** (`/history`) + Watchlist; API via tunnel when running — see [DEPLOY.md](DEPLOY.md) |
| **Next** | Optional local weekly watch script; Always-on Fly still deferred |
| **Pending** | `search-demo.yiwang.dev` static gallery DNS |

## Frontend roadmap

| Step | UI work |
|------|---------|
| 18 (done) | Dossier theme (Instrument Serif + DM Sans), human-readable progress feed |
| 26 (done) | Meta 5-step wizard at `/plan` + deep mode on homepage |
| 27 (done) | Production deploy — Vercel frontend + local API tunnel ([DEPLOY.md](DEPLOY.md)) |
| 35 (done) | Saved reports `/history` + same-origin API proxy on Vercel |
| 36 (done) | Phase 0: executive summary + structured findings table + report page redesign |

## Phase overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1-alpha | Done | FastAPI + Next.js pipeline: search → extract → dedup → report + SSE |
| Wave 1 (Step 13–19) | Done | Search reliability: Tavily, fetch fallback, per-source extract, eval |
| Wave 2 (Step 20–24) | Done | Deep research: planner, parallel sections, verifier, multihop, event log |
| Wave 3 (Step 25–35) | Done | Meta UI, deploy Mode B (local API + BYOK), saved reports |
| Wave 4 (Step 36) | Done | Phase 0: report synthesis, intelligence brief UI, Swiss robotics demo |
| Wave 5 (Step 37) | Done | Phase 1: DACH source registry + site: seed queries + 90d recency |
| Wave 6 (Step 38a) | Done | Phase 2a: private debt registry + investor_brief + Entity/Signal enums + EU PD demo |
| Wave 7 (Step 39–40) | Done | Source catalog (36+ entries) + LLM Router + Coverage-driven research loop |
| Wave 7b (Step 38b–38c) | Done | Extraction `signal_type` + European PD golden eval + catalog/links enrichment |
| Wave 8 search-quality | **Done** | Eval gate → diversity alignment → open-query quality → fail-over → loop tests |
| Phase 3 Watchlist | **Done (preview)** | Topic watch + manual re-run + finding delta + `/watchlist` UI |
| Always-on Fly API | Deferred | Optional paid hosting — not required for personal Mode B use |

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
| 34 | DNS aliases + Vercel env (`api-search.yiwang.dev`, BYOK) | Done |
| 35 | Saved reports `/history` + Vercel API proxy (`/api/reports`, `/api/research/[slug]`) | Done |

## Wave 4 — DACH intelligence Phase 0

| Step | Task | Status |
|------|------|--------|
| 36 | Executive summary + structured findings (`report_synthesis.py`, `ResearchReport` fields) | Done |
| 36 | Report page redesign (`ReportView.tsx` — summary card, sortable table, citation sidebar) | Done |
| 36 | Swiss robotics demo in `public/demos/swiss-robotics-2026/` | Done |

**Phase 0 done when:** Any research run produces summary → table → clickable citations; `/history` retains reports. **Status: complete (2026-07-06).**

## Wave 5 — DACH intelligence Phase 1

| Step | Task | Status |
|------|------|--------|
| 37 | `sources/dach_registry.yaml` — Swiss/DACH/FR media, universities, VC events | Done |
| 37 | `search_topic_with_seeds()` — site: seed layer + Tavily `days` recency | Done |
| 37 | `agent.py` / `planner.py` / `multihop.py` seed injection | Done |
| 37 | Extraction `event_date` + `RESEARCH_RECENCY_DAYS` (default 90) | Done |

**Phase 1 done when:** DACH-topics hit more vertical Swiss/EU sources than broad-only search. **Status: complete (2026-07-06).**

## Wave 6 — Private Debt intelligence Phase 2

> **Product narrative:** Private Markets Open-Source Intelligence Agent — DACH venture is one vertical module; **European private debt** is the Phase 2主线 (StepStone SPD alignment).

| Step | Task | Status |
|------|------|--------|
| 38a | `sources/private_debt_registry.yaml` + `pd_registry.py` intent + site: seeds | Done |
| 38a | `investor_brief` report template (`reporter.py`, `report_synthesis.py`) | Done |
| 38a | `SignalType` / `EntityType` enums in `models.py` | Done |
| 38a | European direct lending demo `public/demos/european-direct-lending-2026/` | Done |
| 38b | Extraction prompt with `signal_type` / `entity_type` for private debt topics | Done |
| 38c | `eval/golden_cases.yaml` — European PD smoke case + signal_type checks | Done |
| 39 | Source catalog `sources/catalog/` (36+ entries) + `links/` direct URLs | Done |
| 39 | `sources/router.py` — LLM constrained source selection + SSE `source_router_decision` | Done |
| 39 | `sources/executor.py` — direct_fetch → site_search → open_search | Done |
| 40 | `coverage.py` + `research_loop.py` — coverage-driven hops + SSE `coverage_eval` | Done |
| 40b | Citation modal + editorial report layout (frontend) | Done |
| 41 | Watchlist + weekly delta (Phase 3 preview) — see Wave below | Done |
| 42 | Always-on API (Fly.io) — optional paid; deferred for personal Mode B | Deferred |
| 43 | Search recall: `query_expand.py` — dimension × info_type × date matrix; hard cap ≤6/hop; SSE `query_expand` (borrowed from DeerFlow skill methodology, code-only) | Done |
| 44 | Search recall: executor open_budget `max(2, budget//3)`; force open on gaps / low diversity; fetch retry via catalog `entry_urls`; SSE `open_search_forced` / `fetch_retry` | Done |
| 45 | Search recall: `GapHint(dimension, research_goal, suggested_queries)` in `coverage.py`; expander fills concrete site:/open queries | Done |

## Wave 8 — Search quality (personal Mode B)

> Priority: measure useful recall → align contracts → improve open-web queries → deepen fail-over. No interview/demo narrative required.

| Step | Task | Status |
|------|------|--------|
| 46 | Recall eval gate: `min_coverage_score` / `min_covered_dimensions` / `require_open_web_query` in `eval/validate.py`; tighten `european-pd-smoke` | Done |
| 47 | Align diversity thresholds (`coverage` / `executor` / eval) + wire GapHint into next-hop routing | Done |
| 48 | Open-web query quality: embed `research_goal`; rotate info_types; budget-aware open query count | Done |
| 49 | Fail-over: empty site / failed fetch → alternate catalog sources; `TAVILY_DEEP_ON_GAP` default on | Done |
| 50 | Research-loop integration tests: gap → expand → pending → open/site hop-2 event chain | Done |

## Wave 9a — General search depth (vs thin open-web)

> Raise stop bar + open fan-out so general topics are not “done” after 3 facts.

| Step | Task | Status |
|------|------|--------|
| 51 | Coverage: `GENERAL_MIN_FACTS=8`, ≥5 domains; multi-angle empty gaps | Done |
| 52 | Defaults: frontend `max_sources=20`, `RESEARCH_MAX_HOPS=5`, expand cap 8 | Done |
| 53 | Executor: up to 6 open queries on force_open; Tavily advanced on open-web | Done |
| 54 | Expand: region / ranking-source / prior-year + entity follow-ups | Done |

## Wave 9b — Multilingual recall (CH / DACH)

> Chinese topics must not collapse to Chinese-only web. Fan out EN/DE/FR for Swiss markets.

| Step | Task | Status |
|------|------|--------|
| 55 | `multilang.py`: script/geo detect + zh→en pivot + locale open seeds | Done |
| 56 | Wire hop-0 `initial_open_queries` + expand multilang seeds | Done |
| 57 | Synthesis: prefer local EN/DE/FR sources for Swiss/DACH topics | Done |

## Wave 10 — Comprehensiveness (vs DeerFlow)

> Parallel fan-out + selective deep-read + hard synthesis gates. See [docs/overall-plan-vs-deerflow.md](docs/overall-plan-vs-deerflow.md).

| Step | Task | Status |
|------|------|--------|
| 58 | Parallel open-web queries per hop (`OPEN_SEARCH_PARALLEL`) | Done |
| 59 | Snippet rank → `FETCH_TOP_K_PER_HOP` deep fetch (`rank_fetch.py`) | Done |
| 60 | General synthesis gates: examples / challenges / experts | Done |
| 61 | Authority / report-type query templates | Done |
| 62 | Fast / standard / deep UI tiers | Done |

## Wave 11 — Swiss telecom catalog

| Step | Task | Status |
|------|------|--------|
| 63 | `swiss_telecom.yaml` + telecom intent → BAKOM/Swisscom/Sunrise/Salt | Done |
| 64 | Expand ZH telecom term map (already in multilang; extend as needed) | Done |
| 65 | Force multilang open seeds even when catalog matched | Done |

`job_brief` deferred — swiss-job-agent integration only.

## Wave 12a — Brief-first industry research

| Step | Task | Status |
|------|------|--------|
| 66 | `ResearchBrief` + `frameworks/*.yaml` + deterministic picker | Done |
| 67 | Industry clarify → generate/revise/confirm APIs (no web during brief) | Done |
| 68 | `research_loop` binds confirmed brief + deprioritize filter | Done |
| 69 | Frontend `/brief` wizard; Standard/Deep from homepage → brief | Done |

## Wave 12b — Report hierarchy UX

| Step | Task | Status |
|------|------|--------|
| 70 | `thesis` + `arguments[]` in synthesis + ResearchReport | Done |
| 71 | ReportView: 结论 → 分论点 → 局限 → 信源；Signals 折叠附录 | Done |

## Wave 12c — Two-pass Gemini-style writing

| Step | Task | Status |
|------|------|--------|
| 72 | Fixed `report_outlines/` + brief→slots mapping | Done |
| 73 | Pass A EvidenceDraft (assign/quarantine) + `draft_ready` SSE | Done |
| 74 | Pass B long section prose (~150–300 字) + ReportView body | Done |

## Wave 12d — Directions + substantive thesis (A′)

| Step | Task | Status |
|------|------|--------|
| 75 | Brief directions with rich `direction_detail`; clarify skippable | Done |
| 76 | Round-robin direction queries + missing-slot expand (code) | Done |
| 77 | Ban meta thesis; sanitize/fallback to findings | Done |
| 78 | Sources UI: one row per URL, no citation pile | Done |

## Wave 12e — Gemini-style 研究计划 instructions

| Step | Task | Status |
|------|------|--------|
| 79 | Prompt + post-parse: ban English skeleton titles; verb-led `direction_detail` | Done |
| 80 | Domain templates (CH telecom / CH ecom) + entity-rich query repair | Done |
| 81 | Brief UI: numbered plan primary; queries collapsed | Done |
| 82 | System prompt gold-standard + strip English goals from checklist; brief uses strongest model | Done |

## Wave 12f — App chrome UX

| Step | Task | Status |
|------|------|--------|
| 83 | Global AppChrome: Library + Settings gear; Settings sheet; offline banner only | Done |
| 84 | `/library` tabs (Saved / Watching); `/history` `/watchlist` redirect | Done |

## Wave 12g — Signal Flag UI (红白黄)

| Step | Task | Status |
|------|------|--------|
| 85 | Restyle app to paper / signal-red / flag-yellow + Fraunces | Done |

## Wave 12h — Direction Contract + Report Contract (planned)

> 输入文档：[docs/2026-08-02-architecture-review-brief-and-report.md](docs/2026-08-02-architecture-review-brief-and-report.md)

| Step | Task | Status |
|------|------|--------|
| 86 | Direction budget + leftover queries + Chinese coverage tokens | Done |
| 87 | Brief rubric + targeted regenerate; examples YAML (no hardcode) | Done |
| 88 | Report bilingual skeleton + thesis gate + args==directions | Done |
| 89 | Citation integrity gate + synthesis strong model + L1/L2 eval | Done |

## Phase 3 — Watchlist + weekly delta (Mode B)

> File-based topic monitoring. Manual Run (no cloud cron). Diff vs last report.

| Step | Task | Status |
|------|------|--------|
| 41a | `WatchItem` + `data/watchlists/` store + REST CRUD | Done |
| 41b | `POST /api/watchlist/{id}/run/stream` → research_loop + runs.jsonl | Done |
| 41c | `delta.compare_reports` + SSE `delta_ready` + unit tests | Done |
| 41d | Delta summary markdown written beside JSON | Done |
| 41e | Frontend `/watchlist` + report “Watch this topic” | Done |
| 41f | Optional `scripts/run-watchlist.ps1` + Task Scheduler docs | Pending |

## Progress ritual

1. Complete one Step → focused `git commit`
2. Check off the Step in this file
3. Append to `.superpowers/sdd/progress.md`
4. Run `python -m eval.run` after Step 19+

## References

| Doc | Path |
|-----|------|
| StepStone interview prep | [docs/interview-prep-stepstone.md](docs/interview-prep-stepstone.md) |
| AI onboarding | [AGENTS.md](AGENTS.md) |
| Product vision | [product-description.md](product-description.md) |
| Design (Obsidian) | `D:\My Second Brain\10-PROJECTS\deep-search-agent\design.md` |
| DeerFlow (reference) | `D:\Agent-self-education\deer-flow` |
| GPT Researcher (reference) | `D:\Agent-self-education\gpt-researcher` |

## Known issues

- DuckDuckGo rate limiting — mitigated by Tavily primary + DDG fallback (Step 15)
- Reports in-memory only until Step 18 — fixed: `reports/<slug>/data.json`
- Batch LLM extraction until Step 17 — fixed: per-source extraction with concurrency limit
- Vercel must not rewrite `/api/research/*` — fixed Step 35: rewrites disabled on Vercel; use App Router proxy routes
- Run only one backend on `:8000` — duplicate `python main.py` causes CORS / stale-process bugs
