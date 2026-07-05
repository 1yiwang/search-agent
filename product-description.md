# Search Agent —— 一个会深度调研的 AI Agent

> 项目定义文档。技术架构随开发推进逐步细化。
> 创建：2026-06-21

---

## 一句话定位

**不是「更快的搜索」，而是「经过验证的、结构化的、可追溯的答案」。**

ChatGPT/Gemini 能搜索，但它们的搜索是黑盒——你不知道它看了什么、漏了什么、哪条结论靠谱。Search Agent 做的是：明确定义搜索策略 → 多源交叉验证 → 结构化输出 → 标注每一条结论的置信度和来源。

---

## 我想解决的问题

### 用户视角：一次深度调研的实际流程

用户想研究一个问题，比如「2026 年最近六个月蓬勃发展的 AI startups」，他的真实需求是：

1. 发现候选名单（多源扫网）
2. 对每个候选验证关键信息（融资、团队、产品）
3. 去重、去噪音（PR 稿 vs 真实信息）
4. 按可比的维度整理成表格（融资额、阶段、领域、地域）
5. 知道每条信息的可信度（单一来源 vs 多源交叉验证）
6. 知道什么被遗漏了（Coverage 说明）

通用 LLM 最多做到第 1 步的单次搜索。剩余的差距就是 Search Agent 存在的理由。

### 通用 LLM 搜索的六个硬伤

| 硬伤 | 表现 | Search Agent 解法 |
|------|------|-------------------|
| **反爬/反 bot** | 高质量网站对 LLM 爬虫有防御，ChatGPT 搜索经常返回「无法访问」 | 真实浏览器指纹、CDP 协议、模拟人类行为节奏 |
| **单跳搜索** | 搜一次 → 回答。无法「搜到 A → 从 A 发现 B → 针对 B 深挖」 | 多跳研究：Plan → Search → Extract → Cross-check → Deepen |
| **非结构化输出** | 一段话回答，无法比对、排序、筛选 | 结构化提取：Pydantic schema → 表格/对比/排序 |
| **无状态** | 每次对话独立，无法追踪增量变化 | append-only 日志，对比「这次」和「上次」的差异 |
| **黑盒策略** | 你不知道它搜了什么、优先级、停止条件 | 用户可定义搜索策略 + 完整搜索链路日志 |
| **无法验证** | 你不知道哪条结论来自哪个源、是否交叉验证 | 每条结论标注来源 URL + 置信度 + 验证状态 |

---

## 核心设计哲学：LLM 在边缘，确定性引擎做大脑

这是从 Scheduling Agent 延续过来的核心架构决策，对 Search Agent 同样关键：

| 器官 | 职责 | 谁来做 |
|------|------|--------|
| 策略 | 制定搜索计划：先搜什么、找到什么后深挖什么、何时停止 | 确定性代码（Planner） |
| 执行 | 浏览器控制、搜索、翻页、提取 | 确定性代码 + Browser-Use |
| 解析 | 从网页内容提取结构化字段 | LLM（结构化提取） |
| 验证 | 交叉比对多个来源，标记冲突和一致 | 确定性代码 |
| 合成 | 排重、排序、生成报告 | 确定性代码 + LLM（表达） |
| 追溯 | 记录每一步搜索的来源和决策 | 确定性代码 |

**为什么？** LLM 对「搜了多少」「是否重复」「两个来源说的是否是同一家公司」这类逻辑判断非常不可靠。把 LLM 当搜索引擎的大脑 → 幻觉和遗漏无法控制。反过来：**代码做搜索策略和结构化处理，LLM 只在需要「理解网页内容」时介入。**

---

## ⭐ 核心架构（初步草案）

```
用户输入研究问题
  │
  ▼
Planner（确定性）
  ├── 拆解问题 → 子问题列表
  ├── 定义搜索策略：信源优先级、关键词、停止条件
  └── 生成 Research Plan → 用户审核/修改
  │
  ▼
Searcher（Agent Loop）
  ├── 对每个子问题：
  │   ├── 搜索（多引擎：Google / Brave / Tavily / Arxiv）
  │   ├── 浏览结果页，过滤相关链接
  │   ├── 访问目标页面（Browser-Use CDP 真实浏览器）
  │   ├── 提取结构化数据（LLM + Pydantic schema）
  │   └── 判断：是否需要深挖？→ 递归
  │
  ▼
Verifier（确定性）
  ├── 去重：不同来源的同一实体合并
  ├── 交叉验证：标记冲突/一致/仅单源
  └── 置信度评分
  │
  ▼
Reporter（确定性 + LLM 表达）
  ├── 结构化输出：表格/对比/排序
  ├── 每条结论标注来源 URL + 置信度
  ├── Coverage 说明：搜了什么、可能遗漏什么
  └── 搜索链路日志：完整可追溯
```

### 关键设计决策（与 Scheduling Agent 一致）

1. **Propose-only**：Planner 出搜索计划，用户确认后 Searcher 才执行。Agent 不替用户做「搜什么」的最终决策。
2. **Detector 注册表模式**：每种新的搜索/验证能力 = 一个纯函数插入注册表，不动 Loop、不动 Reporter。
3. **事件溯源**：每次搜索、每次提取、每次验证都是 append-only 事件，未来可回放分析。

---

## 📚 参考项目

### 核心参考：架构与深度研究

