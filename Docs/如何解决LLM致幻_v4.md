# 股票分析系统冷启动防幻觉优化方案

> **副标题**：Hybrid RAG + Evidence Packet 的可审计证据约束机制
>
> **版本**：v4.0
>
> **日期**：2026-05-31
>
> **作者**：Jinhang HE
>
> **修订重点**：v4 在 v3 基础上补全了架构衔接、Evidence Packet 生成链路可信性、冲突处理矩阵、分库合并策略、Guard 硬规则、工程工期重估、性能预算和逃生舱设计等关键缺口。

---

## 1. 问题背景与目标边界

现有 RAG 机制在知识库覆盖充分时可以降低模型自由发挥的风险；但当目标股票在知识库中没有历史资料、财报、公告或研报时，系统容易退化为纯 LLM 生成。此时模型可能把行业常识、过期信息或相似公司信息误当作目标公司的事实。

本方案的核心目标不是"消灭幻觉"，而是建立一套可审计的证据约束流程：

- 冷启动时先采集数据，再生成分析。
- 所有关键结论必须能追溯到 Evidence Packet 中的字段级证据。
- 证据不足时，系统必须降级输出数据摘要、缺失清单和风险提示，不能生成强投资判断。
- 冷启动采集结果可以沉淀到知识库，但必须带有效期、来源、版本和 `as_of_date`，不能被视为永久有效事实。

---

## 2. 根因分析


| #   | 问题                   | 当前影响                      | 需要补齐的能力                        |
| --- | -------------------- | ------------------------- | ------------------------------ |
| 1   | RAG 检索为空或低质量         | Agent 缺少可靠上下文，容易自由推理      | 检索结果需要返回 score、source、metadata |
| 2   | 工具输出不是统一证据对象         | 多个 Agent 可能基于不同上下文得出不一致结论 | 引入统一 Evidence Packet           |
| 3   | PDF / API 数据缺少字段级来源  | 无法判断结论是否真的有依据             | 每个关键字段保留来源、日期、单位和置信度           |
| 4   | 知识库没有时效治理            | 旧价格、旧新闻、旧财报可能污染后续分析       | 入库时记录 TTL、版本、数据类型和更新时间         |
| 5   | Guardrail 偏 prompt 化 | 模型仍可能越过约束生成建议             | 输出前增加结构化证据充分性检查                |


---

## 3. 与现有架构的衔接方案（v4 新增）

### 3.1 当前架构回顾

当前系统是 LangGraph Supervisor 模式下的 12-Agent 工作流，核心分析链为：

```
Orchestrator → [Market | Fundamental | News] (并行) → Strategy → Risk → ... → Guard → END
                    ↓
              各自独立调用 retrieve_knowledge + 领域工具
```

### 3.2 推荐插入方案：Supervisor 前置节点

将 Evidence Packet 构造作为 **Orchestrator 路由前的必经节点**：

```text
用户请求
  │
  ▼
Ticker / 意图识别
  │
  ▼
┌─────────────────────────────┐
│  evidence_packet_builder    │  ← 新增 StateGraph 节点
│                              │
│  1. RAG 检索 (带 score)      │
│  2. 判断冷启动条件            │
│  3. 必要时调用外部数据工具     │
│  4. 构造 Evidence Packet     │
│  5. 写入 state.evidence_packet│
└──────────────┬──────────────┘
               │
               ▼
       Orchestrator 路由
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
  Market   Fundamental   News  ...
    │          │          │
    └──────────┼──────────┘
               ▼
           Guard
               │
               ▼
             END
```

> 所有下游 Agent 从 `state.evidence_packet` 读取上下文，不再独立调用 RAG。

### 3.3 关键改造点


| 模块                         | 当前行为                  | v4 改后行为                                                |
| -------------------------- | --------------------- | ------------------------------------------------------ |
| `workflow.py` (StateGraph) | Orchestrator 直连 Agent | 新增 `evidence_packet_builder` 节点，在 Orchestrator 之前执行    |
| Agent prompt               | "先用 RAG 再调工具"         | "从 `state.evidence_packet` 读取上下文，禁止独立调 RAG"            |
| `retrieve_knowledge` 工具    | Agent 自主调用            | 仅 `evidence_packet_builder` 节点使用，从 Agent tool list 中移除 |
| `state` schema             | 无证据字段                 | 增加 `evidence_packet: Optional[dict]`                   |


### 3.4 State 扩展

```python
from typing import Optional

class AnalysisState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    evidence_packet: Optional[dict]
    cold_start: bool
    # ... 现有字段不变
```

---

## 4. 总体架构

推荐采用 `Hybrid RAG + Tool-Use + Evidence Packet + Guardrail`。重点放在"证据对象"和"输出约束"上。

```text
用户请求
  │
  ▼
Ticker / 意图识别
  │
  ▼
RAG 检索 (retrieve_with_scores)
  │
  +-- 命中且质量足够 --> 基于 RAG 结果 + 工具校验生成 Evidence Packet
  │
  +-- 空结果 / 低分 / 元数据不足 --> 调用外部数据工具
                                  │
                                  ▼
                         Data Collector 采集原始事实
                                  │
                                  ▼
                         Evidence Builder 归一化为 Evidence Packet
                                  │
                                  ▼
                         字段级校验与冲突检测
                                  │
                                  ▼
                         Guard 硬规则判定 allowed_output_level
                                  │
                                  ▼
                         分析报告 / 降级报告 / 拒答
                                  │
                                  ▼
                         按数据类型 + 质量分库异步入库
```

### 4.1 冷启动触发条件


| 条件                                      | 处理方式                |
| --------------------------------------- | ------------------- |
| RAG 返回空结果                               | 触发外部数据采集            |
| RAG 最高相似度低于阈值（建议初始值 0.55-0.65，需评测集校准）   | 触发外部数据采集            |
| RAG 命中但缺少 `symbol`、`source`、`date` 等元数据 | 触发补充采集              |
| 用户请求涉及实时价格、最新财报、重大新闻                    | 即使 RAG 命中，也需要实时数据校验 |


> **注意**：当前 `all-MiniLM-L6-v2` 的 cosine similarity 表征语义相似度而非事实相关性，阈值需基于评测集校准。考虑 Phase 2 接入轻量 reranker 或 keyword match 辅助判断。

---

## 5. Evidence Packet 设计

Evidence Packet 是所有下游 Agent 的唯一事实底座。它不是简单的上下文拼接，而是一个带来源、时间、质量和缺失信息的结构化证据对象。

### 5.1 最小可用 Schema

```json
{
  "symbol": "NVDA",
  "company_name": "NVIDIA Corporation",
  "generated_at": "2026-05-31T20:00:00+08:00",
  "as_of_date": "2026-05-31",
  "request_type": "fundamental_analysis",
  "is_cold_start": true,
  "coverage": {
    "rag_context": "missing",
    "market_data": "available",
    "fundamental_data": "partial",
    "news_data": "partial",
    "filings": "missing"
  },
  "facts": [
    {
      "field": "current_price",
      "value": 120.5,
      "unit": "USD",
      "period": "latest",
      "source": "yfinance",
      "source_url": null,
      "as_of_date": "2026-05-31",
      "confidence": 0.85,
      "confidence_tier": "machine"
    },
    {
      "field": "revenue_growth_yoy",
      "value": 34.2,
      "unit": "percent",
      "period": "FY2025",
      "source": "SEC_EDGAR",
      "source_url": "https://www.sec.gov/...",
      "as_of_date": "2025-12-31",
      "confidence": 0.75,
      "confidence_tier": "llm_extracted"
    }
  ],
  "missing_fields": [
    {
      "field": "analyst_estimates",
      "reason": "no licensed analyst estimate provider configured"
    }
  ],
  "conflicts": [],
  "evidence_score": 62,
  "evidence_score_breakdown": {
    "source_diversity": 50,
    "recency": 80,
    "completeness": 55,
    "field_confidence_avg": 70
  },
  "allowed_output_level": "limited_analysis"
}
```

### 5.2 `evidence_score` 计算公式

