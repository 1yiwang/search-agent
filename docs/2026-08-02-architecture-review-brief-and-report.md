# Search Agent 架构评审：Brief 方向 × 报告书写

> **日期：** 2026-08-02  
> **视角：** 产品 + 系统架构（可追溯研究 / 确定性引擎优先）  
> **范围：** `backend/brief.py`、`frameworks/`、`research_loop.py`、`coverage.py`、`query_expand.py`、`sources/{router,executor}.py`、`report_synthesis.py`、`report_outlines/`、`reporter.py`、`frontend/app/brief/page.tsx`、`frontend/components/ReportView.tsx`、`eval/`  
> **前提：** Wave 12f/12g UI（Signal Flag）可接受；当前真正的质量短板在 **方向契约** 与 **成文契约**。

---

## 0. 总判

Search Agent 在「搜得到」一层已经扎实（catalog / router / coverage / multilang / rank_fetch）。但 **Brief 方向** 与 **报告成文** 两层，目前有大量质量是靠 **硬编码中文模板 + 正则修补** 撑出来的：

- 瑞士电信 / 瑞士跨境电商之所以「像 Gemini」，主要是因为 `brief._instruction_from_phase` 里写死了 `telecom_zh` / `ecom_zh`；换日本便利店供应链、巴西支付牌照，立刻退化成通用句式。
- 报告侧：`reporter` 仍硬编码英文骨架（`## Conclusion` / `## Arguments`）；thesis 降级路径是「两条事实首句用分号拼接」——不是判断。
- 更严重的是三处 **机制断裂**：**用户批准的计划 ≠ 实际执行的检索 ≠ 报告章节结构**。中文 coverage 分词失效、seed query 被 executor 截断后无条件清空、方向缺口扩维被抹平。

这直接违背产品哲学：**确定性引擎做策略，LLM 只负责理解与表达**。修复方向不是继续加正则，而是把「方向」做成贯穿全链路的一等公民（`direction_id` + 预算 + query + 事实归属 + 报告槽位），并把 LLM 自由度收在「表达」与「可判定的生成」上，配上 L1/L2 离线 eval。

---

## 1. 现状地图

```
选题 (+ depth≠fast) → /brief
  → POST /api/brief/clarify     # 可能用弱 BYOK 模型
  → POST /api/brief/generate    # LLM + _parse_brief_payload 三层修补 / 模板重建
  → revise / confirm
  → POST /api/brief/research/stream
       → run_research_loop(brief)
            hop0: brief_seed_queries(≤18) → pending_open_queries
            route_sources(topic)          # brief 不可见；site 约占预算 ~70%
            execute → 实际只跑少量 open query
            pending_open_queries = []     # 剩余丢弃
            extract_facts(topic)          # 无 direction_id
            evaluate_coverage(brief_dims) # 中文关键词常恒不命中 → score≈0
            expand_queries(gaps)          # 中文常被抹平 → 缺口撞车
       → synthesize_report
            Pass A EvidenceDraft → Pass B write (thesis + ≤5 arguments)
       → generate_report → 英文 markdown 骨架
       → ReportView（前端中文标签映射）
```

**一句话：** brief 对下游的真实控制力，目前主要是 `deprioritize` 与章节标题；**检索预算、query 选择、事实归属** 三件最重要的事没有被方向真正管住。

---

## 2. Brief 方向生成 — 问题诊断

### 2.1 【P0】质量来自硬编码模板，不是 prompt（伪泛化）

`_parse_brief_payload` 多层 fallback 最终落到 `_instruction_from_phase`。其中 `telecom_zh` / `ecom_zh` 几乎就是用户看到的「完美计划」本体；`BRIEF_SYSTEM_PROMPT` 的金标准范例也是同一套电商文案。

**后果：** 命中模板的题永远好看；未命中题退化成「调研「{topic}」所在市场…」——中文版的 English skeleton。每加一个垂直就要加一段 Python 字典，不可扩展。

