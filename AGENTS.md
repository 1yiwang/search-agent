# Search Agent — AI Agent Onboarding

> **读我第一。** 这份文件让你（AI coding agent）在 2 分钟内理解本项目的全貌。

## 这是什么

一个**可控的深度搜索 Agent**：用户输入问题 → 多源搜索 → LLM 提取事实 → 去重验证 → 生成带可点击引用的结构化报告。

定位：「不是更快的搜索，而是经过验证的、结构化的、可追溯的答案。」

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 后端 | Python 3.12 + FastAPI | `backend/` |
| 前端 | Next.js 16 + React 19 + Tailwind v4 + TypeScript | `frontend/` |
| 搜索 | Tavily（主）+ DuckDuckGo（降级） | `backend/providers/` |
| LLM | OpenAI 兼容接口 → 当前用 DeepSeek v4 Pro | `backend/extraction.py` |
| 部署 | 静态 HTML → `reports/<slug>/index.html` | `backend/deploy.py` |
| 包管理 | pip（后端）+ pnpm（前端） |  |

## 项目结构

```
D:/Projects/search-agent/
├── AGENTS.md                  ← 你正在读的文件
├── README.md                  ← 人类阅读的 README
├── product-description.md     ← 完整产品愿景（2026-06-21 原始设计）
│
├── backend/
│   ├── main.py                ← FastAPI 入口：4 个路由 + SSE 流式
│   ├── config.py              ← 环境变量配置（LLM_API_KEY 等）
│   ├── models.py              ← Pydantic v2 数据模型（7 个类）
│   ├── search.py              ← 搜索 + 网页抓取 facade
│   ├── providers/             ← 可插拔 search/fetch（tavily, ddg, httpx）
│   ├── extraction.py          ← LLM 结构化事实提取（OpenAI SDK）
│   ├── dedup.py               ← URL 去重 + 文本相似度去重
│   ├── reporter.py            ← Markdown 报告生成（[^n] 引用系统）
│   ├── agent.py               ← 研究管线编排（6 步 pipeline）
│   ├── deploy.py              ← 静态 HTML 部署到 reports/
│   ├── .env                   ← 本地环境变量（gitignored）
│   └── .env.example           ← 环境变量模板
│
└── frontend/
    └── app/
        ├── page.tsx               ← 搜索主页（SSE 实时进度）
        ├── layout.tsx             ← 根布局
        ├── globals.css            ← Tailwind v4 全局样式
        └── research/[slug]/
            └── page.tsx           ← 报告页（引文侧栏验证）
```

## API 路由

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/research` | 同步研究（fire-and-forget） |
| POST | `/api/research/stream` | **SSE 流式**研究 |
| POST | `/api/plan/preview` | 广度研究 + 生成维度方案（Wave 2） |
| POST | `/api/research/deep/stream` | 规划 + 维度并行深度研究（SSE） |
| GET | `/api/research/{slug}` | 获取已完成的报告 |
| POST | `/api/meta/clarify` | 生成澄清问题 + 创建 meta session |
| POST | `/api/meta/plan` | 带人工答案/反馈生成研究方案 |
| POST | `/api/meta/research/stream` | 执行已批准方案（SSE） |
| GET | `/api/research/{slug}/events` | 获取研究过程 JSONL 事件日志 |

### 请求/响应格式

**POST /api/research** — 入参 `{topic: str, max_sources: int}`，出参 `ResearchReport`（见下文模型）

**POST /api/research/stream** — 入参同上，SSE 流式返回，事件类型（与 `agent.py` + `main.py` 一致）：

| 事件 | 触发时机 | payload |
|------|---------|---------|
| `search_start` | 开始研究 | `{topic, max_sources}` |
| `search_complete` | 搜索完成 | `{results_found}` |
| `fetch_fallback` | 抓取降级（httpx→jina→tavily） | `{url, from, to, reason}` |
| `dedup_complete` | URL 去重完成 | `{before, after, removed}` |
| `extraction_start` | LLM 开始提取 | `{sources_with_content}` |
| `extraction_complete` | 提取完成 | `{facts_extracted}` |
| `fact_dedup_complete` | 事实去重完成 | `{before, after}` |
| `verify_complete` | 跨源验证 + 审查完成 | `{before, after, corroborated, boosted, demoted, removed_by_review, follow_up_queries, hop?}` |
| `multihop_start` | 多跳追加搜索开始 | `{hop, queries}` |
| `multihop_complete` | 多跳搜索完成 | `{hop, new_facts, queries}` |
| `plan_start` | 深度研究开始 | `{topic, title, dimension_count}` |
| `plan_ready` | 方案生成完毕（deep stream） | `{title, dimensions}` |
| `dimension_start` | 维度并行搜索开始 | `{title, queries, info_type}` |
| `dimension_complete` | 维度搜索完成 | `{title, results_found}` |
| `session_start` | SSE 会话开始 | `{topic, mode, seq, run_id}` |
| `report_start` | 开始生成报告 | `{fact_count}` |
| `report_complete` | 报告对象生成 | `{slug, citation_count}` |
| `report_ready` | 部署完成（main.py） | `{slug, topic, html_url, fact_count, citation_count, events_path}` |
| `report_content` | 完整 Markdown | `{markdown}` |
| `error` | 异常 | `{message}` |

## 核心数据模型（详细）

```python
# models.py — 7 个 Pydantic v2 模型

class ResearchRequest(BaseModel):
    topic: str              # 3-500 字符
    max_sources: int = 10   # 3-30

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    full_text: str = ""     # fetch_page 后填充

class ExtractedFact(BaseModel):
    fact: str               # 事实陈述
    source_url: str
    source_title: str
    quoted_text: str        # 原文引述
    confidence: str         # high|medium|low

