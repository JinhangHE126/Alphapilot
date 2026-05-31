# 股票分析系统冷启动防幻觉优化方案

> **副标题**：Hybrid RAG + Evidence Packet 的可审计证据约束机制
>
> **版本**：v3.0
>
> **日期**：2026-05-31
>
> **作者**：Jinhang HE
>
> **修订目标**：将方案从“彻底解决幻觉”的乐观表述，调整为“显著降低冷启动幻觉，并在证据不足时明确降级或拒答”的工程可落地方案。

## 1. 问题背景与目标边界

现有 RAG 机制在知识库覆盖充分时可以降低模型自由发挥的风险；但当目标股票在知识库中没有历史资料、财报、公告或研报时，系统容易退化为纯 LLM 生成。此时模型可能把行业常识、过期信息或相似公司信息误当作目标公司的事实。

本方案的核心目标不是“消灭幻觉”，而是建立一套可审计的证据约束流程：

- 冷启动时先采集数据，再生成分析。
- 所有关键结论必须能追溯到 Evidence Packet 中的字段级证据。
- 证据不足时，系统必须降级输出数据摘要、缺失清单和风险提示，不能生成强投资判断。
- 冷启动采集结果可以沉淀到知识库，但必须带有效期、来源、版本和 `as_of_date`，不能被视为永久有效事实。

## 2. 根因分析

| # | 问题 | 当前影响 | 需要补齐的能力 |
|---|------|----------|----------------|
| 1 | RAG 检索为空或低质量 | Agent 缺少可靠上下文，容易自由推理 | 检索结果需要返回 score、source、metadata |
| 2 | 工具输出不是统一证据对象 | 多个 Agent 可能基于不同上下文得出不一致结论 | 引入统一 Evidence Packet |
| 3 | PDF / API 数据缺少字段级来源 | 无法判断结论是否真的有依据 | 每个关键字段保留来源、日期、单位和置信度 |
| 4 | 知识库没有时效治理 | 旧价格、旧新闻、旧财报可能污染后续分析 | 入库时记录 TTL、版本、数据类型和更新时间 |
| 5 | Guardrail 偏 prompt 化 | 模型仍可能越过约束生成建议 | 输出前增加结构化证据充分性检查 |

## 3. 总体架构

推荐采用 `Hybrid RAG + Tool-Use + Evidence Packet + Guardrail`。相比单纯增加 Agent，重点应放在“证据对象”和“输出约束”上。

```text
用户请求
  |
  v
Ticker / 意图识别
  |
  v
RAG 检索
  |
  +-- 命中且质量足够 --> 生成 Evidence Packet
  |
  +-- 空结果 / 低分 / 元数据不足 --> 调用外部数据工具
                                  |
                                  v
                         生成 Evidence Packet
                                  |
                                  v
                         字段级校验与冲突检测
                                  |
                                  v
                         Guardrail 决定输出等级
                                  |
                                  v
                         分析报告 / 降级报告 / 拒答
                                  |
                                  v
                         按质量异步入库
```

### 3.1 冷启动触发条件

Phase 1 不建议设计过复杂的置信度模型，先使用清晰的规则：

| 条件 | 处理方式 |
|------|----------|
| RAG 返回空结果 | 触发外部数据采集 |
| RAG 最高相似度低于阈值 | 触发外部数据采集 |
| RAG 命中但缺少 `symbol`、`source`、`date` 等元数据 | 触发补充采集 |
| 用户请求涉及实时价格、最新财报、重大新闻 | 即使 RAG 命中，也需要实时数据校验 |

注意：当前 RAG 检索如果只返回文本而不返回相似度，则无法实现“低于阈值触发”。需要优先把检索接口升级为返回 `Document + score + metadata`。

## 4. Evidence Packet 设计

Evidence Packet 是所有下游 Agent 的唯一事实底座。它不是简单的上下文拼接，而是一个带来源、时间、质量和缺失信息的结构化证据对象。