### 2.2 【P0】校验器与硬规则不对齐

Prompt 立了多条硬规则；`_is_good_instruction` 实际主要查：长度、无英文骨架、中文题含中文、动词白名单。

**漏检：** queries 必须含实体；title 短标签；`research_goal` 与 `direction_detail` 语义不同（代码里常 `goal = detail`）。  
**误伤：** 动词白名单过窄 → 合格中文指令被判失败 → 更频繁落模板 → 「方向都一个味」。

### 2.3 【P0】方向数与检索预算脱钩

`brief_seed_queries` 可产出 ≤18 条并 round-robin；但 executor 的 open 预算很小，且 `research_loop` 在执行后 **无条件清空** `pending_open_queries`。结果：6 条方向里往往只有前 2–3 条在 hop0 真正被搜到；后面的「监管 / 物流 / 风险」靠坏掉的 coverage 侥幸回补。

### 2.4 【P1】Brief 对 Source Router 不可见

`route_sources` 不看 brief。catalog 命中时 site/direct 吃掉大部分预算，**用户批准的方向对这 ~70% 预算零影响**。

### 2.5 【P1】澄清用弱模型；英文 fallback

Clarify 用 BYOK `llm_model`；brief generate 才走 `get_brief_model()`。资源分配倒置。`_fallback_questions` 全英文。

### 2.6 【P0】中文 brief 的 coverage 判定失效 → 多跳盲跑

`_brief_coverage_dims` / `_goal_keywords` / 启发式 draft 用空格分词切中文 → 一个超长 token → 对英文事实 corpus 几乎永不命中 → `score≈0` → 循环只靠 hop/预算截停；`brief_direction_queries` 反复补同一批方向。

### 2.7 【P0】缺口 → 下一跳 query 被抹平

中文重写分支把汉字抹掉再拼 pivot，不同缺口撞成同一条 query，再被 `seen_queries` 去重。brief 的 `phase_id` 也不在 PD/telecom 的 `DIMENSION_*` 映射里。

### 2.8 【P1】「不重启就飘」的机械根因

- frameworks / outlines 的 `lru_cache` + uvicorn 默认不 reload YAML  
- 进程内 brief session，reload 丢会话  
- 弱模型白名单不全 → 仍可能用 chat/mini 生成方向再被模板盖住  

### 2.9 【P1】revise 全量重写；无逐条锁定

用户改一条可能毁掉其余已满意条目。前端只有一个总反馈框。

### 2.10 【P1】方向质量几乎无自动化 eval

`test_direction_quality.py` / `test_brief.py` 有少量单测；golden eval 不测 brief 文案质量。Wave 12e 标 Done 但缺少可回归门禁。

---

## 3. Brief 方向生成 — 改进建议

### P0-1｜Direction Contract（方向一等公民 + 预算）

**目标：** 批准的 N 条方向，每条都必须获得可验证的检索份额。

**改什么：**

- `BriefDimension` 增加：`direction_id`、`budget_weight`、`entities: list[str]`、`must_answer: list[str]`
- hop0 按方向切片执行 open search，结果打 `direction_id`
- executor 返回 `leftover_queries`；禁止无条件清空 pending
- `route_sources` 注入 brief 方向与实体；site 预算按方向权重切分

**验收：**

- `direction_coverage ≥ 0.9`（每方向至少 1 条实际 query）写入 metadata + SSE `direction_budget`
- deep 档 6 方向跑完，`topics_searched` 覆盖全部 `direction_id`

### P0-2｜修复中文分词（coverage / expand / heuristic draft）

**改什么：** `backend/text_tokens.py`（中文 2–4gram + entities）；三处统一调用。缺口扩维用 entities，不抹光中文。补齐 brief `phase_id` → info_type / open-only 映射。

**验收：** 中文 brief + 含 Swisscom/BAKOM 的英文 facts → `coverage.score > 0`；两不同缺口 → 字面不同的 open query。

