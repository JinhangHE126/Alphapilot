# AlphaPilot 系统架构 v4.1

> 当前版本以 **Evidence Packet 前置构造 + Guard 硬规则校验 + 动态 RAG 事实缓存** 为核心。  
> 旧版“Agent 各自调工具/RAG”的模式已收敛为“Builder 统一采集证据，Agent 只消费证据”。

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        React 前端 (Vite + TS)                     │
│   Dashboard │ Analyze (SSE) │ History │ Settings │ Auth          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + SSE (JWT Bearer Token)
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI 后端 (Python 3.12)                    │
│  /auth/* │ /profile │ /sessions │ /analyze │ /history │ /dashboard │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              LangGraph StateGraph 多智能体工作流                    │
│                                                                  │
│  Evidence Packet Builder                                         │
│    → RAG 检索 → 冷启动判断 → 数据采集 → Evidence Packet 评分         │
│    → 动态入库 (FAISS facts cache, TTL, doc_id 去重)                │
│                                                                  │
│  Orchestrator                                                    │
│    → 按 allowed_output_level 分级路由                              │
│    → Market/Fundamental/News → Strategy/Risk → Guard              │
│    → full_analysis 时才进入 Portfolio/Backtest/Recommendation      │
│                                                                  │
│  持久化: SQLite (checkpointer + 业务表)                           │
│  知识库: FAISS 动态事实缓存 + ChromaDB 辅助模块                    │
│  用户画像: JSON 文件 (risk_preference, horizon)                   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 技术栈总览

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 18 + Vite + TypeScript | SPA, Vite proxy 代理 API |
| 样式 | 手写 CSS 暗色主题 | 无第三方 UI 库依赖 |
| 后端框架 | FastAPI + Uvicorn | 异步 REST + SSE 流式 |
| 多智能体 | LangGraph (StateGraph) | Evidence Builder + Orchestrator 编排 12 Agent |
| LLM 路由 | Gemini / DeepSeek / Grok | 按 Agent 类型分模型 |
| 数据库 | SQLite (WAL 模式) | 业务表 + LangGraph checkpointer |
| 向量检索 | FAISS (all-MiniLM-L6-v2) + ChromaDB | FAISS 为主流程动态事实缓存，Chroma 保留为辅助模块 |
| 防幻觉 | Evidence Packet + Guard hard rules | 输出等级门控、字段级来源追溯、冷启动拒答/降级 |
| 认证 | JWT (HS256) | register / login / refresh / me |
| 实时通信 | SSE (Server-Sent Events) | agent_start / agent_output / agent_done |
| 数据采集 | yfinance + SEC/HKEX 辅助 | 当前主链路仍以 yfinance 为主，下一阶段接 Polygon/Tiingo/Alpha Vantage |
| CI/CD | GitHub Actions + GHCR + Docker | 前后端独立镜像 + SSH 部署 |

## 3. 12 智能体体系

### 3.1 Agent 角色矩阵

| Agent | 节点名 | LLM | 工具策略 | 结构化输出 |
|-------|--------|-----|------|-----------|
| **Market** | `market_data_expert` | DeepSeek | `tools=[]`，只读 Evidence Packet | ❌ 自然语言 |
| **Fundamental** | `fundamental_expert` | DeepSeek | `tools=[]`，只读 Evidence Packet | ❌ 自然语言 |
| **News** | `news_sentiment_expert` | DeepSeek | `tools=[]`，只读 Evidence Packet | ❌ 自然语言 |
| **Strategy** | `strategy_expert` | DeepSeek | `tools=[]`，综合已验证事实与上游输出 | ❌ 自然语言 |
| **Risk** | `risk_expert` | DeepSeek | `tools=[]`，按证据等级输出风险 | JSON/自然语言混合 |
| **Portfolio** | `portfolio_agent` | DeepSeek | `tools=[]`，仅 full analysis 链路使用 | ❌ 自然语言 |
| **Backtesting** | `backtesting_agent` | DeepSeek | 内部价格下载，limited/eval 场景跳过 | ❌ 自然语言 |
| **Comparison** | `comparison_agent` | DeepSeek | `tools=[]`，专项对比入口 | ❌ 自然语言 |
| **Alert** | `alert_agent` | DeepSeek | `tools=[]`，基于 Packet 指标生成告警 | ❌ 自然语言 |
| **Portfolio Opt** | `portfolio_optimization_agent` | DeepSeek | `tools=[]`，专项组合优化入口 | ❌ 自然语言 |
| **Recommendation** | `recommendation_agent` | DeepSeek | `tools=[]`，仅 full analysis 或个性化入口使用 | ❌ 自然语言 |
| **Guard** | `guard_agent` | Python hard rules | 不调工具，基于 Evidence Packet 确定性校验 | ✅ dict (is_valid, confidence, issues, corrections) |

### 3.2 Agent 依赖拓扑

```
START
  ↓
Evidence Packet Builder
  ├── insufficient_evidence / data_summary_only → Guard → END
  ├── limited_analysis → Market + Fundamental + News → Strategy → Risk → Guard → END
  └── full_analysis → Market + Fundamental + News → Strategy → Risk
                   → Portfolio → Backtest → Recommendation → Guard → END
```

### 3.3 模型路由架构

系统通过 `config/llm.py` 的 `AGENT_LLM_ROUTES` 为每个 Agent 分配独立的 LLM profile，支持：
- **多 Provider**: Gemini / DeepSeek / Grok (OpenAI 兼容)
- **多端口代理**: 按 Agent 类型拆分入口流量 (sing-box mixed inbound)
- **差异化参数**: 每个 Agent 独立 temperature / max_retries / timeout

## 4. GraphState 全局共享状态

所有 Agent 通过 `GraphState` (TypedDict) 共享数据，核心字段：

| 字段 | 类型 | 职责 |
|------|------|------|
| `stock_symbol` | str | 当前分析股票代码 |
| `messages` | list[BaseMessage] | LangGraph 消息流 (add_messages reducer) |
| `evidence_packet` | dict | Evidence Builder 生成的字段级证据包 |
| `cold_start` | bool | 是否触发冷启动采集 |
| `ingestion_result` | dict | Evidence Packet 回写 FAISS 的统计结果 |
| `market_data` | str | Market Agent 输出 |
| `fundamental_data` | str | Fundamental Agent 输出 |
| `news_sentiment` | str | News Agent 输出 |
| `strategy_recommendation` | str | Strategy Agent 输出 |
| `risk_assessment` | str | Risk Agent 输出 |
| `executed_agents` | list[str] | 已执行 Agent 列表 (防重复) |
| `final_report` | str | 最终分析报告 |
| `final_recommendation` | str | Buy/Hold/Sell |
| `user_profile` | dict | 用户画像 (risk_preference, horizon) |
| `guard_check` | dict | Guard 校验结果 |
| `guard_retry_count` | int | Guard 重试计数 (上限 2) |
| `confidence_score` | int | 最终置信度 0-100 |
| `sources` | list[str] | 引用来源列表 |
| `memory` | dict | 跨会话长期记忆 |

## 5. 工作流编排

### 5.1 Orchestrator 路由逻辑

`orchestrator_node` 位于 `graph/workflow.py`，当前以**确定性路由**为主。路由核心不再是“用户是否要求全面分析”，而是 `EvidencePacket.allowed_output_level`：

```
输入检测:
  ├── alert / monitor / 警报        → alert_agent
  ├── portfolio optimization / 优化 → portfolio_optimization_agent
  ├── personalized / 我的偏好       → recommendation_agent
  └── 常规分析:
        Evidence level = insufficient_evidence / data_summary_only
          → guard_agent → END
        Evidence level = limited_analysis
          → market + fundamental + news → strategy → risk → guard_agent → END
        Evidence level = full_analysis
          → market + fundamental + news → strategy → risk
          → portfolio → backtesting → recommendation → guard_agent → END
```

### 5.2 LangGraph 工作流图

```
START → evidence_packet_builder → orchestrator
           ├──→ market ──────────┐
           ├──→ fundamental ─────┤
           ├──→ news ────────────┤
           ├──→ strategy ────────┤
           ├──→ risk ────────────┤──→ orchestrator (循环)
           ├──→ portfolio ───────┤
           ├──→ backtesting ─────┤
           ├──→ recommendation ──┘
           │
           └──→ guard_agent
                  ├── evidence-level hard failure → END
                  ├── valid → END
                  └── output-level soft failure → orchestrator (带 corrections，最多 2 次)
```

### 5.3 SSE 流式分析

`services/analysis_service.py` 的 `stream_analysis_events` 将 LangGraph stream 转换为 SSE 事件：

```
stream_analysis_events()
  ├── yield "analysis_start"     → 前端初始化 Agent 卡片
  ├── for chunk in langgraph_app.stream():
  │     ├── yield "agent_start"  → 卡片进入 running 动画
  │     ├── yield "agent_output" → 内容流式追加
  │     └── yield "agent_done"   → 卡片标记 done
  └── yield "analysis_complete"  → 最终报告 + recommendation
```

## 6. 数据持久化

### 6.1 SQLite 表结构

| 表 | 用途 | 关键字段 |
|----|------|---------|
| `users` | 用户认证 | id, username, password_hash, last_login |
| `sessions` | 分析会话 | id (UUID), user_id, title, updated_at |
| `messages` | 对话历史 | session_id, role, content, node_name |
| `analysis_history` | 分析记录 | user_id, stock_symbol, report, recommendation, status, final_score |
| `analysis_events` | 流式事件日志 | analysis_id, seq_num, agent_name, event_type, content |

### 6.2 LangGraph Checkpointer

`graph/checkpointer.py` 使用 SQLite 作为 LangGraph 的状态持久化后端 (`langgraph.checkpoint.sqlite.SqliteSaver`)，实现：
- 会话恢复：同一 thread_id 可继续未完成的分析
- 断点续传：工作流中断后可从中断点恢复

### 6.3 用户画像

`graph/user_profile.py` 通过 JSON 文件持久化：
- `risk_preference`: low / medium / high → 影响推荐策略激进程度
- `horizon`: short / medium / long → 影响选股时间框架
- 通过 `GET/PUT /profile` API 管理，分析时自动注入工作流

## 7. 前端架构

### 7.1 路由结构

| 路径 | 页面 | 功能 |
|------|------|------|
| `/login` | LoginPage | 登录/注册双模式 |
| `/` | DashboardPage | 统计总览 + 最近分析 |
| `/analyze` | AnalyzePage | SSE 实时分析 + Agent 进度卡片 |
| `/history` | HistoryPage | 分页列表 + 股票筛选 + 删除 |
| `/history/:id` | AnalysisDetailPage | 单次分析事件时间线 |
| `/settings` | SettingsPage | 用户画像配置 |

### 7.2 SSE 客户端

`services/sse.ts` 基于 `fetch` + `ReadableStream` 手动解析 SSE，无需 EventSource（EventSource 不支持 POST + 自定义 headers）：
1. 读取字节流 → 按 `\n\n` 分割事件
2. 解析 `event:` 和 `data:` 行
3. 触发回调更新 React state

## 8. CI/CD 流水线

```
Git Push → GitHub Actions
  ├── CI (PR / push main&dev)
  │   ├── Backend: Ruff Lint + Pytest
  │   └── Frontend: ESLint + TypeScript + Vitest + Vite Build
  └── CD (push main)
      ├── Quality Gate
      ├── Docker Build (backend + frontend 独立镜像)
      ├── Push to GHCR
      └── SSH Remote Deploy (deploy/deploy.sh)
```

---

## 9. 企业级防 LLM 致幻体系（v4 当前实现）

AlphaPilot 采用**证据前置 + 输出门控 + 后验校验**的纵深防御策略。当前核心不是依赖 Agent prompt 自律，而是让所有 Agent 只能消费 Evidence Packet 中的字段级事实。

### 9.1 防线总览

```
  Layer 0  Evidence Packet Builder
    ↓      RAG + 数据采集统一归一化为 Fact
  Layer 1  字段级证据 Schema
    ↓      source / as_of_date / confidence / confidence_tier
  Layer 2  Evidence Score + Output Level
    ↓      full / limited / data_summary / insufficient
  Layer 3  Agent 只消费 Packet
    ↓      tools=[]，禁止自行采集事实
  Layer 4  Guard hard rules
    ↓      grounding / forbidden keywords / insufficient evidence / symbol mismatch
       最终输出（带置信度、来源和降级状态）
```

### 9.2 Layer 0：Evidence Packet 前置构造

**原理**：在 Orchestrator 路由前构造统一证据对象，所有下游 Agent 都只读 `state.evidence_packet`。

**实现**：
- `evidence_packet_builder` 先调用 FAISS RAG 检索，过滤 symbol mismatch。
- RAG 不足时触发 `collect_all(symbol)` 冷启动采集。
- `collect_all()` 当前聚合 yfinance 市场/基本面/新闻，辅以 SEC/HKEX collector。
- 采集结果统一转换为 `Fact`，每个字段保留 `source`、`as_of_date`、`confidence`、`confidence_tier`。
- 高质量 Evidence Packet 会通过 `upsert_packet()` 回写 FAISS，带 doc_id 去重和 TTL。

**文件**：`graph/workflow.py`, `tools/data_collector.py`, `schemas/evidence_packet.py`, `knowledge/ingest_service.py`, `rag/retriever.py`

### 9.3 Layer 1：字段级证据 Schema

**原理**：用 Pydantic `EvidencePacket` / `Fact` 约束事实字段，而不是只约束 Agent 输出格式。

核心字段：

| 字段 | 说明 |
|------|------|
| `field` | 标准化事实字段名，例如 `current_price`, `pe_ratio` |
| `value` | 原始值，不允许 LLM 自行补全 |
| `source` | 数据来源，例如 yfinance / SEC_EDGAR / HKEX / RAG |
| `as_of_date` | 数据对应日期 |
| `confidence` | 字段级置信度 |
| `confidence_tier` | `machine` / `llm_extracted` / `llm_inferred` |

**文件**：`schemas/evidence_packet.py`

### 9.4 Layer 2：Evidence Score 与输出等级门控

**原理**：在生成分析前，根据证据充分性决定系统最多允许输出什么级别的内容。

输出等级：

| 等级 | 允许行为 |
|------|----------|
| `full_analysis` | 可运行完整分析链路 |
| `limited_analysis` | 允许谨慎分析，但禁止目标价/强推荐/未来源化数值 |
| `data_summary_only` | 只能输出事实摘要和缺失字段 |
| `insufficient_evidence` | 直接拒答或请求补充数据 |

评分因素包括 source diversity、recency、completeness、field confidence。缺少关键字段或存在冲突时会降级。

### 9.5 Layer 3：Agent 只消费 Packet

**原理**：Market / Fundamental / News 等 Agent 不再自己调 RAG 或外部 API，避免不同 Agent 基于不同证据生成矛盾结论。

当前策略：

- 主要 Agent 均为 `tools=[]`。
- Agent prompt 要求只使用 Evidence Packet。
- 缺少字段时输出 `NOT AVAILABLE` 或降级说明。
- `limited_analysis` 链路跳过 Portfolio / Backtest / Recommendation，避免过度建议。

### 9.6 Layer 4：Guard hard rules ★核心防线

**这是 AlphaPilot 防致幻体系的最后一道关**，位于工作流输出前。Guard 当前以确定性规则为主，不再依赖 RAG 工具交叉验证。

#### 工作流程

```
Agent 输出
         ↓
    guard_agent 介入
         │
    ┌────┴────┐
    │ Packet   │ ← EvidencePacket facts / missing_fields / output_level
    │ Grounding│
    └────┬────┘
         ↓
    输出 JSON:
    {
      "is_valid": true/false,
      "confidence_score": 85,
      "issues": ["EPS 数据与财报不符"],
      "corrections": ["修正: EPS growth 应为 -23%"],
      "sources": ["RAG: TSLA_Q4_2024_Earnings"]
    }
         │
    ┌────┴────────────────┐
    │ is_valid = true     │ hard failure
    │ → END               │ → END / 拒答
    │                     │
    │                     │ soft failure
    │                     │ → orchestrator
    │                     │   注入 corrections
    │                     │   重跑 strategy/risk
    │                     │         │
    │                     │   ┌─────┴──────┐
    │                     │   │ retry < 2  │ retry ≥ 2
    │                     │   │ → guard    │ → END
    │                     │   │   再次校验  │   (带低置信度警告)
    │                     │   └───────────┘
    └─────────────────────┘
```

#### 关键设计决策

| 决策 | 理由 |
|------|------|
| 冷启动无 machine fact 直接拒答 | 数据不足不是重跑 LLM 能解决的问题 |
| `limited_analysis` 禁止目标价和强推荐 | 防止证据不足时输出强投资结论 |
| Grounding 扫描关键字段和数值 | 报告提到 P/E、目标价、增长率等必须有 Packet fact |
| soft failure 才允许 retry | 仅 ungrounded claim / prohibited keyword 可通过重写修复 |
| 最大重试次数 = 2 | 防止死循环 |

**文件**：`agents/guard_agent.py`, `graph/workflow.py`

### 9.7 防线效果矩阵

| 防线 | 拦截的幻觉类型 | LLM 依赖 | 误杀率 | 当前状态 |
|------|---------------|---------|--------|---------|
| Layer 0 Evidence Builder | 冷启动纯 LLM 分析 | 非 LLM 规则 + 数据工具 | 低 | ✅ 生效 |
| Layer 1 Fact Schema | 无来源事实、字段不完整 | Pydantic | 极低 | ✅ 生效 |
| Layer 2 Output Level | 证据不足时强结论 | 纯 Python 规则 | 低 | ✅ 生效 |
| Layer 3 Agent Packet-only | Agent 私自采集/编造事实 | prompt + tools=[] | 中 | ✅ 生效 |
| Layer 4 Guard hard rules | 未追溯事实、目标价、symbol mismatch | 纯 Python 规则为主 | 中 | ✅ 生效 |

---

## 10. 部署架构

```
                    Internet
                       │
                ┌──────▼──────┐
                │   Nginx      │  (frontend Docker)
                │   :80 → :5173│
                │   /api → :8000│
                └──────┬──────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    React SPA    FastAPI:8000   SQLite
    (静态文件)    (分析引擎)     (checkpoints/ + 业务数据)
                       │
          ┌────────────┼────────────┬────────────────┐
          ▼            ▼            ▼                ▼
      Data Providers  FAISS RAG   DeepSeek API    Gemini/Grok API
      yfinance        facts cache  主分析模型       可选模型路由
      SEC/HKEX
      (Polygon/Tiingo/Alpha Vantage 规划中)
```

## 11. 下一阶段目标架构：多数据源 + Fact Store

当前 v4.1 已经完成“证据前置”和“动态 RAG 事实缓存”，但事实来源仍主要依赖 yfinance。下一阶段应把数据层升级为 Provider + Fact Store + Vector Index 三层：

```
Polygon / Tiingo / Alpha Vantage / SEC / HKEX / yfinance
        │
        ▼
Provider Adapter
  ├── 字段标准化
  ├── source priority
  ├── license / TTL / as_of_date
  └── raw_payload_hash
        │
        ▼
Normalized Fact Store (SQLite / Postgres)
  ├── field-level TTL
  ├── symbol + field + period 唯一键
  ├── source confidence
  └── conflict detection
        │
        ├── Evidence Packet Builder
        │      └── 按字段覆盖 + TTL 决定是否补采
        │
        └── Vector Index (FAISS / future OpenSearch)
               └── 语义召回、上下文补充，不作为唯一真相源
```

### 11.1 Provider 优先级建议

| 数据类型 | 主源 | 备用源 | 说明 |
|----------|------|--------|------|
| 美股财报与增长率 | SEC EDGAR | Alpha Vantage / Polygon | 官方来源优先，用于 `revenue_growth_yoy`、`eps_growth_yoy` |
| 实时/延迟行情 | Polygon / Tiingo | yfinance / Alpha Vantage | 减少 yfinance 单点失败 |
| 基础估值 | Alpha Vantage / Polygon | yfinance | 补 `pe_ratio`、`market_cap`、`pb_ratio` |
| 港股公告与公司资料 | HKEX | yfinance | 港股 yfinance 覆盖不稳定 |
| 新闻 | Tiingo / Polygon | yfinance news | 新闻单源需标记未交叉验证 |

### 11.2 冷启动判定升级

当前冷启动仍主要由 RAG similarity 和 symbol metadata 判断。目标状态应改为：

1. 先查 Fact Store：目标 symbol 的 required fields 是否未过期。
2. 再查 RAG：补充上下文、研报摘要、历史分析。
3. 字段覆盖不足时按 provider priority 补采。
4. 多源冲突时进入 `packet.conflicts`，不用于强结论。

这样可以避免“FAISS top-k 召回其他股票 → 误判冷启动 → 重复下载”的问题。
