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
| 搜索 | DuckDuckGo（免费，易限流）→ 计划切 Tavily | `backend/search.py` |
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
│   ├── search.py              ← 搜索 + 网页抓取（DuckDuckGo / httpx）
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
| GET | `/api/research/{slug}` | 获取已完成的报告 |

### 请求/响应格式

**POST /api/research** — 入参 `{topic: str, max_sources: int}`，出参 `ResearchReport`（见下文模型）

**POST /api/research/stream** — 入参同上，SSE 流式返回，事件类型（与 `agent.py` + `main.py` 一致）：

| 事件 | 触发时机 | payload |
|------|---------|---------|
| `search_start` | 开始研究 | `{topic, max_sources}` |
| `search_complete` | 搜索完成 | `{results_found}` |
| `dedup_complete` | URL 去重完成 | `{before, after, removed}` |
| `extraction_start` | LLM 开始提取 | `{sources_with_content}` |
| `extraction_complete` | 提取完成 | `{facts_extracted}` |
| `fact_dedup_complete` | 事实去重完成 | `{before, after}` |
| `report_start` | 开始生成报告 | `{fact_count}` |
| `report_complete` | 报告对象生成 | `{slug, citation_count}` |
| `report_ready` | 部署完成（main.py） | `{slug, topic, html_url, fact_count, citation_count}` |
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

**Phase 1 MVP ✅ 完成**（2026-07-05，16 commits）

- [x] 完整链路可跑通
- [x] SSE 实时流式进度（10 种事件类型）
- [x] 搜索页 + 报告页（引文侧栏点击验证）
- [x] 静态 HTML 部署
- [x] DeepSeek v4 Pro API 已调通
- [x] Review 修复：语法错误、XSS 风险、未使用 import、StreamRequest 验证

- [ ] **搜索问题**：DuckDuckGo 持续限流（202 Ratelimit），需切 Tavily/Brave → [ROADMAP.md](ROADMAP.md) Step 15
- [ ] Phase 2：Meta 深度规划模式（5 步向导：输入 → 反问澄清 → 生成方案 → 审核 → 执行）
- [ ] Phase 3：多用户（Gmail OAuth + 用户自带 API Key）
- [ ] Phase 4：向量知识库 + Obsidian 集成
- [ ] 推 GitHub + 部署 Vercel

## 设计哲学（为什么这样构建）

做架构决策时理解这些原则。详见 `product-description.md` 和 Obsidian `design.md`。

1. **确定引擎**：搜索策略、验证逻辑由代码（确定性）控制，LLM 只负责理解网页文本和表达——不替代代码做推理。这样行为可预测、可复现、可审计。
2. **每句可验证**：报告里每条事实标注来源 URL + 原文引用 + 置信度，点击 `[¹]` 侧栏展开原文高亮——用户可自行判断可信度。
3. **多跳搜索**：不是搜一次就回答。搜索 → 提取 → 交叉验证 → 发现盲区 → 追加搜索，直到覆盖度达标。
4. **反爬分层**：L1 文本抓取（Jina AI）→ L2 搜索 API（Tavily/Brave）→ L3 真浏览器（Playwright+CDP）→ L4 AI 导航（Browser-Use）。逐层升级，不浪费资源。

## 本地运行

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