### P0-3｜「判定 + 定向重生成」取代「正则代写」

**改什么：**

- `_is_good_instruction` → rubric，返回 `(ok, reasons[])`
- 流程：生成 → 判定 → **只重写失败条** → 再判定 → 仍败才模板
- `telecom_zh` / `ecom_zh` **移出代码**，进 `frameworks/examples/*.yaml` 仅作 few-shot
- 落模板必须 SSE `brief_fallback_used` + UI 提示

**验收：**

- 离线 brief eval：`fallback_rate ≤ 10%`
- 中文选题：`direction_detail` / `title` / `research_goal` 中英文 phase title 出现次数 = 0
- queries 不得为 `topic + English phase title`；每条 `entities ≥ 2` 且至少 1 个进 queries

### P0-4｜消除「要重启才正常」

mtime 缓存 frameworks/outlines；`reload_includes` 含 `*.yaml`；brief session 落盘；`get_brief_model` 白名单 + 响应 `model_used`。

### P0-5｜Brief 离线 eval

`eval/brief_cases.yaml`（≥10 题，跨域）+ `eval/brief_validate.py`；进 CI / progress ritual。

### P1｜clarify 强模型 + 中文 fallback；逐条编辑/锁定；方向计划 vs 实际检索对照表

### P2｜模板库化 few-shot；删除代码内垂直字典

---

## 4. 报告总结 / 结论 — 问题诊断

### 4.1 【P0】报告骨架仍是英文

`reporter._generate_markdown` 硬编码 `## Conclusion` 等；只有 ReportView 做中文标签。静态 HTML / markdown 导出仍是英文骨架。

### 4.2 【P0】开头元叙述与 thesis 禁令自相矛盾

报告头写 `N facts from M URLs`；同时禁止 thesis 出现「整理了 N 条」。情报简报不应以过程指标开场。

### 4.3 【P0】thesis 常是事实拼接，且语言可能混杂

`_substantive_thesis` 拼高置信事实首句；抽取 prompt 未强制「fact 用选题语言」。中文报告可出现英文结论。且「拼接 ≠ 判断」。

### 4.4 【P0】章节数与批准方向数不一致

写作结果 `arguments[:5]`；第 6 方向静默消失。空槽「证据不足」不说明「没搜还是搜了没有」。

### 4.5 【P1】writing_goal 退化成同一句重复

`goal = detail` 后再 `f"{goal}. {detail}"` → 写作合同为空。

### 4.6 【P0】引用绑定是软约束

无引用 claim 会被自动补 `fact_indices`——字面「先写再配引用」。不校验 body 中 `[n]` 是否属于该 slot 的 Pass A 分配集；数字不回溯原文。

### 4.7 【P1】Pass A 中文启发式归属近似随机；facts 无 `direction_id`

检索时已知方向信息，抽取后丢掉，再让 LLM 猜。

### 4.8 【P1】Limits 塞技术噪音；Signal ledger 对 market_entry 是错误抽象

### 4.9 【P1】成文用弱模型 + 静默降级；facts_json 传两遍浪费 token

---

## 5. 报告总结 / 结论 — 改进建议

### 推荐报告骨架（Report Contract）

| # | 章节 | 中文标题 | 字数 | 契约 |
|---|------|----------|------|------|
| 0 | Thesis | 结论 | 60–120 | 判断式：方向 + 量化锚点 + 限定条件；禁元叙述 |
| 0b | Takeaways | 要点 | 3–5×≤40 字 | 断言 + `[n]` |
| 1..N | Arguments | **与批准方向 1:1** | 150–300 | 论点句 → 证据 → 反面/边界 → 对本题含义；答 `must_answer` |
| N+1 | So what | 落地含义 | 120–200 | 跨方向：可行性、优先路径、下一步验证 |
| N+2 | Limits | 局限 | 60–150 | 哪一方向不足 + 为什么 + 补什么源（人话） |
| N+3 | Sources | 信源 | — | URL 去重（已有） |
| 附 | Coverage / 检索日志 /（仅 PD）Signal ledger | 附录 | — | 默认折叠 |