class Citation(BaseModel):
    index: int              # 引用编号 [¹]
    source_name: str
    source_url: str
    quoted_text: str
    highlight_anchor: str   # 原文中高亮定位的文本片段

class ReportMetadata(BaseModel):
    execution_time_seconds: float
    source_count: int
    topics_searched: list[str]
    started_at: str
    completed_at: str

class ResearchReport(BaseModel):
    topic: str
    slug: str               # URL safe 标识
    facts: list[ExtractedFact]
    citations: list[Citation]
    markdown: str           # 带 [^n] 注脚的完整报告
    html_url: str           # 部署后的 URL
    metadata: Optional[ReportMetadata]
```

## 核心数据流

```
用户输入 (topic, max_sources)
  │
  ▼
agent.run_research()
  │
  ├─ 1. search_web()          → DuckDuckGo → list[SearchResult]
  ├─ 2. dedup (URL)           → 去重 URL
  ├─ 3. fetch_page() × N      → httpx 并发抓取 → markdownify
  ├─ 4. extract_facts()       → LLM 提取 → list[ExtractedFact]
  ├─ 5. dedup (facts)         → 同源去重 + 相似度去重
  └─ 6. generate_report()     → Markdown + [^n] 引用
       │
       ▼
     deploy_report()           → reports/<slug>/index.html + data.json
```

## 当前状态

**Wave 3b–5 ✅ 生产可用**（2026-07-06）— 详见 [ROADMAP.md](ROADMAP.md)

- [x] Phase 1-alpha MVP + Wave 1–2（搜索可靠性、深度研究）
- [x] Wave 3b：search.yiwang.dev + BYOK + Saved reports `/history`
- [x] **DACH Phase 0**：执行摘要 + 结构化 findings 表 + ReportView 情报简报 UI
- [x] **引文预览**：`source_snapshots` + 侧栏高亮（Word/PDF 不自动下载）
- [x] **DACH Phase 1**：`sources/dach_registry.yaml` + `site:` 种子查询 + 90 天新鲜度

- [x] **Phase 2a (Wave 6)**：`private_debt_registry.yaml` + `investor_brief` + Entity/Signal 枚举 + European PD demo
- [x] **Wave 7**：`sources/catalog/`（36+ 信源）+ Source Router + Coverage 驱动 `research_loop`
- [x] **Phase 2b**：提取阶段 `signal_type`/`entity_type` + eval golden case（欧洲 PD）
- [x] **报告 UX**：引用弹窗 + editorial 排版（无 Entity 重复列）
- [ ] **搜全优先（Mode B）**：多查询扩展 + open_web 召回 + 抓取失败补救 — **当前主线**
- [ ] Phase 3：Watchlist + 周刊增量
- [ ] Always-on Fly API（**延后**；个人自用默认本机 Mode B，省钱更安全）
- [ ] `job_brief`（swiss-job-agent 集成，非主叙事）
- [ ] `search-demo.yiwang.dev` DNS（demo 公开展示）

## 设计哲学（为什么这样构建）

做架构决策时理解这些原则。详见 `product-description.md` 和 Obsidian `design.md`。

1. **确定引擎**：搜索策略、验证逻辑由代码（确定性）控制，LLM 只负责理解网页文本和表达——不替代代码做推理。这样行为可预测、可复现、可审计。
2. **每句可验证**：报告里每条事实标注来源 URL + 原文引用 + 置信度，点击 `[¹]` 侧栏展开原文高亮——用户可自行判断可信度。
3. **多跳搜索**：不是搜一次就回答。搜索 → 提取 → 交叉验证 → 发现盲区 → 追加搜索，直到覆盖度达标。
4. **反爬分层**：L1 文本抓取（Jina AI）→ L2 搜索 API（Tavily/Brave）→ L3 真浏览器（Playwright+CDP）→ L4 AI 导航（Browser-Use）。逐层升级，不浪费资源。

## Eval (Wave 1 quality gate)

```bash
# From repo root — requires LLM_API_KEY + TAVILY_API_KEY in backend/.env
backend/.venv/Scripts/python.exe -m eval.run
backend/.venv/Scripts/python.exe -m eval.run --case tavily-smoke
```


```bash
# 1. 后端
cd backend
cp .env.example .env    # 编辑填入 LLM_API_KEY
.venv/Scripts/python.exe main.py     # → :8000

# 2. 前端
cd frontend
pnpm dev                              # → :3000
```

### .env 需要

```
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1   # 或 DeepSeek
LLM_MODEL=gpt-4o-mini                     # 或 deepseek-v4-pro
```

## 行为约束（Cursor Rules）

1. **不删数据**：删除文件/代码前确认
2. **读 .env 不提交**：`.env` 在 `.gitignore` 里，绝不 `git add`
3. **先读 AGENTS.md**：每次新会话先读本文件
4. **读 product-description.md**：做任何设计决策前参考原始产品愿景
5. **设计文档在 Obsidian**：`D:\My Second Brain\10-PROJECTS\deep-search-agent\design.md` 有合并后的完整设计
6. **实现计划在**：`D:\My Second Brain\docs\superpowers\plans\2026-07-05-search-agent-phase1.md`

## 设计文档位置

| 文档 | 路径 | 内容 |
|------|------|------|
| 产品设计（合并版） | `D:\My Second Brain\10-PROJECTS\deep-search-agent\design.md` | 810 行完整产品设计 |
| 原始产品描述 | `./product-description.md` | 2026-06-21 原始设计哲学 |
| Phase 1 实施计划 | `D:\My Second Brain\docs\superpowers\plans\2026-07-05-search-agent-phase1.md` | 12 个 task 完整代码 |
| 项目索引 | `D:\My Second Brain\10-PROJECTS\deep-search-agent\_index.md` | Obsidian 项目入口 |
