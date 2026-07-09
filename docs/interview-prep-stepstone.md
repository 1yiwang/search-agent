# StepStone Private Debt — Recruiter Screen Prep

> Role: **2026 Private Debt Product Management Intern** (Zurich)  
> JD: https://boards.greenhouse.io/embed/job_app?token=7492776  
> Demo: `/demo/european-direct-lending-2026`

## 30-second elevator pitch (EN)

I'm building a **private markets search agent**: a **Source Router** (LLM picks from a 36-source catalog) drives curated search, a **Coverage loop** decides when to dig deeper, and every claim links to the original source. Deterministic code executes and verifies — the LLM guides *what* to search, not *whether* facts are true.

## 30-second elevator pitch (中文)

我在做一个 **私募市场 Search Agent**：**Source Router**（LLM 从 36 个信源目录里选源）驱动定向搜索，**Coverage 循环**判断何时补盲深挖，每条结论可点击原文。执行与验证由确定性代码完成——LLM 指导「搜什么」，不替代「对不对」的判断。

## JD mapping

| JD requirement | Your answer / demo |
|----------------|-------------------|
| AI integration / LLM / prompt engineering | Source Router (`sources/router.py`) + extraction/synthesis prompts; `ROUTER_ENABLED=true`; BYOK |
| Client-oriented analysis, reporting, monitoring | Coverage evaluator (`coverage.py`) + `investor_brief` six-dimension check |
| Marketing document optimization | Agent cross-checks public sources against deck claims; flags unsupported stats |
| Cross-functional (research, sales, compliance) | White-box SSE event log + citation sidebar — not black-box synthesis |

## Two AI efficiency examples

### 1. Client FAQ draft pack

**Scenario:** An institutional client asks whether European private debt fundraising rebounded in 2025.

**Without agent:** Analyst spends 2–4 hours scanning research notes, finews, manager letters.

**With agent:** Topic `European corporate direct lending fundraising trends 2025` → 10-minute `investor_brief` with cited facts → SME edits tone for the specific SMA proposal.

**Demo line:** Our european-direct-lending-2026 demo cites StepStone's own [2H25 direct lending research](https://www.stepstonegroup.com/news-insights/recent-trends-in-corporate-direct-lending-2h25/) on the Europe rebound narrative.

### 2. Marketing claim verification

**Scenario:** A slide says "European PD fundraising rebounded in 2025."

**With agent:** Paste the claim → agent searches public sources → marks **corroborated** (with URL) vs **unsupported** vs **gaps** (paywalled LCD data).

**Value for compliance:** Reduces back-and-forth before materials go to legal.

## One honest limitation (shows professionalism)

Open-web intelligence **cannot replace** PitchBook, LCD, or loan-level covenant data. The design explicitly surfaces **gaps** in every report. Paid APIs are a natural L2 extension — not a weakness to hide.

## Good questions to ask the recruiter

1. Where does the product team spend the most time today — primary research or packaging materials for clients?
2. Are AI pilots leaning toward Microsoft Copilot workflows or custom agents integrated with internal data?
3. How does the Zurich office collaborate with London on private debt research and product?

## Demo walkthrough (5 min)

1. Open **search.yiwang.dev** → click **European Private Debt Brief** preset (or `/demo/european-direct-lending-2026`)
2. **Live run:** watch SSE progress — `Catalog: N candidate sources` → `Router hop 0: stepstone_insights, pei — rationale…` → `Direct fetch` → `Coverage hop 0: 50% (4 gaps)` → `Router hop 1` (补盲)
3. Show **Market Signals** table: Entity | Signal | Date | Confidence | Ref
4. Click a citation → sidebar highlights source excerpt
5. Point to **Fund & Product Activity** and **Credit Risk Watch**; read **Gaps** (paywalled LCD data not claimed)

## Architecture talking points

- **Still a Search Agent** — multi-hop, event log, citations; not a static report bot
- **Source Catalog** (`backend/sources/catalog/`) — 36 curated entries; add links by editing YAML only
- **LLM Router** — constrained JSON pick from catalog; code enforces domain/URL allowlist
- **Coverage loop** — deterministic six-dimension check for investor_brief; drives second hop like a human researcher
- **Disable router for eval:** `ROUTER_ENABLED=false` falls back to legacy seed path

## Why StepStone SPD specifically

- SPD is expanding **ELTIF** and **private wealth** channels in Europe — product teams need frequent market-to-client translation.
- StepStone publishes exactly the kind of research the agent can automate collection for ([direct lending 2H25](https://www.stepstonegroup.com/news-insights/recent-trends-in-corporate-direct-lending-2h25/), [Swiss pension funds](https://www.stepstonegroup.com/news-insights/direct-lending-for-swiss-pension-funds/)).
- The intern JD explicitly asks for **AI integration** — your project is a working prototype, not a slide deck.