### P0-6｜双语骨架 + 去掉头部元叙述

`labels.yaml`；中文题 markdown 中不得出现 `## Conclusion|Arguments|Limits|…`。元数据移文末。

### P0-7｜thesis = 判断 + 语言一致 + quality gate

抽取：`fact` 用选题语言，`quoted_text` 保原文。thesis 不过 gate → 定向重写 → 再 fallback（判断式模板，非双事实拼接）。

### P0-8｜`enforce_citation_integrity`（硬门禁）

- `[n]` ⊆ 该 slot 的 draft `fact_indices`  
- 禁止自动补引用；无引用 claim 降级或丢弃  
- 数字必须能在被引 `quoted_text`/`fact` 中找到  
- 引用密度下限（如每 150 字 ≥1）

### P0-9｜章节数 == 方向数；空槽结构化诚实产出

写出：已执行 queries、失败原因、建议信源——把「没写出来」变成可追溯诚实产出。

### P0-10｜成文用强模型；`synthesis_degraded` 可见

### P1｜每节写作合同（must_answer / expected_evidence / forbidden）+ 中文范文；Limits 人话；facts 带 `direction_id` 确定性落槽

### P2｜market_entry 去掉 signal ledger；长报告目录锚点；「复制中文 Markdown」

---

## 6. 跨层架构：确定性引擎 vs LLM

| 器官 | 现状 | 应该 |
|------|------|------|
| 预算 / 停止 | LLM router + 丢弃的 seed | **确定性** `plan_direction_budget()` |
| 方向→query | expand 抹平中文 | **确定性** entities + 模板；LLM 只补实体 |
| 事实归属方向 | Pass A 猜 | **确定性** 检索时打 `direction_id` |
| 网页理解 | LLM ✅ | 保持 |
| 方向文案 | 代码硬编码模板 ❌ | **LLM 生成 + 代码判定重试** |
| 结论/正文 | 弱模型 LLM | **强模型 LLM** + 确定性引用校验 |
| 引用/数字/语言 | 几乎无 | **确定性硬门禁** |

**一句话：代码不该替 LLM 写字，LLM 不该替代码做账。**

### Eval 三层

| 层 | 内容 | 联网 |
|----|------|------|
| L1 | brief 方向 rubric / fallback / 实体密度 | 否 |
| L2 | 固定 facts+brief → thesis/章节/引用完整性 | 否 |
| L3 | 现有 golden + `direction_coverage` | 是 |

### 成本

- facts_json 勿双传；Pass A 增量  
- hop0 router 可确定性，缺口再 LLM  
- clarify/brief/write = 强模型；extract/router = 便宜模型（现状常反着）

---

## 7. 建议落地顺序（2–3 周）

### 第 1 周 — 止血：批准的计划真被执行

1. `text_tokens` + 修 coverage/expand/heuristic 中文分词  
2. frameworks/outlines 缓存与 YAML reload；session 落盘；`model_used`  
3. Direction Contract + leftover 回填 + `direction_budget` SSE  
4. **验收：** 中文 deep 6 方向每条 ≥1 query；coverage 单调上升；`direction_coverage ≥ 0.9`

### 第 2 周 — 质量契约：方向生成 + 报告骨架

1. rubric + 定向重生成；模板移 YAML few-shot  
2. `eval/brief` 跑绿  
3. reporter 双语骨架；删头部元叙述；So what；thesis gate；章节数==方向数  
4. **验收：** 中文 markdown 无英文骨架标题；thesis 中文非 meta

### 第 3 周 — 硬门禁 + 可信度

1. `enforce_citation_integrity`；synthesis 强模型 + degraded 可见  
2. `eval/writing` + `backend/tests`  
3. clarify/逐条锁定；写作合同；`direction_id` 落槽  
4. ROADMAP 记 Wave 12h：Direction Contract + Report Contract + L1/L2 eval