| 项目 | 学什么 | 路径 |
|------|--------|------|
| **DeerFlow（字节跳动）** | 多 Agent 编排做 Deep Research。Coordinator → Planner → Researcher → Coder → Reporter 的流水线。Plan-then-execute 模式。多搜索引擎 + 爬虫集成。结构化报告产出（时间线、对比表、置信度、方法论、来源列表）。 | `D:\Agent-self-education\deer-flow\` |
| **Browser-Use（微软教程）** | Browser-Use + Playwright + CDP 混合工作流。Agent 处理开放式导航（打开网站、关闭弹窗），确定性代码做结构化提取。Agent vs Actor 模式选择标准。 | `D:\Agent-self-education\ai-agents-for-beginners\15-browser-use\` |
| **Search & Summarize（GenAI Agents）** | 互联网搜索 + 总结的轻量入门实现。 | `D:\Agent-self-education\genai-agents\all_agents_tutorials\search_the_internet_and_summarize.ipynb` |

### 架构哲学参考：自己的项目

| 项目 | 学什么 |
|------|--------|
| **Scheduling Agent** | Agent Loop + 确定性引擎 + propose-only + 学习飞轮 + 事件溯源数据层。Search Agent 的架构哲学直接继承。 |
| **CV/作品集** | 从 `product-description.md` 到 `我的cv情况.md` 的 CL 素材转化流程。 |

### 可调研的额外资源（尚未入库）

- **OpenAI Deep Research**：封闭源但产品体验可参考（输出格式、用户交互模式）
- **Perplexity**：搜索型 AI 的产品设计参考（信源标注、追问引导）
- **LangChain OpenDeepResearch**：开源实现，与 DeerFlow 可做架构对比
- **BrowseComp / WebArena**：浏览器 agent benchmark，定义「做得好」的标准

---

## 技术栈（初步选型）

| 维度 | 候选 | 理由 |
|------|------|------|
| 浏览器控制 | Playwright + CDP | 真实浏览器指纹，反反爬 |
| AI 驱动导航 | Browser-Use | 自然语言驱动的浏览器操作 |
| 结构化提取 | LLM + Pydantic | Schema 约束输出格式 |
| 搜索引擎 | Tavily / Brave Search API / Google Custom Search | 多引擎互补 |
| 爬虫/内容提取 | Jina AI / Firecrawl | 整页 Markdown 转换 |
| 后端 | 待定（Python FastAPI 或 Node.js） | 取决于是否复用现有技术栈 |
| 数据层 | Supabase（Postgres + 事件溯源表） | 与 Scheduling Agent 一致 |
| 部署 | Vercel / Railway | 前后端分离 |
| LLM | Anthropic / OpenAI / DeepSeek | 多模型可切换 |

---

## 🗺️ 阶段规划

### 阶段 1 · 点火（MVP）

**目标**：跑通「一个问题 → 搜索 → 结构化结果」的完整链路。

- [ ] 单引擎搜索（Tavily 或 Brave）
- [ ] 单页面结构化提取（Pydantic schema）
- [ ] 基础结果去重
- [ ] Markdown 报告输出（表格 + 来源标注）
- [ ] 命令行或简单 Web UI

**产出物**：对一个问题返回结构化的搜索结果表，每条标注来源 URL。

### 阶段 2 · 深研

**目标**：多跳研究 + 交叉验证 + 置信度。

- [ ] Planner：自动拆解问题 → 子问题 → 搜索计划
- [ ] 多跳执行：搜到 A → 从 A 提取实体 → 针对实体深搜
- [ ] 多源交叉验证 + 冲突检测
- [ ] 置信度评分（High/Medium/Low + 理由）
- [ ] 搜索链路日志

**产出物**：类似 DeerFlow demo 的结构化深度研究报告。

### 阶段 3 · 产品化

**目标**：可用的 Web 产品 + 学习飞轮。

- [ ] Web UI：输入问题 → 审核计划 → 查看报告
- [ ] 增量研究：追踪同一主题随时间的变化
- [ ] 用户偏好学习：记住感兴趣的领域、偏好的信源
- [ ] 搜索策略自定义
- [ ] 部署上线

---

## 这个项目展示什么（写 CV 时用）

- **Agent 架构能力**：多 Agent 编排（Planner → Searcher → Verifier → Reporter），与 Scheduling Agent 形成互补——前者管时间，后者管信息。
- **务实的工程判断**：LLM 在边缘做解析和表达，确定性引擎做搜索策略和验证——和 Scheduling Agent 一脉相承。
- **深度理解搜索问题**：不是「接个 API 就完事」，而是对反爬、去重、交叉验证、置信度评估有系统方案。
- **端到端落地**：从浏览器控制、结构化提取、数据去重、报告生成，到部署上线。

---

## 开放决策

| # | 决策 | 选项 | 时机 |
|---|------|------|------|
| 1 | 做通用搜索还是聚焦垂直领域（如 AI startup 追踪、学术文献） | 先通用 MVP，再决定 | MVP 后 |
| 2 | 后端语言：Python（与 DeerFlow/Browser-Use 生态一致）还是 TypeScript（与 Scheduling Agent 一致） | Python（Browser-Use 生态强依赖）| 实现前 |
| 3 | 是否需要前端，还是先 CLI | CLI 先跑通链路 | MVP 阶段 |
| 4 | 单体 Agent 还是多 Agent 编排 | 先单 Agent 跑通，再拆多 Agent | 阶段 2 |
| 5 | 是否需要 Sandbox（Docker 隔离浏览器） | 阶段 2 引入 | 安全需求出现时 |

---

> 「做一个能搜索的 AI」不难——ChatGPT 已经做到了。做一个「让你信任搜索结果」的 AI，才是壁垒。