### 4.1 最小可用 Schema

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
      "confidence": 0.85
    },
    {
      "field": "revenue_growth_yoy",
      "value": 34.2,
      "unit": "percent",
      "period": "FY2025",
      "source": "SEC EDGAR 10-K",
      "source_url": "https://www.sec.gov/...",
      "as_of_date": "2025-12-31",
      "confidence": 0.9
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
  "allowed_output_level": "limited_analysis"
}
```

### 4.2 字段级要求

| 字段 | 必要性 | 说明 |
|------|--------|------|
| `field` | 必需 | 标准化字段名，避免模型自由命名 |
| `value` | 必需 | 原始值，不应让 LLM 自行补全 |
| `unit` | 必需 | 例如 USD、HKD、percent、shares |
| `period` | 必需 | latest、FY2025、Q1 2026、TTM 等 |
| `source` | 必需 | 数据来源，不允许空来源事实进入报告 |
| `source_url` | 推荐 | 官方文件、新闻或网页链接 |
| `as_of_date` | 必需 | 数据对应日期，而不是采集日期 |
| `confidence` | 必需 | 字段级置信度，不等同于整份报告置信度 |

## 5. 验证与冲突处理

原方案中的“同一指标至少两个来源一致方采纳”方向正确，但不应机械执行。金融数据经常因为口径不同而不一致，例如 TTM、FY、GAAP、Non-GAAP、币种和拆股调整都会影响结果。

更合理的规则是：

| 场景 | 处理方式 |
|------|----------|
| 官方披露和第三方 API 冲突 | 优先采用官方披露，并记录第三方冲突 |
| 两个第三方数据源冲突 | 标记为 conflict，不用于强结论 |
| 字段缺少 period 或 unit | 降低置信度，必要时排除 |
| 新闻类信息只有单一来源 | 允许引用，但必须标记为未交叉验证 |
| 实时价格超过缓存 TTL | 重新采集，不使用旧缓存 |

## 6. 多 Agent 角色调整

不建议在 Phase 1 过早拆出过多 Agent。早期重点是工具链和数据结构稳定，Agent 数量可以保持克制。

| 角色 | Phase 1 建议 | 职责 |
|------|--------------|------|
| RAG Retriever | 增强现有模块 | 返回文档、分数、来源、日期和 ticker metadata |
| Data Collector | 新增工具或轻量 Agent | 拉取价格、基本面、PDF 或公告，并产出原始事实 |
| Evidence Builder | 新增纯函数 / 服务 | 将 RAG 和工具结果归一化为 Evidence Packet |
| Guard | 新增结构化检查 | 判断输出等级：正常分析、有限分析、数据摘要、拒答 |
| Verifier / Critic | Phase 2 再拆分 | 做跨来源校验、冲突解释和质量评分 |

## 7. 输出策略

报告不应只依赖 prompt 约束，而应由 `allowed_output_level` 控制。

| `allowed_output_level` | 触发条件 | 允许输出 |
|------------------------|----------|----------|
| `full_analysis` | 官方财报 / 结构化数据充分，关键字段来源完整 | 完整基本面分析，可给出有条件判断 |
| `limited_analysis` | 有部分可靠数据，但缺少关键字段 | 数据事实 + 谨慎分析 + 明确缺失项 |
| `data_summary_only` | 只有市场数据或少量新闻 | 只输出事实摘要和来源，不输出投资判断 |
| `insufficient_evidence` | 无可靠来源或冲突严重 | 拒绝分析，并说明缺失数据 |

### 7.1 推荐报告模板

```text
# 分析报告：NVDA

## 证据状态
- 本次为冷启动分析：是
- 证据等级：limited_analysis
- 数据日期：2026-05-31
- 主要来源：yfinance、SEC EDGAR

## 已验证事实
- 当前价格：120.5 USD，来源：yfinance，日期：2026-05-31
- FY2025 营收同比增长：34.2%，来源：SEC EDGAR 10-K，日期：2025-12-31

## 缺失或不完整信息
- analyst_estimates：未配置授权数据源
- latest_10K_details：未成功获取完整官方文件

## 分析结论
基于现有证据，可以进行有限基本面分析，但不形成强投资建议。