**不可谈判项：** 第 1 周 Direction Contract + 第 3 周引用完整性。其余可后排。

---

## 附录 A — Brief Generate System Prompt（草案）

```
你是资深行业研究策划。唯一任务：把用户选题写成「Gemini 搜索概览」风格的研究计划 JSON。

【合格计划】
5–6 条编号方向，每条可直接拿去搜索：
- 动词开头（调研/梳理/评估/研究/分析/对比/探索/量化/复盘）
- 点名具名平台/监管/品类/公司/指标
- 6 条彼此不可替代

【每条字段】
- title：≤12 字，选题语言
- direction_detail：30–120 字可执行指令，≥2 具名实体
- research_goal：答完应得到什么产出物（与 detail 措辞不同）
- entities：≥2 具名实体
- must_answer：1–2 个具体问题
- queries：2–4 条可搜串，每条至少含一个 entity；可中英德混用

【禁止】
英文栏目名（Demand segments… / Rough opportunity sizing…）；
「选题 + 英文标题」查询；无实体空话；元叙述。

【硬规则】
输出语言 = 选题语言。覆盖清单只给角度，禁止粘贴其英文标签。
除非用户要求，不研究国家 GDP/宏观百科。
overview_markdown = (1)(2)… 的 direction_detail 列表。

【范例】{{few_shot_examples}}

只返回合法 JSON。
```

**定向重写 user 消息：**

```
以下方向未通过校验，请只重写这些条目，其余字节级不变。
不合格与原因：{{failures}}
保持 phase_id/priority。只返回被重写条目的 JSON 数组。
```

---

## 附录 B — Report Write System Prompt（草案）

```
你是行业研究报告主笔。只负责【表达】：事实、引用编号、章节结构已固定。不得增删事实、不得引入外部知识。

【语言】与选题一致。中文题 → 全文中文（含标题）。quoted 原文可保留原语言。

【结构】
1. thesis（60–120 字）：判断，非摘录。必须含：方向性判断 + 量化锚点 + 限定条件。
   禁止：本报告整理了N条 / 来自M个来源 / 综上所述 / 本文将探讨
2. key_takeaways：3–5 条，每条 ≤40 字 + [n]
3. arguments：数量 = slot 数，顺序一致。每节 150–300 字：
   论点句 → 关键证据[n] → 反面/边界 → 对本题含义
   必须回答 must_answer；无事实则写「本方向未获得可引用证据」+ 缺什么源，不编造
4. so_what（120–200）：可行性、优先路径、下一步验证
5. limits（60–150）：哪一方向不足、为什么、补什么源（人话）

【引用】只能用该 slot 分配到的编号；每 claim ≥1 引用；数字必须来自被引事实。
【禁用】本报告 / 本节将 / 我们搜索了 / 根据以上事实 / 综上所述 / 值得注意的是 / 总的来说

只返回合法 JSON。
```

---

## 附录 C — 相关文件速查

| 主题 | 路径 |
|------|------|
| Brief 生成/修补 | `backend/brief.py` |
| Framework 清单 | `backend/frameworks/*.yaml` |
| 研究循环 | `backend/research_loop.py` |
| 覆盖度 | `backend/coverage.py` |
| Query 扩维 | `backend/query_expand.py` |
| 执行/预算 | `backend/sources/executor.py` |
| 两阶段成文 | `backend/report_synthesis.py` |
| Markdown 骨架 | `backend/reporter.py` |
| Outline/slots | `backend/report_outlines/` |
| Brief UI | `frontend/app/brief/page.tsx` |
| 报告 UI | `frontend/components/ReportView.tsx` |
| 方向单测 | `backend/test_direction_quality.py` |

---

*本文由架构评审整理，作为 Wave 12h（Direction Contract + Report Contract）的输入文档。实施时以 ROADMAP Step 勾选为准。*
