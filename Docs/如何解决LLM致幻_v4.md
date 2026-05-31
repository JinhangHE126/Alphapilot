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

| # | 问题 | 当前影响 | 需要补齐的能力 |
|---|------|----------|----------------|
| 1 | RAG 检索为空或低质量 | Agent 缺少可靠上下文，容易自由推理 | 检索结果需要返回 score、source、metadata |
| 2 | 工具输出不是统一证据对象 | 多个 Agent 可能基于不同上下文得出不一致结论 | 引入统一 Evidence Packet |
| 3 | PDF / API 数据缺少字段级来源 | 无法判断结论是否真的有依据 | 每个关键字段保留来源、日期、单位和置信度 |
| 4 | 知识库没有时效治理 | 旧价格、旧新闻、旧财报可能污染后续分析 | 入库时记录 TTL、版本、数据类型和更新时间 |
| 5 | Guardrail 偏 prompt 化 | 模型仍可能越过约束生成建议 | 输出前增加结构化证据充分性检查 |

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

| 模块 | 当前行为 | v4 改后行为 |
|------|---------|------------|
| `workflow.py` (StateGraph) | Orchestrator 直连 Agent | 新增 `evidence_packet_builder` 节点，在 Orchestrator 之前执行 |
| Agent prompt | "先用 RAG 再调工具" | "从 `state.evidence_packet` 读取上下文，禁止独立调 RAG" |
| `retrieve_knowledge` 工具 | Agent 自主调用 | 仅 `evidence_packet_builder` 节点使用，从 Agent tool list 中移除 |
| `state` schema | 无证据字段 | 增加 `evidence_packet: Optional[dict]` |

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

| 条件 | 处理方式 |
|------|----------|
| RAG 返回空结果 | 触发外部数据采集 |
| RAG 最高相似度低于阈值（建议初始值 0.55-0.65，需评测集校准） | 触发外部数据采集 |
| RAG 命中但缺少 `symbol`、`source`、`date` 等元数据 | 触发补充采集 |
| 用户请求涉及实时价格、最新财报、重大新闻 | 即使 RAG 命中，也需要实时数据校验 |

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

| 子项 | 计算方式 |
|------|---------|
| `source_diversity` | `min(100, 已覆盖数据源数 / 期望数据源数 × 100)`，期望数按 request_type 设定（基本面 ≥2，技术面 ≥1） |
| `recency` | 全部在 24h 内→100，7d 内→80，30d 内→60，有超过 90d→30，有超过 180d→10 |
| `completeness` | `min(100, 已填充字段数 / 期望字段数 × 100)`，期望数按 request_type 设定 |
| `field_confidence_avg` | `mean(fact.confidence for fact in facts) × 100` |

### 5.3 字段级要求

| 字段 | 必要性 | 说明 |
|------|--------|------|
| `field` | 必需 | 标准化字段名，枚举约束，避免模型自由命名 |
| `value` | 必需 | 原始值，不应让 LLM 自行补全 |
| `unit` | 必需 | USD、HKD、percent、shares、ratio 等（枚举约束） |
| `period` | 必需 | latest、FY2025、Q1_2026、TTM 等 |
| `source` | 必需 | 枚举值，不允许空来源事实进入报告 |
| `source_url` | 推荐 | 官方文件、新闻或网页链接 |
| `as_of_date` | 必需 | 数据对应日期，非采集日期 |
| `confidence` | 必需 | 字段级置信度 |
| `confidence_tier` | 必需 | `machine` / `llm_extracted` / `llm_inferred`，决定下游信任权重 |

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

| 置信度来源 | 标记 | 评分规则 | 下游信任度 |
|-----------|------|---------|:---:|
| API 数值（yfinance 价格） | `machine` | 基础 0.95，字段缺失扣 0.1，API 报错即排除 | 高 |
| API 数值（yfinance 基本面） | `machine` | 基础 0.85（基本面可能滞后），字段缺失扣 0.1 | 中高 |
| LLM 从 PDF 抽取（表格数据） | `llm_extracted` | 基础 0.75，未带页码引用扣 0.15，数值范围溢出扣 0.3 | 中 |
| LLM 从 PDF 抽取（叙述性文本） | `llm_extracted` | 基础 0.55，无原文引用即 0 | 低 |
| LLM 推理/计算 | `llm_inferred` | 基础 0.4，仅作参考 | 极低 |

### 6.3 PDF 抽取增强

`fundamental_tools.py` 当前只取 PDF 前 8000 字，风险是遗漏表格后的关键数据。建议增强：