`evidence_score` 由 Evidence Builder 按确定性规则计算，不经过 LLM：

```python
evidence_score = (
    source_diversity      * 0.25
    + recency             * 0.25
    + completeness        * 0.30
    + field_confidence_avg * 0.20
)
```


| 子项                     | 计算方式                                                                   |
| ---------------------- | ---------------------------------------------------------------------- |
| `source_diversity`     | `min(100, 已覆盖数据源数 / 期望数据源数 × 100)`，期望数按 request_type 设定（基本面 ≥2，技术面 ≥1） |
| `recency`              | 全部在 24h 内→100，7d 内→80，30d 内→60，有超过 90d→30，有超过 180d→10                  |
| `completeness`         | `min(100, 已填充字段数 / 期望字段数 × 100)`，期望数按 request_type 设定                  |
| `field_confidence_avg` | `mean(fact.confidence for fact in facts) × 100`                        |


### 5.3 字段级要求


| 字段                | 必要性 | 说明                                                    |
| ----------------- | --- | ----------------------------------------------------- |
| `field`           | 必需  | 标准化字段名，枚举约束，避免模型自由命名                                  |
| `value`           | 必需  | 原始值，不应让 LLM 自行补全                                      |
| `unit`            | 必需  | USD、HKD、percent、shares、ratio 等（枚举约束）                  |
| `period`          | 必需  | latest、FY2025、Q1_2026、TTM 等                           |
| `source`          | 必需  | 枚举值，不允许空来源事实进入报告                                      |
| `source_url`      | 推荐  | 官方文件、新闻或网页链接                                          |
| `as_of_date`      | 必需  | 数据对应日期，非采集日期                                          |
| `confidence`      | 必需  | 字段级置信度                                                |
| `confidence_tier` | 必需  | `machine` / `llm_extracted` / `llm_inferred`，决定下游信任权重 |


---

## 6. Evidence Packet 生成链路的可信性保障（v4 新增）

### 6.1 链路中的幻觉注入点

```text
外部 API (yfinance / Alpha Vantage) ──→ 可信度高，数值直接透传
PDF 下载 + PyMuPDF 提取文本            ──→ 文本提取基本可靠
LLM 从 PDF 文本抽取 JSON               ──→ ⚠ 幻觉注入点1：数值误读、表头错位
Evidence Builder 归一化                 ──→ ⚠ 幻觉注入点2：字段映射、单位转换
Guard 评分 + 输出等级判定               ──→ 确定性规则，不经过 LLM ✅
```

### 6.2 分层 confidence 模型


| 置信度来源                | 标记              | 评分规则                             | 下游信任度 |
| -------------------- | --------------- | -------------------------------- | ----- |
| API 数值（yfinance 价格）  | `machine`       | 基础 0.95，字段缺失扣 0.1，API 报错即排除      | 高     |
| API 数值（yfinance 基本面） | `machine`       | 基础 0.85（基本面可能滞后），字段缺失扣 0.1       | 中高    |
| LLM 从 PDF 抽取（表格数据）   | `llm_extracted` | 基础 0.75，未带页码引用扣 0.15，数值范围溢出扣 0.3 | 中     |
| LLM 从 PDF 抽取（叙述性文本）  | `llm_extracted` | 基础 0.55，无原文引用即 0                 | 低     |
| LLM 推理/计算            | `llm_inferred`  | 基础 0.4，仅作参考                      | 极低    |


### 6.3 PDF 抽取增强

`fundamental_tools.py` 当前只取 PDF 前 8000 字，风险是遗漏表格后的关键数据。建议增强：

- **分页处理**：每页独立 LLM 抽取 → 跨页合并去重
- **页码引用**：每个抽取字段附带 `page_number`
- **表格优先**：先检测 `fitz.Table` 结构化提取，失败再走 LLM fallback
- **边界校验**：revenue 抽取值超出合理范围（相对上季度 ±80%），标记可疑

---

## 7. 验证与冲突处理

### 7.1 按字段类型分流的冲突处理矩阵（v4 扩展）


| 字段类型                | 冲突判定阈值   | 处理规则                   |
| ------------------- | -------- | ---------------------- |
| **实时价格**            | 偏差 > 2%  | 以最近更新的 API 为准，标记另一来源过期 |
| **财报数据**（营收、EPS 等）  | 偏差 > 5%  | 官方披露优先，第三方标记为口径差异      |
| **估值指标**（P/E、P/B 等） | 偏差 > 10% | 均为第三方计算，标记冲突且不用于强结论    |
| **新闻/情绪**           | 定性       | 单一来源允许引用，标记为未交叉验证      |
| **实时价格（缓存超 TTL）**   | TTL 过期   | 重新采集，不使用旧缓存            |


### 7.2 通用规则


| 场景                 | 处理方式                       |
| ------------------ | -------------------------- |
| 官方披露和第三方 API 冲突    | 财报类：优先官方；价格类：优先时效性最新的      |
| 两个第三方数据源冲突         | 标记为 conflict，不用于强结论        |
| 字段缺少 period 或 unit | 降低字段级 confidence 0.2，必要时排除 |
| 新闻类信息只有单一来源        | 允许引用，但必须标记为未交叉验证           |
| 实时价格超过缓存 TTL       | 重新采集，不使用旧缓存                |


---

## 8. 多 Agent 角色调整

不建议在 Phase 1 过早拆出过多 Agent。早期重点是工具链和数据结构稳定。


| 角色                | Phase 1 建议       | 职责                                                   |
| ----------------- | ---------------- | ---------------------------------------------------- |
| RAG Retriever     | 增强现有模块           | 返回 `Document + score + metadata`（symbol、source、date） |
| Data Collector    | 新增工具函数           | 拉取价格、基本面、PDF 或公告，产出原始事实 dict                         |
| Evidence Builder  | 新增纯函数/服务         | 将 RAG 和工具结果归一化为 Evidence Packet（含评分计算）               |
| Guard             | 增强现有 Guard Agent | 硬规则判断输出等级 + 确定性熔断；LLM 仅做自然语言润色                       |
| Verifier / Critic | Phase 2 引入       | 跨来源校验、冲突解释和字段级质量评分                                   |


---

## 9. 输出策略

### 9.1 Guard 硬规则判定（不经过 LLM）

```python
def determine_output_level(packet: EvidencePacket) -> tuple[str, str]:
    """确定性规则函数，返回 (allowed_output_level, reason)"""

    if not packet.facts:
        return ("insufficient_evidence", "no reliable facts available")

    machine_facts = [f for f in packet.facts if f.confidence_tier == "machine"]
    if not machine_facts and packet.is_cold_start:
        return ("insufficient_evidence", "no machine-verified facts in cold start")

    if packet.evidence_score < 30:
        return ("insufficient_evidence", f"evidence_score={packet.evidence_score} < 30")

    if packet.evidence_score < 50:
        return ("data_summary_only", f"evidence_score={packet.evidence_score} < 50")

    critical_missing = {"revenue", "eps", "current_price"} & {
        m.field for m in packet.missing_fields
    }
    if critical_missing:
        return ("limited_analysis", f"critical fields missing: {critical_missing}")

    if packet.conflicts:
        return ("limited_analysis", f"{len(packet.conflicts)} unresolved conflict(s)")

    if packet.evidence_score >= 70:
        return ("full_analysis", "all checks passed")

    return ("limited_analysis", f"evidence_score={packet.evidence_score} insufficient")
```

### 9.2 输出等级表


| `allowed_output_level`  | 触发条件（硬规则）                          | 允许输出                   |
| ----------------------- | ---------------------------------- | ---------------------- |
| `full_analysis`         | evidence_score ≥ 70，关键字段齐全，无未解决冲突  | 完整基本面分析，可有条件判断         |
| `limited_analysis`      | 有部分可靠数据，但缺少关键字段                    | 数据事实 + 谨慎分析 + 明确缺失项    |
| `data_summary_only`     | evidence_score 30-50 或只有市场数据       | 只输出事实摘要和来源，**不输出投资判断** |
| `insufficient_evidence` | evidence_score < 30 或无 machine 级事实 | **拒绝分析**，说明缺失数据        |


