# README_DEV — 开发者交接文档

> 给未来接手者（人或 AI，如 Claude Code）的**工程导航图**。
> 目标：读完这一份，就能定位任何模块、理解依赖关系、知道从哪继续做。
>
> 三份文档分工：
> - **本文** = 架构 + 模块依赖 + 核心函数位置 + Todo（工程视角）
> - [`AGENTS.md`](AGENTS.md) = 2 分钟上手 + API 路由 + SSE 事件表 + 数据模型 + 行为约束
> - [`product-description.md`](product-description.md) = 产品愿景 + 设计取舍（「当初想做什么 vs 实际做成什么」）
> - [`ROADMAP.md`](ROADMAP.md) = 逐 Step 进度（single source of truth）
>
> 设计文档（Obsidian，非本仓）：`D:\My Second Brain\10-PROJECTS\deep-search-agent\design.md`

---

## 0. 30 秒理解

可控的深度搜索 Agent：**选题 → 澄清 → 确认研究计划 → 多跳搜索 → 提取事实 → 去重验证 → 生成带可点击引用的结构化报告**。

核心信条：**代码不该替 LLM 写字，LLM 不该替代码做账。** 预算/停止/归属/引用校验由确定性代码控制，LLM 只做网页理解与文字表达，且用强模型。

技术栈：Python 3.12 + FastAPI（后端）/ Next.js 16 + React 19 + Tailwind v4（前端）/ Tavily + DDG（搜索）/ OpenAI 兼容 LLM（当前 DeepSeek）/ 文件存储 + 静态 HTML 部署。

---

## 1. 目录结构

```
search-agent/
├── README_DEV.md            ← 本文
├── AGENTS.md ROADMAP.md product-description.md README.md
├── backend/                 ← FastAPI + 全部研究管线
│   ├── frameworks/          ← 行业研究骨架 YAML + examples/ few-shot 范文
│   ├── report_outlines/     ← 成文固定槽位 YAML（与 frameworks 同名对应）
│   ├── prompts/             ← 提示词
│   ├── providers/           ← 可插拔 search/fetch（tavily, ddg, httpx, jina）
│   ├── sources/             ← 信源目录 + Source Router + executor
│   ├── watchlist/           ← 订阅存储 + 再跑 runner + delta
│   └── .venv/               ← 虚拟环境（.venv/Scripts/python.exe）
├── eval/                    ← 质量门禁（L1/L2 离线 + L3 golden 联网）
│   └── fixtures/            ← 离线 eval 的 YAML 夹具
├── frontend/                ← Next.js App Router
│   └── app/  components/  lib/
└── reports/                ← 部署产物 <slug>/index.html + data.json（gitignored）
```

---

## 2. 数据流（主管线）

```
用户 topic
  │
  ▼  meta.py / brief.py           ← 澄清问题 → ResearchBrief（LLM 生成，代码判质量）
  │                                  brief_rubric.py 判定 → _rewrite_failed_directions 单条重写
  ▼  research_loop.run_research_loop  ← coverage 驱动多跳编排
  │    ├─ query_expand.py          确定性扩维（方向×信息类型×日期），中文保实体+英文 pivot
  │    ├─ sources/router.py        Source Router：选信源目录 + site: 种子
  │    ├─ sources/executor.py      执行检索（预算保护，leftover query 回填下一跳）
  │    ├─ providers/fetch_chain    抓取降级 httpx → jina → tavily
  │    ├─ extraction.py            LLM 提取结构化事实（ExtractedFact）
  │    ├─ dedup.py                 URL 去重 + 文本相似度去重
  │    ├─ verifier.py              跨源验证 + 置信度 + follow-up query
  │    └─ coverage.py              覆盖度评估 → GapHint → 是否继续跳
  ▼  report_synthesis.synthesize_report  ← 两阶段成文
  │    ├─ build_evidence_draft     Pass A：事实归槽（LLM，弱模型可）
  │    ├─ write_from_draft         Pass B：thesis + 长论述（强模型）
  │    │    ├─ check_thesis        结论门禁（判断/语言/锚点/限定）→ _repair_thesis
  │    │    ├─ _align_arguments_to_slots  章节数 == 方向数，空槽诚实产出
  │    │    └─ citation_integrity.enforce_citation_integrity  引用硬门禁
  │    └─ _degraded                降级可见（synthesis_degraded 事件）
  ▼  reporter.generate_report      ← 组装 Markdown（report_labels.yaml 双语骨架）
  ▼  deploy.py                     ← reports/<slug>/index.html + data.json
```