- **分页处理**：每页独立 LLM 抽取 → 跨页合并去重
- **页码引用**：每个抽取字段附带 `page_number`
- **表格优先**：先检测 `fitz.Table` 结构化提取，失败再走 LLM fallback
- **边界校验**：revenue 抽取值超出合理范围（相对上季度 ±80%），标记可疑

---

## 7. 验证与冲突处理

### 7.1 按字段类型分流的冲突处理矩阵（v4 扩展）

| 字段类型 | 冲突判定阈值 | 处理规则 |
|---------|:----------:|----------|
| **实时价格** | 偏差 > 2% | 以最近更新的 API 为准，标记另一来源过期 |
| **财报数据**（营收、EPS 等） | 偏差 > 5% | 官方披露优先，第三方标记为口径差异 |
| **估值指标**（P/E、P/B 等） | 偏差 > 10% | 均为第三方计算，标记冲突且不用于强结论 |
| **新闻/情绪** | 定性 | 单一来源允许引用，标记为未交叉验证 |
| **实时价格（缓存超 TTL）** | TTL 过期 | 重新采集，不使用旧缓存 |

### 7.2 通用规则

| 场景 | 处理方式 |
|------|----------|
| 官方披露和第三方 API 冲突 | 财报类：优先官方；价格类：优先时效性最新的 |
| 两个第三方数据源冲突 | 标记为 conflict，不用于强结论 |
| 字段缺少 period 或 unit | 降低字段级 confidence 0.2，必要时排除 |
| 新闻类信息只有单一来源 | 允许引用，但必须标记为未交叉验证 |
| 实时价格超过缓存 TTL | 重新采集，不使用旧缓存 |

---

## 8. 多 Agent 角色调整

不建议在 Phase 1 过早拆出过多 Agent。早期重点是工具链和数据结构稳定。

| 角色 | Phase 1 建议 | 职责 |
|------|--------------|------|
| RAG Retriever | 增强现有模块 | 返回 `Document + score + metadata`（symbol、source、date） |
| Data Collector | 新增工具函数 | 拉取价格、基本面、PDF 或公告，产出原始事实 dict |
| Evidence Builder | 新增纯函数/服务 | 将 RAG 和工具结果归一化为 Evidence Packet（含评分计算） |
| Guard | 增强现有 Guard Agent | 硬规则判断输出等级 + 确定性熔断；LLM 仅做自然语言润色 |
| Verifier / Critic | Phase 2 引入 | 跨来源校验、冲突解释和字段级质量评分 |

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

| `allowed_output_level` | 触发条件（硬规则） | 允许输出 |
|------------------------|-------------------|----------|
| `full_analysis` | evidence_score ≥ 70，关键字段齐全，无未解决冲突 | 完整基本面分析，可有条件判断 |
| `limited_analysis` | 有部分可靠数据，但缺少关键字段 | 数据事实 + 谨慎分析 + 明确缺失项 |
| `data_summary_only` | evidence_score 30-50 或只有市场数据 | 只输出事实摘要和来源，**不输出投资判断** |
| `insufficient_evidence` | evidence_score < 30 或无 machine 级事实 | **拒绝分析**，说明缺失数据 |

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

| 数据类型 | 存储 | TTL | 合并策略 |
|---------|------|-----|---------|
| **market_data** | TimescaleDB + Redis 缓存 | 实时：5min / 日线：24h | 同 `as_of_date` 覆盖 |
| **fundamental_data** | PostgreSQL（结构化）+ 向量库（文本） | 财报级：180d / 预估：30d | 按 period + field 去重 |
| **news_data** | 向量库 | 30d | 按 URL / title hash 去重 |
| **filings** | 向量库 + 元数据表 | 永久（带版本） | 版本追加，按日期链式关联 |

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

| 阶段 | 操作 | 预估延迟 |
|------|------|:---:|
| RAG 检索 | FAISS 本地向量检索 | 0.2-0.5s |
| Data Collector | yfinance 市场 + 基本面 | 1-3s |
| Data Collector | PDF 下载（~2MB） | 2-5s |
| Data Collector | NewsAPI / web_search | 1-3s |
| Evidence Builder | LLM 抽取 + 归一化 | 2-5s |
| Guard | 硬规则判定 | <0.1s |
| **冷启动总延迟** | **（并行采集）** | **5-10s** |
| **热路径总延迟** | **（命中 RAG）** | **1-3s** |

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

