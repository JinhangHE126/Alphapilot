# AlphaPilot HK Fintech AI Engineer 竞争力优化方案

> 本文档说明 AlphaPilot 在面向香港 Fintech（投资研究 / AI 平台 / Agentic 系统）岗位投递时的**现状评估、优化优先级与执行计划**。  
> 与 [文档提取与RAG功能.md](./文档提取与RAG功能.md) 互补：后者聚焦 RAG 技术实现与 Phase 1–4 落地；本文聚焦**整体竞争力提升**与面试展示策略。  
> **工程排期与任务拆解**见 [HK-Fintech-AI-开发方案.md](./HK-Fintech-AI-开发方案.md)。  
> 相关架构说明见 [alphapilot/Docs/architecture.md](../alphapilot/Docs/architecture.md)。

---

## 1. 现状评估

### 1.1 核心优势（已有差异化）

AlphaPilot 的基础工程能力较强，以下体系在 HK Fintech AI Engineer 岗位中属于**加分方向**：

| 能力 | 说明 |
|------|------|
| Evidence Packet 前置 | Builder 统一采集证据，Agent 不各自调工具，可控性强 |
| 多层防幻觉 | 输出等级门控 + Guard 硬规则（含文档 grounding L1/L2/L3） |
| 双轨证据 | `structured_facts` + `document_evidence`，结构化与定性并行 |
| 文档感知 RAG | 公开文档自动摄取 + 用户私有上传 + hybrid 检索 + session 隔离 |
| 多 Agent 协作 | Bull vs Bear 辩论、Strategy 综合、14 Agent 分级路由 |

### 1.2 当前短板（「工程强、分析效果一般」）

| 短板 | 表现 | 根因（代码层） |
|------|------|----------------|
| Document Evidence 质量不足 | TSLA 等案例暴露 MD&A、Risk Factors、表格召回差 | 表格堆在文末；`chunk_id` 无语义；检索无 section boost（见 §10.2） |
| 报告洞察密度低 | Recommendation 输出冗长、复述各 Agent | prompt 要求「逐智能体详细拆解」，与 Strategy 职责重叠 |
| Audit Trail 不完整 | ~~面试追问「引用可追溯吗」时证据链断档~~ → M3：`analysis_citations` 表 + History API + 前端 CitationsPanel | 有 `analysis_id` / events；`cited_chunk_ids` 已持久化并在分析页/历史详情展示 |
| 缺高质量 Demo | 验收脚本偏工程链路，缺可展示的分析案例 | Phase 1–4 完成但无「主展示案例」 |

**结论**：项目已可用于投递，但若想显著提高 HK Fintech AI Engineer 命中率，需**有针对性地放大亮点、补齐上述四项**，而非全面 perfection。

---

## 2. HK Fintech 岗位看重什么

香港 Fintech（尤其投资研究、量化、AI 平台方向）通常优先考察：

1. **可靠性 & 可控性** — Hallucination 控制、Grounding、Audit
2. **RAG + Agentic 实际落地** — 非 demo 级拼装，有 production 思维
3. **非结构化数据处理** — 金融 PDF、年报、表格
4. **合规叙事** — SFC GenAI 高风险场景的可解释性与证据追溯

AlphaPilot 在第 1、2 点已有基础；第 3、4 点需在 Phase 1 重点补强。

---

## 3. 优化优先级

### 3.1 High Priority（强烈建议先做）

| 优化项 | 具体建议 | 理由 | 预计收益 |
|--------|----------|------|----------|
| 提升 Document Evidence 质量 | 加强年报解析（MD&A、Risk Factors）；表格提取以 pdfplumber 为默认可用路径；section 感知分块与检索 boost | 当前最大短板；TSLA 案例已暴露 | 非常高 |
| 补全 Audit Trail | 最终报告落库时记录引用的 `chunk_id` / `[doc:N]` 列表（SQLite 即可） | Fintech 看重可解释性与合规 | 高 |
| 优化 Recommendation Agent | 减少复述；增加跨 Agent 综合与矛盾分析；突出 Document Evidence 作用 | 报告冗长、洞察密度不够 | 高 |
| 准备 1–2 个高质量 Demo | 用内容完整的年报跑通 upload/抓取 → 分析 → 报告，作为主展示案例 | 面试最能体现项目价值 | 非常高 |