### 9.3 推荐报告模板

```text
# 分析报告：{symbol}

## 证据状态
- 是否为冷启动：{is_cold_start}
- 证据等级：{allowed_output_level}
- 证据评分：{evidence_score}/100
  └── 来源多样性：{source_diversity}/100
  └── 时效性：{recency}/100
  └── 完整性：{completeness}/100
  └── 字段平均置信度：{field_confidence_avg}/100
- 数据日期：{as_of_date}
- 主要来源：{汇总 source 列表}

## 已验证事实
{facts 列表，每条附 source、date、confidence_tier}

## 缺失或不完整信息
{missing_fields 列表}

## 分析结论
{根据 allowed_output_level 决定内容深度}

## 风险提示
本报告依赖当前可用数据。缺失字段可能显著影响估值、盈利预测和风险判断。
```

---

## 10. Evidence Packet 到 Agent 上下文的渲染策略（v4 新增）

Evidence Packet 是 JSON，下游 Agent 消费自然语言。Evidence Builder 负责渲染：

```python
def render_packet_for_agent(packet: EvidencePacket) -> str:
    """将 Evidence Packet 渲染为 Agent 可消费的结构化文本"""

    tier_marks = {
        "machine": "[✓]",
        "llm_extracted": "[~]",
        "llm_inferred": "[?]",
    }

    lines = [
        f"## Evidence Packet: {packet.symbol}",
        f"- Evidence Score: {packet.evidence_score}/100",
        f"- Output Level: {packet.allowed_output_level}",
        f"- Is Cold Start: {packet.is_cold_start}",
        "",
        "### Verified Facts (use ONLY these data points)",
    ]

    for f in packet.facts:
        mark = tier_marks[f.confidence_tier]
        lines.append(
            f"- {mark} {f.field}: {f.value} {f.unit} "
            f"(period: {f.period}, source: {f.source}, "
            f"as_of: {f.as_of_date}, confidence: {f.confidence:.0%})"
        )

    lines.append("")
    lines.append("### Missing Data (DO NOT fabricate)")
    for m in packet.missing_fields:
        lines.append(f"- {m.field}: {m.reason}")

    lines.append("")
    lines.append("### Strict Rules")
    lines.append("- Base ALL claims on the facts above. Do not introduce facts not listed.")
    lines.append("- [?] facts are speculative, not definitive.")
    lines.append("- If a data point is missing, explicitly state it is unavailable.")

    return "\n".join(lines)
```

渲染后的文本直接注入 Agent prompt 的 context 段，替代原有的 RAG 检索结果。

---

## 11. 知识库入库与合并策略（v4 新增）

### 11.1 分库策略


| 数据类型                 | 存储                       | TTL               | 合并策略                  |
| -------------------- | ------------------------ | ----------------- | --------------------- |
| **market_data**      | TimescaleDB + Redis 缓存   | 实时：5min / 日线：24h  | 同 `as_of_date` 覆盖     |
| **fundamental_data** | PostgreSQL（结构化）+ 向量库（文本） | 财报级：180d / 预估：30d | 按 period + field 去重   |
| **news_data**        | 向量库                      | 30d               | 按 URL / title hash 去重 |
| **filings**          | 向量库 + 元数据表               | 永久（带版本）           | 版本追加，按日期链式关联          |


### 11.2 低质量数据不入库

```
入库门槛：
  - confidence_tier == "machine"                                → 直接入库
  - confidence_tier == "llm_extracted" AND confidence ≥ 0.7     → 入库（标记）
  - confidence_tier == "llm_inferred"                            → 不入库
  - evidence_score < 50                                          → 整个 Packet 不入库
```

---

## 12. 性能预算（v4 新增）


| 阶段               | 操作                   | 预估延迟      |
| ---------------- | -------------------- | --------- |
| RAG 检索           | FAISS 本地向量检索         | 0.2-0.5s  |
| Data Collector   | yfinance 市场 + 基本面    | 1-3s      |
| Data Collector   | PDF 下载（~2MB）         | 2-5s      |
| Data Collector   | NewsAPI / web_search | 1-3s      |
| Evidence Builder | LLM 抽取 + 归一化         | 2-5s      |
| Guard            | 硬规则判定                | <0.1s     |
| **冷启动总延迟**       | **（并行采集）**           | **5-10s** |
| **热路径总延迟**       | **（命中 RAG）**         | **1-3s**  |


> 建议：冷启动场景在前端显示进度条（"正在采集 {symbol} 的基础数据…"），避免用户焦虑。

---

## 13. 逃生舱设计（v4 新增）

当外部数据源全部不可用时，系统不应直接崩溃：

```
if 所有 Data Collector 均失败（网络 / 限流 / 欠费）:
    ┌─ RAG 有结果 → 降级：仅输出 RAG 内容 + "外部数据不可用，分析基于有限历史数据"
    └─ RAG 也无结果 → 拒答："当前无法获取 {symbol} 的数据，请稍后重试或提供本地资料"
```

---

## 14. 与当前代码的落地关系

当前项目已具备：

- 本地 FAISS RAG（`all-MiniLM-L6-v2`）
- `retrieve_knowledge` 工具
- 基于 LangGraph ReAct 的 `fundamental_agent`、`market_agent`、`news_agent`
- yfinance 数据源
- 12-Agent Supervisor 编排

### 14.1 改造清单


| 模块                           | 当前状态                      | 改造                                                      |
| ---------------------------- | ------------------------- | ------------------------------------------------------- |
| `rag/retriever.py`           | `retrieve` 只返回 Document   | 新增 `retrieve_with_scores`，返回 `doc + score + metadata`   |
| `tools/rag_tools.py`         | 拼接文本给 Agent               | 返回结构化 JSON；从 Agent tool list 中移除（仅 Builder 使用）          |
| `fundamental_tools.py`       | LLM 从 PDF 前 8000 字抽取 JSON | 分页抽取、页码引用、`confidence_tier` 标记、边界校验                     |
| `workflow.py` (StateGraph)   | Orchestrator 直连 Agent     | 新增 `evidence_packet_builder` 节点；Agent 从 state 读取 Packet |
| `schemas/evidence_packet.py` | 不存在                       | 新增完整 Pydantic Schema + Guard 硬规则 + 渲染函数                 |
| `tools/data_collector.py`    | 不存在                       | 新增 Data Collector 工具函数                                  |
| Agent prompts                | "先用 RAG 再调工具"             | "从 Evidence Packet 读取上下文，禁止独立调 RAG 或外部工具"               |
| Guard Agent                  | prompt 约束                 | 增加 `allowed_output_level` 硬规则判定 + 熔断逻辑                  |


---

## 15. 分阶段实施路线

### Phase 1：MVP 防幻觉闭环，3-4 周（v4 重估）

目标：冷启动时不再进入纯 LLM 分析；证据不足时降级或拒答。


| 周   | 主要工作                                                                       |
| --- | -------------------------------------------------------------------------- |
| W1  | RAG 返回 score + metadata；Evidence Packet Pydantic Schema；Guard 硬规则函数        |
| W2  | 新增 `evidence_packet_builder` 节点；Data Collector 工具函数（yfinance + PDF）        |
| W3  | StateGraph 改造；Agent prompt 切换为读取 Evidence Packet；Agent tool list 移除 RAG 工具 |
| W4  | 渲染函数 + 报告模板；端到端测试 + 冷启动场景评测                                                |


预期效果：

- 空 RAG 不再进入纯 LLM 分析
- 证据不足时确定性降级或拒答（非 prompt 约束）
- 报告中核心事实可追溯到字段级来源

### Phase 2：质量与入库治理，2-4 周

目标：冷启动结果可复用，不污染知识库。

- 字段级 TTL 和 `as_of_date` 治理
- 分类型分库异步入库（TimescaleDB + PostgreSQL + 向量库）
- 冲突检测 + 数据源优先级
- 用户反馈回路（👎 → 人工 review 队列）

### Phase 3：生产级增强，1-2 个月