| 模块 | 当前状态 | 改造 |
|------|----------|------|
| `rag/retriever.py` | `retrieve` 只返回 Document | 新增 `retrieve_with_scores`，返回 `doc + score + metadata` |
| `tools/rag_tools.py` | 拼接文本给 Agent | 返回结构化 JSON；从 Agent tool list 中移除（仅 Builder 使用） |
| `fundamental_tools.py` | LLM 从 PDF 前 8000 字抽取 JSON | 分页抽取、页码引用、`confidence_tier` 标记、边界校验 |
| `workflow.py` (StateGraph) | Orchestrator 直连 Agent | 新增 `evidence_packet_builder` 节点；Agent 从 state 读取 Packet |
| `schemas/evidence_packet.py` | 不存在 | 新增完整 Pydantic Schema + Guard 硬规则 + 渲染函数 |
| `tools/data_collector.py` | 不存在 | 新增 Data Collector 工具函数 |
| Agent prompts | "先用 RAG 再调工具" | "从 Evidence Packet 读取上下文，禁止独立调 RAG 或外部工具" |
| Guard Agent | prompt 约束 | 增加 `allowed_output_level` 硬规则判定 + 熔断逻辑 |

---

## 15. 分阶段实施路线

### Phase 1：MVP 防幻觉闭环，3-4 周（v4 重估）

目标：冷启动时不再进入纯 LLM 分析；证据不足时降级或拒答。

| 周 | 主要工作 |
|:--:|----------|
| W1 | RAG 返回 score + metadata；Evidence Packet Pydantic Schema；Guard 硬规则函数 |
| W2 | 新增 `evidence_packet_builder` 节点；Data Collector 工具函数（yfinance + PDF） |
| W3 | StateGraph 改造；Agent prompt 切换为读取 Evidence Packet；Agent tool list 移除 RAG 工具 |
| W4 | 渲染函数 + 报告模板；端到端测试 + 冷启动场景评测 |

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

| 指标 | 定义 | 目标值 (Phase 1) |
|------|------|:---:|
| **幻觉率** | 含不可追溯事实的回答数 / 总回答数 | ≤ 15% |
| **拒答准确率** | 证据不足时正确拒答 / 应拒答总数 | ≥ 90% |
| **来源追溯率** | 可追溯到 Evidence Packet 字段的结论数 / 总结论数 | ≥ 85% |
| **冷启动覆盖率** | 冷启动时成功构造 Packet 的比例 | ≥ 80% |

---

## 17. 多市场支持（v4 新增）

Evidence Packet 的 `source` 字段需按市场扩展：

| 市场 | 价格数据 | 基本面/财报 | 公告/新闻 |
|------|---------|-----------|----------|
| 美股 | yfinance, Alpha Vantage, Polygon.io | SEC EDGAR | NewsAPI, Google News |
| 港股 | yfinance (延迟), HKEX API | HKEX 公告板 | 港交所披露易 |
| A 股 | akshare, tushare | 巨潮资讯 / 上交所/深交所 | 东方财富 / 同花顺 |
| 日股 | yfinance | 东京证交所 EDINET | Nikkei, Reuters |
| 欧股 | yfinance | 各国监管披露系统 | Reuters, Bloomberg |

---

## 18. 风险与限制

| 风险 | 说明 | 缓解方式 |
|------|------|----------|
| 外部 API 质量不稳定 | 免费数据源可能延迟、字段缺失或限流 | 逃生舱：降级到 RAG-only 或拒答 |
| LLM 抽取 PDF 仍可能出错 | 模型可能误读表格或遗漏页后数据 | 分页抽取 + 页码引用 + `confidence_tier` |
| FAISS 相似度 ≠ 事实相关性 | all-MiniLM-L6-v2 对金融文本分辨力有限 | Phase 2 接入 reranker 或金融 embedding |
| 多 Agent 复杂度 | 新增 Builder 节点增加链路长度 | Builder 保持纯函数，仅加一个 StateGraph 节点 |
| 旧数据污染知识库 | 股票数据强时效性 | 分库 TTL + 低质量不入库 + 版本化 |
| 合规风险 | 投资建议需监管和免责声明 | 证据不足时硬规则拒答，保留完整日志 |
| 冷启动延迟 | 外部 API 5-10s | 并行请求 + 进度提示 + 超时逃生 |

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

| # | 内容 | 优先级 |
|---|------|:--:|
| A | Evidence Packet Pydantic Schema 完整代码（含校验逻辑） | **高** |
| B | `retrieve_with_scores` 改造方案 + 重索引脚本 | **高** |
| C | Guard 硬规则函数单元测试用例 | **高** |
| D | `evidence_packet_builder` 节点 LangGraph 伪代码 | **高** |
| E | Data Collector 工具接口设计（yfinance / PDF / news） | 中 |
| F | 冷启动评测集 20 只股票 + 100 个问题 | 中 |
| G | 生产监控指标 Prometheus / Grafana 配置 | 中 |