SSE 实时进度贯穿全程；事件类型全表见 `AGENTS.md`。

---

## 3. 模块依赖（谁调用谁）

```
main.py ──> agent.py ──────────────> research_loop.py ──> sources/*  providers/*
   │           │                          │  ├──> extraction.py  dedup.py  verifier.py
   │           │                          │  ├──> coverage.py    query_expand.py
   │           │                          │  └──> brief.py (绑定已确认 Brief)
   │           └──> report_synthesis.py ──> report_outlines/*  citation_integrity.py
   │                     │                   report_labels.py
   │                     └──> reporter.py ──> deploy.py  source_snapshots.py
   ├──> meta.py ──> brief.py ──> brief_rubric.py  frameworks/*
   └──> watchlist/* ──> runner.py ──> research_loop.py ──> delta.py

横切：
  config.py        全局配置（env）
  llm_context.py   BYOK per-request keys + get_openai_client + get_strong_model
  models.py        全部 Pydantic 模型（单一真相源）
  text_tokens.py   CJK 感知分词（coverage/expand/heuristic 共用）
  event_log.py     JSONL 事件日志
  streaming.py     SSE 封装
  auth.py middleware_auth.py  可选鉴权
```

关键约束：**`report_synthesis` 与 `frameworks` 有潜在循环依赖**，用惰性 import 打破（见 `report_outlines/__init__.py::select_outline_id`）。

---

## 4. 核心函数速查（文件:函数）

| 关注点 | 位置 |
|---|---|
| 同步研究入口 | `agent.py::run_research` / `run_deep_research` |
| 多跳编排 | `research_loop.py::run_research_loop` → `_run_research_loop_body` |
| Brief 生成 | `brief.py::generate_research_brief` / `revise_research_brief` |
| Brief 方向重写 | `brief.py::_rewrite_failed_directions` / `_judge_directions` |
| 方向质量 rubric | `brief_rubric.py::check_direction` / `check_instruction` / `harvest_entities` |
| 强模型选择 | `llm_context.py::get_strong_model`（`brief.py::get_brief_model` 委托它） |
| 澄清问题 | `meta.py::generate_clarifying_questions`、`brief.py::generate_industry_clarifying_questions` |
| 查询扩维 | `query_expand.py`（`DIMENSION_INFO_TYPES` / `OPEN_ONLY_DIMENSIONS`） |
| 信源路由 | `sources/router.py`、目录 `sources/catalog.py` + `sources/*.yaml` |
| 检索执行 | `sources/executor.py::execute_router_decision`（返回 3-tuple 含 leftover） |
| 抓取降级 | `providers/fetch_chain.py` |
| 事实提取 | `extraction.py` |
| 覆盖度 | `coverage.py::evaluate_coverage`（→ `GapHint`） |
| 两阶段成文 | `report_synthesis.py::synthesize_report` → `build_evidence_draft` + `write_from_draft` |
| 结论门禁 | `report_synthesis.py::check_thesis`（`ThesisVerdict`）+ `_repair_thesis` + `_judgment_thesis` |
| 章节对齐 | `report_synthesis.py::_align_arguments_to_slots` + `_empty_slot_argument` |
| 引用硬门禁 | `citation_integrity.py::enforce_citation_integrity`（`IntegrityReport`） |
| 报告骨架/标签 | `reporter.py::_generate_markdown` + `report_labels.py::get_labels` + `report_labels.yaml` |
| 方向→写作槽位 | `report_outlines/__init__.py::slots_from_brief` / `resolve_slots` |
| 数据模型 | `models.py`（`ResearchBrief` `BriefDimension` `ExtractedFact` `ReportSynthesis` `ResearchReport` …） |
| Watchlist 再跑 | `watchlist/runner.py`、增量 `watchlist/delta.py` |

---

## 5. 两份核心契约（Wave 12h，理解当前代码的关键）

**Direction Contract（方向契约）** — 批准的每条方向都必须被执行：
- 方向 LLM 生成、代码判质量（`brief_rubric`：动词开头、具名实体、语言一致）；不合格**单条重写**。
- 领域范文在 `frameworks/examples/*.yaml`（few-shot + 兜底），代码不再硬编码中文模板。
- 每方向带 `direction_id` / `entities` / `must_answer` / `budget_weight`；未执行 query 回填下一跳。