## 风险提示
本报告依赖当前可用数据。缺失字段可能显著影响估值、盈利预测和风险判断。
```

## 8. 与当前代码的落地关系

当前项目已经具备三个基础条件：

- 已有本地 FAISS RAG。
- 已有 `retrieve_knowledge` 工具。
- 已有基于 LangGraph ReAct 的 `fundamental_agent`。

但要实现本方案，需要优先补齐以下改造点：

| 模块 | 当前状态 | 建议改造 |
|------|----------|----------|
| `rag/retriever.py` | `retrieve` 只返回 Document | 增加 `retrieve_with_scores`，返回 `doc + score + metadata` |
| `tools/rag_tools.py` | 只拼接文本 | 返回结构化 JSON，至少包含 source、score、doc_id |
| `fundamental_tools.py` | LLM 从 PDF 前 8000 字抽取 JSON | 增加页码引用、字段来源和解析失败字段 |
| `fundamental_agent.py` | prompt 要求先 RAG 后工具 | 改为先构造 Evidence Packet，再基于 Packet 输出 |
| 报告输出 | 主要依赖 prompt | 增加 Guard 根据证据等级控制输出 |

## 9. 分阶段实施路线

### Phase 1：MVP 防幻觉闭环，1-2 周

目标：降低冷启动时模型自由发挥的概率。

主要工作：

- RAG 返回分数和 metadata。
- 增加 Evidence Packet Pydantic Schema。
- 冷启动时接入一个稳定外部数据源，例如 yfinance 或 Alpha Vantage。
- 增加 `allowed_output_level` 规则。
- 修改 fundamental agent，让它只能基于 Evidence Packet 输出。

预期效果：

- 空 RAG 不再直接进入纯 LLM 分析。
- 证据不足时可以降级输出或拒答。
- 报告中的核心事实可以追溯到来源。

### Phase 2：质量与入库治理，2-4 周

目标：让冷启动结果可复用，但不污染知识库。

主要工作：

- 增加字段级 TTL 和 `as_of_date`。
- 将高质量 Evidence Packet 异步写入结构化存储和向量库。
- 增加冲突检测和数据源优先级。
- 引入用户反馈和人工 review 队列。

预期效果：

- “第一次分析后可复用”，但不是“永久有效”。
- 旧数据和低质量数据不会直接污染后续分析。

### Phase 3：生产级增强，1-2 个月

目标：提升稳定性、审计能力和覆盖率。

主要工作：

- 接入官方披露源，例如 SEC EDGAR、HKEX 公告。
- 接入监控指标：冷启动比例、证据不足率、拒答率、字段缺失率。
- 建立评测集，使用 RAGAS / LLM-as-Judge / 人工抽检评估幻觉率。
- 根据业务预算决定是否接入 Bloomberg、Refinitiv、FactSet 等机构级数据源。

## 10. 风险与限制

| 风险 | 说明 | 缓解方式 |
|------|------|----------|
| 外部 API 质量不稳定 | 免费数据源可能延迟、字段缺失或限流 | 缓存、重试、来源优先级和降级输出 |
| LLM 抽取 PDF 仍可能出错 | 模型可能误读表格或遗漏页后数据 | 页码引用、表格解析、字段级置信度 |
| 多 Agent 增加复杂度 | Agent 过多会让调试和审计变难 | Phase 1 保持轻量，优先用纯函数和结构化 schema |
| 旧数据污染知识库 | 股票数据强时效，不能永久有效 | TTL、版本化、`as_of_date` 和数据类型隔离 |
| 合规风险 | 投资建议有监管和免责声明要求 | 证据不足时拒绝强建议，保留日志和来源 |

## 11. 总结

本方案技术方向可行，但应避免把“多 Agent”本身当成防幻觉的核心。真正关键的是建立可审计的证据对象、字段级来源、时效治理和输出熔断机制。

推荐的落地顺序是：

1. 先让 RAG 和工具输出结构化证据。
2. 再用 Evidence Packet 统一所有下游分析上下文。
3. 最后用 Guard 根据证据充分性控制报告等级。

合理预期是：Phase 1 可以显著降低冷启动幻觉，并让系统在证据不足时更诚实；生产级稳定性则需要 Phase 2 和 Phase 3 的数据治理、监控和评测体系共同支撑。

---

## 附录：后续可补充内容

| # | 内容 | 优先级 |
|---|------|--------|
| A | Evidence Packet Pydantic Schema 完整代码 | 高 |
| B | `retrieve_with_scores` 改造方案 | 高 |
| C | Guard 输出等级规则代码 | 高 |
| D | Data Collector 工具接口设计 | 中 |
| E | Verifier / Critic Prompt 模板 | 中 |
| F | 生产监控指标和评测集设计 | 中 |