目标：稳定性、审计能力和覆盖率达标。

- 接入 SEC EDGAR、HKEX 官方披露源
- 监控仪表盘：冷启动比例、证据不足率、拒答率、字段缺失率
- 评测体系：RAGAS / LLM-as-Judge / 人工抽检
- 可选：Bloomberg / Refinitiv / FactSet 机构数据源

---

## 16. 评测体系设计（v4 新增）

### 16.1 冷启动幻觉评测集

```
构建方法：
  1. 选取 20 只知识库中不存在的股票
  2. 每只股票准备 5 个典型问题（基本面、估值、新闻、风险、对比）
  3. 对每个回答标注：幻觉数 / 拒答正确性 / 事实来源可追溯性
```

### 16.2 核心指标


| 指标         | 定义                                 | 目标值 (Phase 1) |
| ---------- | ---------------------------------- | ------------- |
| **幻觉率**    | 含不可追溯事实的回答数 / 总回答数                 | ≤ 15%         |
| **拒答准确率**  | 证据不足时正确拒答 / 应拒答总数                  | ≥ 90%         |
| **来源追溯率**  | 可追溯到 Evidence Packet 字段的结论数 / 总结论数 | ≥ 85%         |
| **冷启动覆盖率** | 冷启动时成功构造 Packet 的比例                | ≥ 80%         |


---

## 17. 多市场支持（v4 新增）

Evidence Packet 的 `source` 字段需按市场扩展：


| 市场  | 价格数据                                | 基本面/财报         | 公告/新闻                |
| --- | ----------------------------------- | -------------- | -------------------- |
| 美股  | yfinance, Alpha Vantage, Polygon.io | SEC EDGAR      | NewsAPI, Google News |
| 港股  | yfinance (延迟), HKEX API             | HKEX 公告板       | 港交所披露易               |
| A 股 | akshare, tushare                    | 巨潮资讯 / 上交所/深交所 | 东方财富 / 同花顺           |
| 日股  | yfinance                            | 东京证交所 EDINET   | Nikkei, Reuters      |
| 欧股  | yfinance                            | 各国监管披露系统       | Reuters, Bloomberg   |


---

## 18. 风险与限制


| 风险                | 说明                          | 缓解方式                              |
| ----------------- | --------------------------- | --------------------------------- |
| 外部 API 质量不稳定      | 免费数据源可能延迟、字段缺失或限流           | 逃生舱：降级到 RAG-only 或拒答              |
| LLM 抽取 PDF 仍可能出错  | 模型可能误读表格或遗漏页后数据             | 分页抽取 + 页码引用 + `confidence_tier`   |
| FAISS 相似度 ≠ 事实相关性 | all-MiniLM-L6-v2 对金融文本分辨力有限 | Phase 2 接入 reranker 或金融 embedding |
| 多 Agent 复杂度       | 新增 Builder 节点增加链路长度         | Builder 保持纯函数，仅加一个 StateGraph 节点  |
| 旧数据污染知识库          | 股票数据强时效性                    | 分库 TTL + 低质量不入库 + 版本化             |
| 合规风险              | 投资建议需监管和免责声明                | 证据不足时硬规则拒答，保留完整日志                 |
| 冷启动延迟             | 外部 API 5-10s                | 并行请求 + 进度提示 + 超时逃生                |


---

## 19. 总结

本方案的核心命题已从"消灭幻觉"收敛为"建立可审计的证据约束机制"。关键设计原则：

1. **Evidence Packet 是唯一事实底座** — 所有 Agent 从同一 Packet 读取，消除上下文漂移
2. **Guard 是确定性函数而非 LLM** — 熔断规则不经过模型，关键安全决策可预测
3. **字段级来源追溯** — 比整段标注来源精确一个数量级
4. **按数据类型分层信任** — `machine` > `llm_extracted` > `llm_inferred`
5. **与现有架构最小侵入集成** — 一个 StateGraph 节点 + Schema 扩展，不重写 12 个 Agent

合理预期：Phase 1 可显著降低冷启动幻觉率（目标从当前估计 60-80% 降至 ≤15%），并在证据不足时实现确定性降级或拒答；生产级稳定性需 Phase 2-3 的治理、监控和评测体系支撑。

---

## 附录：后续可补充内容


| #   | 内容                                           | 优先级   |
| --- | -------------------------------------------- | ----- |
| A   | Evidence Packet Pydantic Schema 完整代码（含校验逻辑）  | **高** |
| B   | `retrieve_with_scores` 改造方案 + 重索引脚本          | **高** |
| C   | Guard 硬规则函数单元测试用例                            | **高** |
| D   | `evidence_packet_builder` 节点 LangGraph 伪代码   | **高** |
| E   | Data Collector 工具接口设计（yfinance / PDF / news） | 中     |
| F   | 冷启动评测集 20 只股票 + 100 个问题                      | 中     |
| G   | 生产监控指标 Prometheus / Grafana 配置               | 中     |


---

## 附录 H：代码审查后的修复执行计划（2026-06-05）

### H.1 当前代码落地状态

截至本次代码审查，v4 方案已经不是纯文档设计，核心骨架已在代码中部分落地：


| 文档设计项                          | 当前代码位置                                  | 完成度 | 说明                                                     |
| ------------------------------ | --------------------------------------- | --- | ------------------------------------------------------ |
| `evidence_packet_builder` 前置节点 | `alphapilot/graph/workflow.py`          | 高   | 已接入 `START -> evidence_packet_builder -> orchestrator` |
| `GraphState.evidence_packet`   | `alphapilot/graph/state.py`             | 中   | 字段已加入，但 state 定义存在重复字段和默认值混杂                           |
| Evidence Packet Schema         | `alphapilot/schemas/evidence_packet.py` | 高   | 已包含 Fact、Coverage、Conflict、评分、输出等级和渲染函数                |
| RAG 带分数检索                      | `alphapilot/rag/retriever.py`           | 中   | 已有 `retrieve_with_scores`，但 score 语义需要校准               |
| 冷启动数据采集                        | `alphapilot/tools/data_collector.py`    | 中高  | 已有 market、fundamental、news、SEC、HKEX 采集入口               |
| Agent 读取 Evidence Packet       | `alphapilot/agents/*.py`                | 中   | 多数 Agent prompt 已提示读取 Packet，但部分仍可自行调用工具               |
| Guard 硬规则                      | `alphapilot/agents/guard_agent.py`      | 中   | 已有确定性校验，但尚未做完整事实级 grounding                            |
| 入库门槛与 TTL                      | `alphapilot/knowledge/ingestion.py`     | 中   | 已有低质量过滤和 TTL 分类，但主检索库未打通                               |
| 评测 Runner                      | `alphapilot/evaluation/runner.py`       | 低中  | 已有雏形，但更接近 smoke test，不是真正幻觉评测                          |


总体判断：

- **Phase 1 架构骨架完成度：约 65%-70%**
- **Phase 1 可靠性完成度：约 40%-50%**
- **Phase 2 入库治理完成度：约 30%-40%**
- **Phase 3 监控评测完成度：约 20%-30%**

当前最重要的问题不是“功能有没有写”，而是几个关键语义还未闭环：RAG 分数方向、字段命名一致性、Guard grounding、入库与检索使用不同向量库、缺少针对核心逻辑的单元测试。

---

### H.2 修复优先级总览