### 3.2 Medium Priority（值得做）

| 优化项 | 具体建议 | 理由 |
|--------|----------|------|
| 受控工具调用 | Fundamental / Risk / Strategy 可选调用文档检索（非全面 `tools=[]`） | 展示「自主性 vs 可控性」权衡；**须保持 Evidence Packet 为主路径** |
| 简单评估指标 | Grounding 通过率、文档引用准确率、证据充分性评分等 | 体现 production 思维 |
| 合规与风控叙事 | README / 面试中强调 SFC 高风险 use case 应对 | HK fintech 很吃这一套 |
| 用户上传体验 | 上传前确认 + 免责声明 | 产品思维 |

### 3.3 Low Priority（后期再做）

- A/B 测试框架
- 完整监控与可观测性
- 更复杂的多 Provider Fact Store 冲突检测
- Embedding 模型升级（当前 `all-MiniLM-L6-v2` 够用）

与 [文档提取与RAG功能.md §10.2](./文档提取与RAG功能.md#102-与-proposal-原文的差距未做或简化) 未实现项一致，不必在投递前全部完成。

---

## 4. 具体执行计划

### Phase 1（建议 1–2 周）— 快速提升展示价值

**推荐执行顺序**（相对原清单微调：先修证据质量，再跑 Demo）：

```
1. Document Evidence 处理增强
   ↓
2. Recommendation Agent prompt 重构
   ↓
3. Audit Trail 简单版（与 report 落库同步）
   ↓
4. 高质量 Demo 全流程
```

#### 4.1 Document Evidence 处理

**现状**（`alphapilot/knowledge/pdf_parser.py`）：

- pdfplumber 已实现，但是作为 camelot 回退，且为 optional 依赖
- 表格统一 append 到 `## Extracted Tables` 末尾，与章节脱节
- `document_chunker.py` 的 `chunk_id` 为 `{doc_id}_chunk0001` 格式，无语义

**待做**：

| 任务 | 文件 / 模块 |
|------|-------------|
| pdfplumber 作为默认可用表格路径（demo 环境必装） | `pdf_parser.py`、`requirements-optional.txt` |
| 表格尽量挂到对应 section，而非全部堆在文末 | `pdf_parser.py`、`document_chunker.py` |
| SEC Item 7 / Item 1A、港股 MD&A / 风险因素 section 识别 | `document_chunker.py` |
| 检索对 Risk Factors / MD&A 做 boost | `rag/retriever.py` |
| 语义化 `chunk_id`（如 `{doc_id}_RiskFactors_p45`） | `document_chunker.py` |

#### 4.2 Recommendation Agent 优化

**现状**（`alphapilot/agents/recommendation_agent.py`）：

- Section「一、多维度综合分析」要求对每个 Agent **逐条详述**，导致与上游输出大量重复
- Strategy Agent 已承担综合与辩论选边，Recommendation 应聚焦**最终交付层**

**目标结构**（prompt 重构方向）：

```markdown
## 一、核心洞察（Executive Synthesis）
3–5 条跨 Agent 综合结论，非逐 Agent 复述

## 二、跨智能体矛盾与倾向判断
识别 Market / Fundamental / News / Debate / Risk 之间的张力，给出倾向及理由

## 三、文档证据支撑的定性判断
2–3 条由 [doc:N] 支撑的洞察（管理层展望、风险披露等）

## 四、个性化投资建议
（保留，结合 user_profile）

## 五、风险警告 & 行动计划
（保留，关联 Agent 依据 + Document Evidence）
```

#### 4.3 Audit Trail（简单版）

**现状**：

- SQLite 已有 `analysis` 表、`analysis_events` 表
- Guard 已校验 `[doc:N]` ↔ `document_evidence` 下标
- **缺失**：每次分析持久化「实际引用了哪些 chunk」

**待做**：

- 在 report 落库时解析最终输出中的 `[doc:N]`，映射为 `chunk_id` 列表
- 新增字段或表，例如 `analysis_citations(analysis_id, chunk_ids JSON, evidence_snapshot JSON)`
- 可选：History API 返回 citations，便于前端或面试演示

#### 4.4 高质量 Demo 案例

**标的建议**：

| 市场 | 推荐 | 说明 |
|------|------|------|
| 美股 | AAPL / MSFT | 10-K 结构清晰，MD&A / Risk Factors 完整 |
| 港股 | 0700.HK / 9988.HK | 若 HKEX 抓取 + 上传链路稳定 |

**流程**：

1. 修复解析与分块 → ingest 完整年报
2. 跑 `full_analysis` 全链路（含 Bull vs Bear → Recommendation → Guard）
3. 保存 report + audit log
4. README 中放 2–3 页摘要截图或关键段落（含 `[doc:N]` 引用示例）

> TSLA 适合测工程链路，但 10-K 体量大、表格复杂，更适合作为**压力测试**而非主 Demo。

---

### Phase 2（面试前约 1 周）— 包装与叙事

#### 4.5 README 重点突出

- Evidence Packet + 多层防幻觉（核心亮点）
- 文档感知 RAG 完整实现（上传 + 自动抓取 + 私有隔离）
- Bull vs Bear 辩论机制
- 生产可靠性：Grounding、Audit、输出等级门控

#### 4.6 面试常见问题准备

| 问题 | 回答要点 |
|------|----------|
| 为什么 Evidence Packet 前置，而不是让 Agent 自己调工具？ | 统一证据源、避免 Agent 间矛盾、Guard 可确定性校验、符合 SFC 可追溯要求 |
| 文档质量差怎么办？ | 冷启动降级、`document_evidence=missing` 时拒答或 limited；Guard L3 无文档时升 issues |
| 如何平衡 Agent 自主性与系统可控性？ | 默认 `tools=[]` + Packet 消费；可选受控补充检索；输出等级门控 |
| 对 SFC GenAI 监管的理解？ | 高风险 use case 需 human oversight、证据 grounding、audit trail、免责声明 |

---

## 5. 与现有文档的对应关系

| 本文档 Phase 1 项 | 文档提取与RAG功能.md §10.2 差距 | 状态 |
|-------------------|----------------------------------|------|
| Document Evidence 质量 | §3.2 解析、§9.3 表格、§3.4 section 预过滤 | ⚠️ 部分实现 |
| Audit Trail | §5.1 完整 audit trail | ✅ M3：`analysis_citations` + History API + 前端展示 |
| Recommendation 优化 | （非 RAG 文档范围） | ✅ M4 Executive Synthesis |
| Demo 案例 | Phase 1–4 验收偏工程 | ✅ M5 `Docs/demo/` |
| 上传确认 / 免责声明 | §4 上传、§5.1 合规 | ✅ M6 前端 + API `consent_at` |
| A/B / 监控 / BGE embedding | §6 Phase 4、§7 成功指标 | Low，后期 |

---

## 6. 最终建议

**投递前优先完成以下四项**（完成后竞争力从「中上」→「比较有竞争力」）：

1. ✅ 一个内容完整的 Demo 案例（最重要）
2. ✅ Document Evidence 解析质量提升
3. ✅ Recommendation Agent 输出更有洞察力
4. ✅ 简单的 Audit Trail

不必等待 A/B 框架、完整 observability 或 embedding 升级；当前瓶颈在**证据质量、综合层输出、可展示闭环**，而非模型或基础设施。

---

## 7. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-28 | 初版：基于项目现状与 HK Fintech AI Engineer 岗位需求整理优化优先级与 Phase 1/2 计划 |
| 2026-06-29 | Audit Trail 前端补全：`CitationsPanel` + 分析页/历史详情展示 `chunk_ids`；流式分析每次完成均落库 citations |