**Report Contract（报告契约）** — 结构由方向决定、每句可回溯：
- **章节数 == 方向数**，顺序一致；无证据的方向诚实产出「已检索什么 / 可能原因 / 建议信源」。
- **thesis 门禁**：判断而非过程说明、语言一致、含量化锚点 + 限定条件；不过则重写→确定性模板兜底。
- **引用硬门禁**：`[n]` 必须属于该章节 Pass A 分配集，越界剔除；缺引用不自动补（降级）；数字须见于被引原文。
- **双语骨架**：中文报告不出现英文标题；过程指标移文末附录。

---

## 6. 质量门禁（改动后必跑）

```bash
# 离线（不联网、不调 LLM）— 秒级，改成文/brief 逻辑后必跑
backend/.venv/Scripts/python.exe -m eval.offline            # L1 方向 + L2 成文/引用契约
backend/.venv/Scripts/python.exe -m eval.offline --layer l2

# 联网 golden（需 backend/.env 里的 LLM_API_KEY + TAVILY_API_KEY）
backend/.venv/Scripts/python.exe -m eval.run

# 后端单测（每个 test_*.py 是独立可执行模块，非 pytest）
backend/.venv/Scripts/python.exe -m test_wave12h_citations
# 全跑：Get-ChildItem test_*.py | %{ .\.venv\Scripts\python.exe -m $_.BaseName }
```

- **测试框架不是 pytest**，是每个 `test_*.py` 带 `if __name__ == "__main__"` 直接跑。
- 已知失败：`test_providers` 在无 `TAVILY_API_KEY` 时挂（环境问题，非代码 bug）。
- 前端类型检查：`cd frontend && pnpm exec tsc --noEmit`。
- eval 夹具在 `eval/fixtures/*.yaml`：`brief_*.yaml` 喂 L1，`writing_*.yaml` 喂 L2。

---

## 7. 本地运行

```bash
# 后端 → :8000
cd backend && .venv/Scripts/python.exe main.py     # 热重载含 *.py + *.yaml

# 前端 → :3000
cd frontend && pnpm dev
```

`.env`（在 `backend/`，gitignored，**绝不提交**）：
```
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1   # 或 OpenAI 兼容端点
LLM_MODEL=deepseek-v4-pro
LLM_BRIEF_MODEL=                            # 可选，留空则自动升级弱别名
TAVILY_API_KEY=tvly-...                     # 可选，缺失则降级 DDG
```

---

## 8. 未完成 Todo

### 质量收尾（评审文档剩余 P1，建议优先）
- [ ] **facts 检索阶段打 `direction_id`**：让归槽从「Pass A 猜」变确定性落槽。这是当前报告最易出错的环节，且与刚做完的引用门禁同一条线。触点：`extraction.py`（提取时带方向）+ `report_synthesis.build_evidence_draft`（用确定性归属替代 LLM 猜）。
- [ ] **market_entry 去掉 signal ledger**：signal ledger 是从私募债 investor_brief 借来的抽象，套在市场进入类报告上是错的。触点：`reporter.py::_generate_markdown` 的 `structured_findings` 分支 + `report_synthesis` findings 生成。

### 检索可靠性（ROADMAP Wave 12e）
- [ ] 第二搜索源 failover（现在 Tavily 挂只能退 DDG，质量落差大）。触点：`providers/search_*.py` + `sources/executor.py`。
- [ ] 早停策略 eval（多跳停止条件缺量化验证，易早停漏证据或白烧预算）。触点：`coverage.py` + 新增 eval case。

### 运维收尾（半小时级）
- [ ] Watchlist 本机周更脚本（Task Scheduler，ROADMAP 41f）：`scripts/run-watchlist.ps1`。
- [ ] 长报告目录锚点 + 报告页「复制中文 Markdown」按钮。触点：`frontend/components/ReportView.tsx`。

### 明确不做（个人自用场景优先级低）
- 公网 always-on 部署（Fly）：与「$0 + 最小攻击面」冲突，默认本机 Mode B。
- 用户偏好学习。
- Playwright/CDP 浏览器抓取层（L3/L4）：前三层抓取已够用，留给真正被墙的信源。

---

## 9. 接手建议

1. 先读 `AGENTS.md`（2 分钟全貌）+ 本文第 2-5 节。
2. 跑一遍 `eval.offline` 确认环境 OK。
3. 改成文/brief 逻辑 → 必跑 `eval.offline`；改检索 → 跑相关 `test_*.py` + 视情况 `eval.run`。
4. 完成一个 Step → 聚焦 commit + 勾选 `ROADMAP.md` + 更新本文 Todo。
5. 下一步首选：**facts 打 `direction_id`**（第 8 节质量收尾第一条）。