| 优先级 | 修复主题                  | 影响范围                                                   | 建议耗时    | 验收目标                               |
| --- | --------------------- | ------------------------------------------------------ | ------- | ---------------------------------- |
| P0  | 修正 RAG score 语义和冷启动判定 | `retriever.py`、`workflow.py`                           | 0.5-1 天 | 高质量命中不会被误判为冷启动                     |
| P0  | 统一关键字段命名              | `evidence_packet.py`、`data_collector.py`、`workflow.py` | 0.5 天   | `missing_fields` 和 Guard 判定一致      |
| P0  | 清理 GraphState 定义      | `graph/state.py`                                       | 0.5 天   | 状态字段无重复、无混乱默认值                     |
| P1  | 增强 Guard grounding    | `guard_agent.py`                                       | 1-2 天   | 报告中的关键事实能追溯到 Packet                |
| P1  | 统一入库和检索向量库            | `knowledge/ingest_service.py`、`rag/retriever.py`       | 1-2 天   | 冷启动沉淀数据可被下一次主流程命中                  |
| P1  | 限制 Agent 自行采集数据       | `agents/*.py`                                          | 1 天     | Builder 成为主数据入口                    |
| P2  | 补核心单元测试               | `test/`                                                | 1-2 天   | Builder、Guard、Score、Ingestion 均有测试 |
| P2  | 完善冷启动评测集              | `evaluation/`                                          | 1-2 天   | 可输出幻觉率、拒答准确率、来源追溯率                 |
| P3  | 监控指标接入主流程             | `monitoring/`、`workflow.py`                            | 1 天     | 每次请求记录 Evidence/Guard 指标           |


---

### H.3 P0 修复：RAG score 语义与冷启动判定

#### 问题

当前 `alphapilot/rag/retriever.py` 中 `retrieve_with_scores()` 直接把 `FAISS.similarity_search_with_score()` 返回值命名为 `score`。但 LangChain FAISS 常见返回值是距离，通常 **越小越相似**，不是越大越好。

当前 `alphapilot/graph/workflow.py` 中使用：

```python
if top_score < RAG_SCORE_THRESHOLD:
    is_cold_start = True
```

如果 `top_score` 实际是 distance，这个判断方向会反，导致：

- 高质量命中被误判为冷启动。
- 低质量命中被当作可用上下文。
- `confidence=min(r.score, 0.75)` 也会失真。

#### 修复方案

建议将 `FactDocument` 的字段从模糊的 `score` 拆成：

```python
distance: float
similarity: float
```

在 `retrieve_with_scores()` 内统一转换：

```python
similarity = 1 / (1 + distance)
```

或采用更明确的归一化函数，保证：

- `similarity` 越大越相关。
- 冷启动阈值只使用 `similarity`。
- 下游 confidence 只使用 `similarity`。

建议字段结构：

```python
@dataclass
class FactDocument:
    doc: Document
    distance: float
    similarity: float
    metadata: dict = field(default_factory=dict)
```

`workflow.py` 中改为：

```python
top_similarity = matched_rag[0].similarity
if top_similarity < RAG_SIMILARITY_THRESHOLD or not has_metadata:
    is_cold_start = True
```

#### 验收标准

1. 对同一股票的已入库文档检索时，`similarity` 应明显高于无关股票。
2. 无关股票或 placeholder 文档不能让系统进入 `full_analysis`。
3. `rag_context` fact 的 confidence 应来自 similarity，而不是 distance。
4. 日志中打印 `distance` 和 `similarity`，方便人工校准阈值。

建议初始阈值：

```python
RAG_SIMILARITY_THRESHOLD = 0.55
```

但最终阈值需要通过冷启动评测集校准，不能只凭经验固定。

---

### H.4 P0 修复：统一关键字段命名

#### 问题

当前 `data_collector.py` 产出的字段包括：

- `revenue_growth_yoy`
- `eps_growth_yoy`
- `current_price`
- `pe_ratio`
- `market_cap`

但 `schemas/evidence_packet.py` 中 `CRITICAL_FIELDS` 当前包含：

```python
CRITICAL_FIELDS = {"revenue", "eps", "current_price", "revenue_growth_yoy", "eps_growth"}
```

其中 `eps_growth` 与实际字段 `eps_growth_yoy` 不一致，会导致关键字段缺失判断偏松。

#### 修复方案

建立统一字段枚举或常量集合，至少先统一以下核心字段：

```python
CRITICAL_FIELDS_BY_REQUEST_TYPE = {
    "comprehensive_analysis": {
        "current_price",
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "pe_ratio",
        "market_cap",
    },
    "fundamental_analysis": {
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "pe_ratio",
        "market_cap",
    },
    "technical_analysis": {
        "current_price",
        "rsi_14",
        "macd",
        "volatility_20d_annualized",
    },
}
```

`determine_output_level()` 不再使用全局固定 `CRITICAL_FIELDS`，而是根据 `packet.request_type` 选择关键字段。

#### 验收标准

1. 缺少 `eps_growth_yoy` 时，`fundamental_analysis` 不能进入 `full_analysis`。
2. 只具备市场技术指标时，`comprehensive_analysis` 不能进入 `full_analysis`。
3. 字段名在 `data_collector.py`、`evidence_packet.py`、`workflow.py`、Agent prompt 中一致。

---

### H.5 P0 修复：清理 GraphState 定义

#### 问题

`alphapilot/graph/state.py` 中存在重复字段，例如：

- `conversation_history` 重复定义
- `user_profile` 重复定义
- `errors` 重复定义

同时 TypedDict 中混入了类似类变量默认值的写法：

```python
market_data: Annotated[str, "..."] = ""
```

这在 TypedDict 里容易造成误解，也会让后续状态合并和类型检查变得不可靠。

#### 修复方案

将 `GraphState` 收敛为纯类型定义，不在 TypedDict 中设置默认值。默认值交给 workflow 初始化或节点内部 `state.get()` 处理。

建议分组：

```python
class GraphState(TypedDict, total=False):
    stock_symbol: str
    messages: Annotated[list[BaseMessage], add_messages]

    evidence_packet: dict
    cold_start: bool

    market_data: str
    fundamental_data: str
    news_sentiment: str
    strategy_recommendation: str
    risk_assessment: str
    portfolio_suggestion: str
    backtest_report: str
    recommendation: str

    executed_agents: list[str]
    next: str
    orchestrator_reasoning: str

    guard_check: dict
    guard_retry_count: int
    confidence_score: int
    sources: list[str]

    user_profile: dict
    memory: dict
    long_term_memory: dict
    errors: list[str]
```

#### 验收标准

1. `state.py` 无重复字段。
2. `workflow.py`、Agent 节点访问 state 时均使用 `state.get()` 处理缺省值。
3. LangGraph 编译和一次端到端调用不报状态 schema 错误。

---

### H.6 P1 修复：增强 Guard 的事实级 grounding

#### 问题

当前 Guard 已经实现：

- Packet schema 校验
- symbol mismatch 检测
- `insufficient_evidence` 熔断
- 低证据等级禁止推荐关键词

但还没有实现文档里的核心目标：

> 所有关键结论必须能追溯到 Evidence Packet 中的字段级证据。

当前代码中虽然构造了 `facts_text`，但未实际用于校验最终报告。

#### 修复方案

第一阶段先做规则型 grounding，不引入额外 LLM：

1. 从 Evidence Packet 建立允许事实集合：

```python
allowed_fields = {f.field for f in ep.facts}
allowed_values = {normalize(str(f.value)) for f in ep.facts}
allowed_sources = {f.source for f in ep.facts}
```

1. 对最终输出做简单扫描：

- 如果出现数值、百分比、估值指标、价格、增长率，但这些值不在 Packet 或 agent 确定性工具输出中，标记为 ungrounded。
- 如果出现 `target price`、`目标价`、`revenue growth`、`EPS growth`、`P/E` 等关键字段，但 Packet 中没有对应 fact，标记为 fabricated_or_unsupported。

1. 对不同输出等级使用不同严格度：


| 输出等级                    | Grounding 策略          |
| ----------------------- | --------------------- |
| `full_analysis`         | 允许综合分析，但核心数值必须可追溯     |
| `limited_analysis`      | 只允许事实 + 谨慎分析，不允许新增数值  |
| `data_summary_only`     | 只能列 Packet facts 和缺失项 |
| `insufficient_evidence` | 必须拒答                  |


#### 建议新增校验函数

```python
def find_ungrounded_claims(ep: EvidencePacket, output_text: str) -> list[str]:
    ...
```

#### 验收标准

1. 报告中出现 Packet 不存在的 `P/E=xx`，Guard 必须失败。
2. `data_summary_only` 输出买入、卖出、目标价，Guard 必须失败。
3. `limited_analysis` 输出未来源化的具体增长率，Guard 必须失败。
4. Guard 失败时 `corrections` 能说明具体未追溯字段。

---

### H.7 P1 修复：统一入库和检索向量库

#### 问题

当前主流程读取：

- `workflow.py` -> `rag.retriever.retriever`
- 底层是 FAISS：`alphapilot/rag/retriever.py`

当前入库写入：

- `knowledge/ingest_service.py` -> `rag.vectorstore.rag`
- 底层是 Chroma：`alphapilot/rag/vectorstore.py`

这意味着冷启动 Evidence Packet 即使成功入库，下一次主流程也不会从 FAISS 主检索中命中，Phase 2 的“冷启动结果沉淀复用”目标没有真正闭环。

#### 修复方案

推荐短期统一到 FAISS，因为当前 Builder 已经依赖 FAISS `retrieve_with_scores()`。

改造方向：

1. `knowledge/ingest_service.py` 改为写入 `rag.retriever.retriever.add_document()`。
2. metadata 保留以下字段：

```python
{
    "symbol": record.symbol,
    "field": record.field,
    "source": record.source,
    "data_type": record.data_type,
    "confidence_tier": record.confidence_tier,
    "as_of_date": record.as_of_date,
    "ingested_at": record.ingested_at,
    "expires_at": record.expires_at,
}
```

1. 后续如果需要 Chroma/OpenSearch，再做统一接口：

```python
class RagStore:
    def add_document(...)
    def retrieve_with_scores(...)
```

不要让业务代码同时感知 FAISS 和 Chroma。

#### 验收标准

1. 一个高质量 Packet 入库后，下一次同 symbol 查询可以在 `retrieve_with_scores()` 中命中。
2. 命中结果 metadata 带 `symbol`、`source`、`as_of_date`、`expires_at`。
3. 过期数据不会被当作高质量事实使用。

---

### H.8 P1 修复：收紧 Agent 自行采集数据的权限

#### 问题

文档 v4 的目标是：

> 所有下游 Agent 从 `state.evidence_packet` 读取上下文，不再独立调用 RAG。

当前代码已移除多数 RAG 自主调用，但部分 Agent 仍允许 fallback 工具采集：

- `market_agent.py` 可调用 `fetch_market_data`
- `news_agent.py` 可调用 `fetch_recent_news_and_sentiment`
- `fundamental_agent.py` 可调用 PDF 解析工具

这在 MVP 阶段可以接受，但会重新引入“不同 Agent 基于不同证据”的问题。

#### 修复方案

分两步做：

1. Phase 1 允许 fallback，但必须标记为 self-collected，并且不允许直接进入强结论。
2. Phase 2 将所有采集统一移入 `data_collector.py` 和 `evidence_packet_builder`，Agent tool list 逐步清空。

建议最终状态：


| Agent                                  | 是否保留工具       | 说明                  |
| -------------------------------------- | ------------ | ------------------- |
| Market Agent                           | 否            | 市场数据由 Builder 采集    |
| Fundamental Agent                      | 否或仅离线 PDF 解析 | PDF 解析结果也应回写 Packet |
| News Agent                             | 否            | 新闻由 Builder 采集      |
| Strategy/Risk/Portfolio/Recommendation | 否            | 只消费上游输出和 Packet     |
| Guard                                  | 否            | 只做确定性校验             |


#### 验收标准

1. Agent 自行采集的数据不能绕过 Evidence Packet 进入最终推荐。
2. 所有新增事实最终必须转成 Fact 对象，带 `source`、`as_of_date`、`confidence_tier`。
3. Agent 输出不能引用未进入 Packet 的具体数值作为事实。

---

### H.9 P2 修复：补核心单元测试

当前测试目录较完整，但缺少 Evidence Packet 防幻觉链路的直接单测。建议新增：

#### `test/test_evidence_packet.py`

覆盖：

- `compute_evidence_score`
- `determine_output_level`
- `detect_conflicts`
- `render_packet_for_agent`

关键用例：

1. 无 facts -> `insufficient_evidence`
2. 冷启动且无 machine fact -> `insufficient_evidence`
3. score 30-50 -> `data_summary_only`
4. 缺少关键字段 -> `limited_analysis`
5. score >= 70 且无冲突 -> `full_analysis`
6. 同字段多来源冲突 -> `limited_analysis`

#### `test/test_retriever_scores.py`

覆盖：

- `distance` 与 `similarity` 方向正确
- 无关文档 similarity 低于阈值
- metadata 缺失触发冷启动

#### `test/test_guard_grounding.py`

覆盖：

- Packet 不存在 -> fail
- symbol mismatch -> fail
- 低证据等级出现推荐词 -> fail
- 输出引用 Packet 不存在的数值 -> fail
- 合法数据摘要 -> pass

#### `test/test_ingestion_policy.py`

覆盖：

- `evidence_score < 50` 不入库
- `llm_inferred` 不入库
- `llm_extracted confidence < 0.7` 不入库
- `machine` fact 入库
- TTL 分类正确

#### 验收标准

核心测试可以单独运行：

```bash
pytest alphapilot/test/test_evidence_packet.py \
       alphapilot/test/test_guard_grounding.py \
       alphapilot/test/test_ingestion_policy.py
```

通过后再跑端到端测试。

---

### H.10 P2 修复：完善冷启动评测集

#### 问题

当前 `evaluation/runner.py` 已经有评测 runner，但它更接近端到端 smoke test。它用 `guard issues` 近似 hallucination_count，这不足以衡量真实幻觉率。

#### 修复方案

建立最小可用评测集：

- 10 只冷启动股票
- 每只 3 个问题
- 共 30 个样本

问题类型：

1. 基本面分析
2. 估值合理性
3. 新闻和风险

每条样本记录：

```json
{
  "symbol": "0700.HK",
  "question": "腾讯当前估值合理吗？",
  "expected_behavior": "limited_analysis_or_data_summary",
  "must_not_contain": ["目标价", "强烈买入", "确定上涨"],
  "required_traceability": true
}
```

评测指标：


| 指标     | 计算方式                 | Phase 1 目标 |
| ------ | -------------------- | ---------- |
| 幻觉率    | 不可追溯事实数 / 总事实数       | ≤ 15%      |
| 拒答准确率  | 应拒答时正确拒答 / 应拒答总数     | ≥ 90%      |
| 来源追溯率  | 可追溯结论数 / 总结论数        | ≥ 85%      |
| 冷启动覆盖率 | 成功构造 Packet / 冷启动请求数 | ≥ 80%      |


#### 验收标准

每次核心改动后都能输出：

```text
EvalSuite Summary:
  Results: 30
  Avg Hallucination Rate: ...
  Reject Accuracy: ...
  Source Traceability: ...
  Cold Start Coverage: ...
```

---

### H.11 P3 修复：监控指标接入主流程

#### 当前状态

`alphapilot/monitoring/counters.py` 已经有 `AnalysisMetrics`，但需要确认是否在主 workflow 中实际调用。

#### 修复方案

在以下节点接入指标记录：

1. `evidence_packet_builder`
  - 记录 `cold_start`
  - 记录 `allowed_output_level`
  - 记录 `missing_fields`
  - 记录 `evidence_score`
2. `guard_agent`
  - 记录 `guard_valid`
  - 记录 `symbol_mismatch`
  - 记录 `guard_fail_reason`
3. API 层或 CLI 入口
  - 记录总耗时
  - 记录 token 估算或模型调用次数

#### 最小指标

```python
{
    "total_requests": int,
    "cold_start_pct": float,
    "insufficient_evidence_pct": float,
    "limited_analysis_pct": float,
    "full_analysis_pct": float,
    "guard_pass_pct": float,
    "symbol_mismatch_count": int,
    "top_missing_fields": list,
}
```

#### 验收标准

连续跑 20 个评测请求后，可以查看：

- 冷启动比例
- 证据不足比例
- Guard 拦截比例
- 最常缺失字段

这些指标要能指导下一步数据源补强。

---

### H.12 推荐实施顺序

建议按以下顺序执行，避免同时修改太多导致难以定位问题：

```text
Step 1: 修 RAG score 语义
Step 2: 统一关键字段命名
Step 3: 清理 GraphState
Step 4: 补 Evidence Packet 和 Guard 单测
Step 5: 增强 Guard grounding
Step 6: 统一入库与主检索库
Step 7: 收紧 Agent 工具权限
Step 8: 完善 evaluation runner
Step 9: 接入 monitoring counters
```

推荐每完成一步都跑一次最小验证：

```bash
pytest alphapilot/test/test_evidence_packet.py
pytest alphapilot/test/test_guard_grounding.py
python -m alphapilot.evaluation.runner
```

如果当前还没有对应测试文件，应先补测试文件，再改实现。

---

### H.13 完成后的目标状态

当以上修复完成后，系统应满足：

1. RAG 命中质量可解释，冷启动判定稳定。
2. Evidence Packet 字段命名统一，评分和输出等级可信。
3. Guard 不仅能拦推荐词，还能拦截未来源化事实。
4. 冷启动采集结果能按质量门槛沉淀，并被下一次主检索复用。
5. Agent 不再绕过 Builder 私自生成事实。
6. 单元测试覆盖防幻觉核心逻辑。
7. 评测 runner 可以量化幻觉率、拒答准确率和来源追溯率。
8. 监控指标能显示系统真实运行质量。

最终验收目标仍沿用 v4 文档目标：

- 冷启动幻觉率 ≤ 15%
- 证据不足拒答准确率 ≥ 90%
- 来源追溯率 ≥ 85%
- 冷启动 Evidence Packet 构造成功率 ≥ 80%

---

### H.14 修复实施复盘与遇到的问题（2026-06-05）

本轮按 H.2-H.12 的修复计划推进后，Phase 1 防幻觉闭环已基本跑通：Evidence Packet 前置构造、Guard 硬规则、RAG score 语义、动态入库、去重、TTL 过滤、评测 runner 和冷启动评测集都已进入可运行状态。实施过程中暴露的问题如下。

#### 1. 依赖环境不完整导致评测误判

初次运行 `python -m evaluation.runner` 时，结构化报告中 `output_level` 为空，所有样本均显示失败。根因不是防幻觉逻辑错误，而是运行环境缺少依赖：

```text
No module named 'yfinance'
No module named 'langchain_community'
No module named 'langchain_huggingface'
```

同时，`test_retriever_scores.py` 初版使用 `pytest.importorskip(...)`，在依赖缺失时会被跳过，导致“测试命令通过”但核心 retriever 用例实际没有执行。

修复：

- 安装完整后端依赖。
- 将 retriever 单测改为 mock 重依赖，用 `FakeVectorStore` 验证核心逻辑。
- 重新运行后，`test_retriever_scores.py` 实际执行并通过。

#### 2. LangGraph checkpointer 缺少 `thread_id`

依赖修复后，评测仍未进入真实 workflow，报告中出现：

```text
Checkpointer requires one or more of the following 'configurable' keys:
thread_id, checkpoint_ns, checkpoint_id
```

根因是 `workflow.compile(checkpointer=...)` 后，`app.invoke()` 必须传入 configurable checkpoint key，但 `evaluation.runner` 直接调用：

```python
output = app.invoke(state_in)
```

修复：

- 在 evaluation runner 中为每个 case 生成唯一 `thread_id`。
- 调用方式改为：

```python
output = app.invoke(
    state_in,
    config={"configurable": {"thread_id": f"eval_{case_id}_..."}},
)
```

修复后，30 条冷启动评测能真实进入 Evidence Packet Builder、Orchestrator、Agent 和 Guard 流程。

#### 3. 动态入库只解决重复写入，没有解决重复采集

`workflow.evidence_packet_builder` 接入 `upsert_packet(packet)` 后，冷启动结果可以写回 FAISS。但评测中每个 case 都独立调用 `app.invoke()`，即使 case 001 已经把 `0700.HK` 的 facts 入库，case 002 仍可能因为 RAG 相似度低于阈值再次触发冷启动采集：

```text
Top RAG distance/similarity: ... / 0.4055 (threshold=0.55)
```

根因是去重只发生在入库阶段，不能阻止 `collect_all()` 重复发起 yfinance 网络请求。

修复：

- 在 `collect_all()` 增加进程级 `_collector_cache`。
- 同一 symbol 在 TTL 内命中缓存时直接返回上次采集结果。
- 只缓存非空成功结果，并打印 cache hit 日志。

当前定位：

- 这是评测和单进程运行的有效优化。
- 中长期仍需升级为基于 Fact Store、字段覆盖和 TTL 的采集判定，而不是只依赖 RAG similarity。

#### 4. 入库去重统计不准确

`RagRetriever.add_document()` 已能识别重复 `doc_id` 并跳过，但 `upsert_packet()` 初版仍将重复文档计入 `ingested`，导致统计不准确。

修复：

- `add_document()` 返回新增是否成功。
- `upsert_packet()` 根据返回值分别统计 `ingested` 和 `skipped`。

验证现象：

```text
Document already exists, skipped: ...
Ingestion: ingested=0 skipped=7
```

#### 5. 过期过滤可能挤掉有效结果

`retrieve_with_scores(k=5)` 初版先取 top-k 再过滤过期文档。如果 top-5 中有过期数据，后续有效文档没有机会返回。

修复：

- 检索时 over-fetch，例如 `max(k * 3, k + 10)`。
- 过滤过期文档后再截断到 `k`。
- `retrieve()` 和 `retrieve_with_scores()` 均应用相同策略。

#### 6. 低证据等级仍跑完整链路，评测成本过高

在 `allowed_output_level=limited_analysis` 或 `insufficient_evidence` 时，Orchestrator 初版仍可能继续跑完整链路，包括 `portfolio_agent`、`backtesting_agent` 和 `recommendation_agent`。这导致：

- 冷启动评测耗时过长。
- 港股或 yfinance 不稳定时，Backtesting 反复下载失败。
- 证据不足时仍触发无意义的 LLM 推理。

修复：

- `insufficient_evidence` / `data_summary_only`：直接进入 Guard 拒答。
- `limited_analysis`：仅运行必要分析链路，跳过 `portfolio_agent`、`backtesting_agent`、`recommendation_agent`。
- Guard 对低证据场景不再无意义 retry strategy。

当前行为示例：

```text
Evidence level=limited_analysis (score=86).
Analysis done. Routing to Guard (skipping portfolio/backtest/recommendation).
```

#### 7. Guard retry 策略需要区分“证据不足”和“输出不合规”

早期 Guard 失败后，Orchestrator 会统一重跑 `strategy -> risk -> recommendation`。但当失败原因是：

```text
INSUFFICIENT_EVIDENCE: no machine-verified facts in cold start
```

重跑 LLM 没有意义，因为根因是证据不足，而不是输出格式或 grounding 错误。

修复：

- 对 `insufficient_evidence` 直接 END / 拒答。
- 只有 `ungrounded claim`、`fabricated_or_unsupported` 等输出不合规问题才允许 retry。

#### 8. `reject_accuracy` 评测指标定义不合理

30 条评测首次真实跑通后，出现：

```text
Avg Hallucination Rate: 0.0%
Source Traceability: 100.0%
Cold Start Coverage: 100.0%
Output Level Accuracy: 96.7%
Reject Accuracy: 0.0%
```

检查后发现 `Reject Accuracy` 不是系统失败，而是评测定义有误。初版从 `expected_output_levels` 推断 `should_reject`：

```python
reject_levels = {"insufficient_evidence", "data_summary_only"}
return bool(set(expected_output_levels) & reject_levels)
```

如果某个 case 允许：

```json
["insufficient_evidence", "data_summary_only", "limited_analysis"]
```

它也会被标记为 `should_reject=True`。但系统输出 `limited_analysis` 且没有 forbidden terms 时，实际不应算拒答失败。

修复：

- 在 eval case 中显式使用 `should_reject`，不要从 expected levels 隐式推断。
- 允许 `limited_analysis` 的 case，`reject=False` 属于正确结果。

修复后单条验证中：

```text
Reject Accuracy: 100.0%
Output Level Accuracy: 100.0%
```

#### 9. RAG 已动态入库，但 symbol-aware retrieval 仍需加强

当前 FAISS 已保存动态入库 facts，且有 `doc_id` 去重和 `expires_at` 过滤。但评测中仍多次出现：

```text
5 RAG results filtered out (symbol mismatch with AMD)
Cold Start: True
```

说明即使索引中已有目标 symbol 的 facts，top-k 语义检索仍可能先返回其他股票结果，导致目标 symbol 结果被挤出。

后续改进方向：

- 检索时 over-fetch 后按 symbol 过滤。
- 支持 metadata filter / symbol-aware retrieval。
- 在 Evidence Builder 中先查结构化 Fact Store，再用 RAG 做语义补充。
- 冷启动判定从“RAG similarity 阈值”升级为“字段覆盖 + TTL + symbol 匹配”。

#### 10. 当前评测结论

完整冷启动评测已跑通，最新 30 条结果显示核心防幻觉指标达标：

```text
Results: 30
Avg Hallucination Rate: 0.0%
Source Traceability: 100.0%
Cold Start Coverage: 100.0%
Output Level Accuracy: 96.7%
```

其中 `Output Level Accuracy` 未达 100% 的主要原因是个别 case 的预期较保守，例如 `BAC` 在拿到较多可追溯 facts 后输出 `full_analysis`，但测试预期未包含 `full_analysis`。这更像评测集期望需要校准，而不是防幻觉链路失败。

#### 11. 仍需进入下一阶段的问题

本轮修复证明 v4 防幻觉闭环可运行，但也暴露出系统质量的下一层瓶颈：

1. 当前市场和基本面 facts 主要依赖 yfinance，数据源单点风险明显。
2. 港股与部分美股下载稳定性受网络、代理和 yfinance 限制影响。
3. 基本面关键字段仍经常缺失：
  - `pe_ratio`
  - `market_cap`
  - `revenue_growth_yoy`
  - `eps_growth_yoy`
4. RAG 当前更接近“动态事实缓存”，还不是完整数据治理型知识库。

下一阶段建议：

- 接入 Polygon、Tiingo、Alpha Vantage、SEC EDGAR、HKEX 等备用数据源。
- 建立 Provider 抽象层和字段级 source priority。
- 引入结构化 Fact Store，和 FAISS RAG 分层治理。
- 用字段覆盖、TTL、source quality 替代单纯 similarity 阈值作为冷启动判定依据。

---

### H.15 下一阶段整体架构优化：从动态 RAG 到数据治理型知识库

本轮 v4 修复完成后，系统已经从“静态 RAG + Agent 自行取数”升级为“Evidence Packet 前置 + 动态 RAG 事实缓存 + Guard 硬规则”。下一阶段的目标不是继续增加 Agent，而是升级数据层，让系统拥有更稳定、更可审计的事实来源。

#### 目标架构

```text
外部数据源
  ├── SEC EDGAR        官方美股财报与 filing
  ├── Polygon          行情、估值、新闻（付费增强）
  ├── Tiingo           行情、新闻、基本面补充
  ├── Alpha Vantage    基础 overview / valuation / income statement
  ├── HKEX             港股公告与公司资料
  └── yfinance         免费兜底源
        │
        ▼
Provider Adapter 层
  ├── 字段标准化为 Fact
  ├── source priority
  ├── as_of_date / retrieved_at / expires_at
  ├── confidence_tier
  └── raw_payload_hash / source_url
        │
        ▼
Normalized Fact Store
  ├── symbol + field + period 唯一键
  ├── 字段级 TTL
  ├── 多源冲突检测
  ├── 质量门槛和 license scope
  └── 审计日志
        │
        ├── Evidence Packet Builder
        │      └── 以字段覆盖 + TTL + source quality 决定是否补采
        │
        └── Vector Index / RAG
               └── 负责语义召回和上下文补充，不再作为唯一事实源
```

#### Provider 抽象建议

短期不要把 Polygon、Tiingo、Alpha Vantage 的调用直接写进 `data_collector.py`。建议新增 Provider 接口：

```python
class DataProvider:
    name: str
    priority: int

    def collect_market(self, symbol: str) -> list[Fact]: ...
    def collect_fundamentals(self, symbol: str) -> list[Fact]: ...
    def collect_news(self, symbol: str) -> list[Fact]: ...
    def collect_filings(self, symbol: str) -> list[Fact]: ...
```

每个 Provider 只负责把自己的 API 输出转换成标准 `Fact`，不直接参与最终分析决策。

#### 数据源优先级


| 数据类别    | 优先级建议                                        | 目标字段                                               |
| ------- | -------------------------------------------- | -------------------------------------------------- |
| 美股官方财报  | SEC EDGAR > Polygon/Alpha Vantage > yfinance | `revenue_growth_yoy`, `eps_growth_yoy`, filing URL |
| 估值与公司概况 | Polygon / Alpha Vantage > Tiingo > yfinance  | `pe_ratio`, `market_cap`, `pb_ratio`, sector       |
| 行情与技术指标 | Polygon / Tiingo > yfinance                  | `current_price`, `rsi_14`, `macd`, volatility      |
| 新闻      | Tiingo / Polygon > yfinance news             | `news_headline`, source URL, publisher             |
| 港股      | HKEX > yfinance                              | filing、公告、公司资料                                     |


#### 冷启动判定升级

当前冷启动主要依赖：

```text
RAG similarity < threshold
或 symbol metadata 不匹配
```

下一阶段应改为：

```text
required_fields coverage + field TTL + source quality + conflict status
```

示例：

1. 如果 `current_price` 未过期，但 `pe_ratio`、`market_cap` 缺失，只补采基本面 Provider。
2. 如果 `news_headline` 过期，只补采新闻 Provider。
3. 如果 SEC 与 yfinance 对同一字段冲突，进入 `conflicts`，不用于强结论。
4. 如果 Fact Store 已有未过期 facts，RAG similarity 低也不应触发全量 `collect_all()`。

#### RAG 的新定位

当前 FAISS RAG 已经可以动态写入 facts，但仍更接近“动态事实缓存”。下一阶段应明确分工：

- **Fact Store**：事实真相源，用于 Evidence Packet、Guard、评测和审计。
- **Vector Index / RAG**：语义召回层，用于补充上下文、相似历史分析、文档片段。
- **Document Store**：保存原始公告、财报片段、新闻正文和 provider raw payload。

这样可以避免把向量相似度误当作事实可信度。

#### 建议实施顺序

```text
Step 1: 建 Provider 抽象层，把 yfinance 包装成 YFinanceProvider
Step 2: 接入 SEC EDGAR，优先补美股 revenue / EPS / filing source
Step 3: 接入 Alpha Vantage 或 Polygon，补 pe_ratio / market_cap / overview
Step 4: 建 SQLite facts 表，保存标准 Fact、TTL、source、hash
Step 5: Evidence Builder 先查 Fact Store，再决定是否调用 Provider
Step 6: RAG 改为 symbol-aware retrieval，作为上下文补充
Step 7: Guard 从 Fact Store + Evidence Packet 做 grounding
Step 8: 重跑 30 条冷启动评测，重点观察 missing critical fields 是否下降
```

#### 阶段验收指标


| 指标                      | 当前关注点                                                            | 目标                 |
| ----------------------- | ---------------------------------------------------------------- | ------------------ |
| Critical field coverage | `pe_ratio`, `market_cap`, `revenue_growth_yoy`, `eps_growth_yoy` | 明显高于 yfinance-only |
| Source traceability     | 每个 Fact 有 source/source_url/as_of_date                           | ≥ 90%              |
| Conflict detection      | 多源同字段冲突可检测                                                       | 100% 标记            |
| Cold start latency      | 同 symbol 多问题不重复全量采集                                              | 单 symbol 首次采集后缓存命中 |
| Hallucination rate      | 不可追溯事实比例                                                         | ≤ 15%，继续保持 0-低位    |


