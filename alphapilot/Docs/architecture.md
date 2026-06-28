# AlphaPilot 系统架构 v4.3

> 当前版本以 **Evidence Packet 前置构造 + 双轨证据（结构化 Fact + Document Evidence）+ Bull vs Bear 多空辩论 + Guard 硬规则校验 + 文档感知 RAG** 为核心。  
> 旧版「Agent 各自调工具/RAG」的模式已收敛为「Builder 统一采集证据，Agent 只消费证据」。  
> v4.2 新增 Bull vs Bear 辩论子图；**v4.3 落地文档感知 RAG（Phase 1–4）**：公开文档自动摄取、用户私有上传、混合检索与 Guard 文档 grounding。

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        React 前端 (Vite + TS)                     │
│   Dashboard │ Analyze (SSE) │ History │ Settings │ Auth          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + SSE (JWT Bearer Token)
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI 后端 (Python 3.12)                    │
│  /auth/* │ /profile │ /sessions │ /analyze │ /upload/document │ /history │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              LangGraph StateGraph 多智能体工作流                    │
│                                                                  │
│  Evidence Packet Builder                                         │
│    → 结构化 RAG + Fact Store → 多 Provider 采集 → 评分/门控      │
│    → 文档 RAG (hybrid_retrieve) → document_evidence             │
│    → 动态入库 (FAISS facts cache, TTL, doc_id 去重)                │
│                                                                  │
│  Orchestrator                                                    │
│    → 按 allowed_output_level 分级路由                              │
│    → Market/Fundamental/News → Bull vs Bear 辩论 → Strategy/Risk  │
│    → full_analysis 时才进入 Portfolio/Backtest/Recommendation      │
│                                                                  │
│  持久化: SQLite (checkpointer + 业务表 + Fact Store)              │
│  知识库: FAISS（事实 + document_chunk）+ FTS5 全文索引              │
│  文档摄取: scheduler (HKEX/SEC/News) + 用户上传 API               │
│  用户画像: JSON 文件 (risk_preference, horizon)                   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 技术栈总览


| 层级     | 技术                                  | 说明                                                          |
| ------ | ----------------------------------- | ----------------------------------------------------------- |
| 前端框架   | React 18 + Vite + TypeScript        | SPA, Vite proxy 代理 API                                      |
| 样式     | 手写 CSS 暗色主题                         | 无第三方 UI 库依赖                                                 |
| 后端框架   | FastAPI + Uvicorn                   | 异步 REST + SSE 流式                                            |
| 多智能体   | LangGraph (StateGraph)              | Evidence Builder + Orchestrator 编排 14 Agent（含 Bull/Bear 辩论） |
| LLM 路由 | Gemini / DeepSeek / Grok            | 按 Agent 类型分模型                                               |
| 数据库    | SQLite (WAL 模式)                     | 业务表 + LangGraph checkpointer                                |
| 向量检索   | FAISS (all-MiniLM-L6-v2) + FTS5     | 结构化事实 + `document_chunk` 双轨；RRF 混合检索、时效加权、`user_session_id` 私有隔离 |
| 文档摄取   | pymupdf / markitdown + APScheduler  | HKEX/SEC/News 定时抓取；用户上传 PDF/Word/HTML/TXT；敏感信息打码 |
| 防幻觉    | Evidence Packet + Guard hard rules  | 输出等级门控、字段级来源追溯、冷启动拒答/降级                                     |
| 认证     | JWT (HS256)                         | register / login / refresh / me                             |
| 实时通信   | SSE (Server-Sent Events)            | agent_start / agent_output / agent_done                     |
| 数据采集   | 多 Provider + Fact Store            | yfinance / SEC / Finnhub / EastMoney / AKShare 等；字段级 TTL 与优先级去重 |
| CI/CD  | GitHub Actions + GHCR + Docker      | 前后端独立镜像 + SSH 部署                                            |


## 3. 14 智能体体系

### 3.1 Agent 角色矩阵


| Agent               | 节点名                                       | LLM               | 工具策略                                | 结构化输出                                              |
| ------------------- | ----------------------------------------- | ----------------- | ----------------------------------- | -------------------------------------------------- |
| **Market**          | `market_data_expert`                      | DeepSeek          | `tools=[]`，只读 Evidence Packet       | ❌ 自然语言                                             |
| **Fundamental**     | `fundamental_expert`                      | DeepSeek          | `tools=[]`，只读 Evidence Packet       | ❌ 自然语言                                             |
| **News**            | `news_sentiment_expert`                   | DeepSeek          | `tools=[]`，只读 Evidence Packet       | ❌ 自然语言                                             |
| **Bull Researcher** | `bull_researcher` (inside `debate_stage`) | DeepSeek          | `tools=[]`，构建做多论点                   | ❌ 自然语言                                             |
| **Bear Researcher** | `bear_researcher` (inside `debate_stage`) | DeepSeek          | `tools=[]`，构建做空论点                   | ❌ 自然语言                                             |
| **Strategy**        | `strategy_expert`                         | DeepSeek          | `tools=[]`，综合已验证事实、辩论论点与上游输出        | ❌ 自然语言                                             |
| **Risk**            | `risk_expert`                             | DeepSeek          | `tools=[]`，按证据等级输出风险                | JSON/自然语言混合                                        |
| **Portfolio**       | `portfolio_agent`                         | DeepSeek          | `tools=[]`，仅 full analysis 链路使用     | ❌ 自然语言                                             |
| **Backtesting**     | `backtesting_agent`                       | DeepSeek          | 内部价格下载，limited/eval 场景跳过            | ❌ 自然语言                                             |
| **Comparison**      | `comparison_agent`                        | DeepSeek          | `tools=[]`，专项对比入口                   | ❌ 自然语言                                             |
| **Alert**           | `alert_agent`                             | DeepSeek          | `tools=[]`，基于 Packet 指标生成告警         | ❌ 自然语言                                             |
| **Portfolio Opt**   | `portfolio_optimization_agent`            | DeepSeek          | `tools=[]`，专项组合优化入口                 | ❌ 自然语言                                             |
| **Recommendation**  | `recommendation_agent`                    | DeepSeek          | `tools=[]`，仅 full analysis 或个性化入口使用 | ❌ 自然语言                                             |
| **Guard**           | `guard_agent`                             | Python hard rules | 不调工具，基于 Evidence Packet 确定性校验       | ✅ dict (is_valid, confidence, issues, corrections) |


### 3.2 Agent 依赖拓扑

```
START
  ↓
Evidence Packet Builder
  ├── insufficient_evidence / data_summary_only → Guard → END
  ├── limited_analysis → Market + Fundamental + News → Strategy → Risk → Guard → END
  └── full_analysis → Market + Fundamental + News 
                   → Bull vs Bear 辩论子图 (bull_researcher ⇄ bear_researcher, 最多 2 轮)
                   → Strategy（综合辩论结论输出 Buy/Hold/Sell）→ Risk
                   → Portfolio → Backtest → Recommendation → Guard → END
```

#### Bull vs Bear 辩论子图

辩论仅在 `full_analysis` 证据等级时触发，以子图形式嵌入主工作流：

```
debate_stage (子图)
  ├── 入口检查: 证据不足 → END（跳过辩论）
  ├── bull_researcher → bear_researcher
  │       ↑                  │
  │       │  rounds < 2?     │
  │       │  YES → 回到 Bull │
  │       │  NO  → END       │
  │       └──────────────────┘
  ▼
strategy_expert (消费辩论历史 + 上游输出)
```

- 双方消费相同的 Evidence Packet 和上游 Market/Fundamental/News 输出
- 每轮 Bull 先发言、Bear 反驳，支持多轮往复
- Strategy Agent 权重分配：Market 25% + Fundamental 35% + News 15% + Debate 25%

### 3.3 模型路由架构

系统通过 `config/llm.py` 的 `AGENT_LLM_ROUTES` 为每个 Agent 分配独立的 LLM profile，支持：

- **多 Provider**: Gemini / DeepSeek / Grok (OpenAI 兼容)
- **多端口代理**: 按 Agent 类型拆分入口流量 (sing-box mixed inbound)
- **差异化参数**: 每个 Agent 独立 temperature / max_retries / timeout

## 4. GraphState 全局共享状态

所有 Agent 通过 `GraphState` (TypedDict) 共享数据，核心字段：


| 字段                        | 类型                | 职责                                   |
| ------------------------- | ----------------- | ------------------------------------ |
| `stock_symbol`            | str               | 当前分析股票代码                             |
| `messages`                | list[BaseMessage] | LangGraph 消息流 (add_messages reducer) |
| `evidence_packet`         | dict              | Evidence Builder 生成的双轨证据包（facts + document_evidence） |
| `user_session_id`         | str               | 登录用户 ID，用于检索用户私有 document chunk              |
| `cold_start`              | bool              | 是否触发冷启动采集                            |
| `ingestion_result`        | dict              | Evidence Packet 回写 FAISS 的统计结果       |
| `market_data`             | str               | Market Agent 输出                      |
| `fundamental_data`        | str               | Fundamental Agent 输出                 |
| `news_sentiment`          | str               | News Agent 输出                        |
| `bull_argument`           | str               | Bull Researcher 输出                   |
| `bear_argument`           | str               | Bear Researcher 输出                   |
| `debate_rounds`           | int               | 当前辩论轮数                               |
| `max_debate_rounds`       | int               | 最大辩论轮数（默认 2）                         |
| `strategy_recommendation` | str               | Strategy Agent 输出                    |
| `risk_assessment`         | str               | Risk Agent 输出                        |
| `executed_agents`         | list[str]         | 已执行 Agent 列表 (防重复)                   |
| `final_report`            | str               | 最终分析报告                               |
| `final_recommendation`    | str               | Buy/Hold/Sell                        |
| `user_profile`            | dict              | 用户画像 (risk_preference, horizon)      |
| `guard_check`             | dict              | Guard 校验结果                           |
| `guard_retry_count`       | int               | Guard 重试计数 (上限 2)                    |
| `confidence_score`        | int               | 最终置信度 0-100                          |
| `sources`                 | list[str]         | 引用来源列表                               |
| `memory`                  | dict              | 跨会话长期记忆                              |


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
          → market + fundamental + news
          → debate_stage (Bull vs Bear 辩论子图)
          → strategy → risk
          → portfolio → backtesting → recommendation → guard_agent → END
```

### 5.2 LangGraph 工作流图

```
START → evidence_packet_builder → orchestrator
           ├──→ market ──────────┐
           ├──→ fundamental ─────┤
           ├──→ news ────────────┤
           ├──→ debate_stage ────┤──→ orchestrator (循环)
           │    (Bull⇄Bear 子图) │
           ├──→ strategy ────────┤
           ├──→ risk ────────────┤
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


| 表                  | 用途     | 关键字段                                                               |
| ------------------ | ------ | ------------------------------------------------------------------ |
| `users`            | 用户认证   | id, username, password_hash, last_login                            |
| `sessions`         | 分析会话   | id (UUID), user_id, title, updated_at                              |
| `messages`         | 对话历史   | session_id, role, content, node_name                               |
| `analysis_history` | 分析记录   | user_id, stock_symbol, report, recommendation, status, final_score |
| `analysis_events`  | 流式事件日志 | analysis_id, seq_num, agent_name, event_type, content              |


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


| 路径             | 页面                 | 功能                    |
| -------------- | ------------------ | --------------------- |
| `/login`       | LoginPage          | 登录/注册双模式              |
| `/`            | DashboardPage      | 统计总览 + 最近分析           |
| `/analyze`     | AnalyzePage        | SSE 实时分析 + Agent 进度卡片 + **文档上传** |
| `/history`     | HistoryPage        | 分页列表 + 股票筛选 + 删除      |
| `/history/:id` | AnalysisDetailPage | 单次分析事件时间线             |
| `/settings`    | SettingsPage       | 用户画像配置                |


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
    ↓      结构化采集 + Fact Store + 文档 RAG → Fact + DocumentChunk
  Layer 1  字段级证据 Schema
    ↓      Fact (source/confidence_tier) + DocumentChunk ([doc:N] / user_submitted)
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

- `evidence_packet_builder` 先查 **Fact Store** 与 FAISS 结构化事实检索，过滤 symbol mismatch。
- 调用 `attach_document_evidence()` → `hybrid_retrieve()`（向量 Top-20 + FTS5 Top-20 → RRF k=60 → 时效加权 + **M2 section/doc_type boost**），写入 `packet.document_evidence`。
- 可选 `state.document_doc_type`（如 `annual_report`）传入后过滤 doc_type；默认空串不过滤。
- 登录用户传入 `user_session_id`：公开 chunk + 当前用户私有上传 chunk 混合返回；无 session 时屏蔽私有 chunk。
- RAG / Fact Store 不足时触发 `collect_all(symbol)` 冷启动采集。
- `collect_all()` 聚合多 Provider 市场/基本面/新闻与 SEC/HKEX 披露。
- 采集结果统一转换为 `Fact`；用户上传经 `sensitive_scanner` 打码后入库，`confidence_tier=user_submitted`。
- 高质量 Evidence Packet 通过 `upsert_packet()` 回写 FAISS（结构化 facts 去重 + TTL）。

**文件**：`graph/workflow.py`, `graph/document_evidence.py`, `tools/data_collector.py`, `schemas/evidence_packet.py`, `knowledge/document_ingest.py`, `knowledge/scheduler.py`, `rag/retriever.py`, `rag/chunk_fts.py`, `db/fact_store.py`

### 9.3 Layer 1：字段级证据 Schema

**原理**：用 Pydantic `EvidencePacket` / `Fact` 约束事实字段，而不是只约束 Agent 输出格式。

核心字段：


| 字段                | 说明                                           |
| ----------------- | -------------------------------------------- |
| `field`           | 标准化事实字段名，例如 `current_price`, `pe_ratio`      |
| `value`           | 原始值，不允许 LLM 自行补全                             |
| `source`          | 数据来源，例如 yfinance / SEC_EDGAR / HKEX / RAG    |
| `as_of_date`      | 数据对应日期                                       |
| `confidence`      | 字段级置信度                                       |
| `confidence_tier` | `machine` / `llm_extracted` / `llm_inferred` / **`user_submitted`**（用户上传文档） |

**DocumentChunk**（与 `Fact` 并行，见 `schemas/evidence_packet.py`）：

| 字段 | 说明 |
| ---- | ---- |
| `chunk_id` / `doc_id` | 向量库主键与 audit |
| `source` | `HKEX` / `SEC` / `user_uploaded` 等 |
| `doc_type` | `annual_report` / `earnings_call` / `research_report` / `news` |
| `confidence_tier` | 用户上传为 `user_submitted`，渲染时带 `[U]` 标记 |
| `user_session_id` | 私有空间隔离（仅上传者 + 登录分析可见） |

Agent 侧通过 `render_packet_for_agent()` 输出 `### Document Evidence`，每条 chunk 带 **`[doc:N]`** 序号；Guard L1 校验 `[doc:N]` 与列表下标对应关系。

**文件**：`schemas/evidence_packet.py`

### 9.4 Layer 2：Evidence Score 与输出等级门控

**原理**：在生成分析前，根据证据充分性决定系统最多允许输出什么级别的内容。

输出等级：


| 等级                      | 允许行为                     |
| ----------------------- | ------------------------ |
| `full_analysis`         | 可运行完整分析链路                |
| `limited_analysis`      | 允许谨慎分析，但禁止目标价/强推荐/未来源化数值 |
| `data_summary_only`     | 只能输出事实摘要和缺失字段            |
| `insufficient_evidence` | 直接拒答或请求补充数据              |


评分因素包括 source diversity、recency、completeness、field confidence；`coverage.document_evidence == "available"` 时 evidence_score **+5**。缺少关键字段或存在冲突时会降级。

### 9.5 Layer 3：Agent 只消费 Packet

**原理**：Market / Fundamental / News 等 Agent 不再自己调 RAG 或外部 API，避免不同 Agent 基于不同证据生成矛盾结论。

当前策略：

- 主要 Agent 均为 `tools=[]`。
- Agent prompt 要求只使用 Evidence Packet（结构化 facts + document_evidence）。
- **Market Agent 明确忽略 Document Evidence**，仅用 Verified Facts 做技术面分析。
- 缺少字段时输出 `NOT AVAILABLE` 或降级说明。
- `limited_analysis` 链路跳过 Portfolio / Backtest / Recommendation，避免过度建议。

### 9.6 Layer 4：Guard hard rules ★核心防线

**这是 AlphaPilot 防致幻体系的最后一道关**，位于工作流输出前。Guard 当前以确定性规则为主，不再依赖 RAG 工具交叉验证。

1. **证据级熔断**：无 Packet、symbol mismatch、`insufficient_evidence` → 硬拒
2. **输出级约束**：limited 级别禁止目标价、强推荐等
3. **Keyword grounding**（仅非 full）：输出提到某类指标 → Packet 里必须有对应 field
4. **数值 grounding**（部分）：提到指标且 Packet 有值 → 报告里的数要对得上
5. **文档 grounding**（Phase 2）：
   - **L1**：`[doc:N]` 必须在 `document_evidence[N-1]` 范围内
   - **L2**：疑似文档引用段落与 chunk embedding 相似度 ≥ 0.45（段内已有合法 `[doc:N]` 则跳过）
   - **L3**：文档引用句式粗检；`document_evidence` 为空时升为 issues
   - `FULL_ANALYSIS` 时 L1/L2 可降级为 warnings，不阻断

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


| 决策                           | 理由                                              |
| ---------------------------- | ----------------------------------------------- |
| 冷启动无 machine fact 直接拒答       | 数据不足不是重跑 LLM 能解决的问题                             |
| `limited_analysis` 禁止目标价和强推荐 | 防止证据不足时输出强投资结论                                  |
| Grounding 扫描关键字段和数值          | 报告提到 P/E、目标价、增长率等必须有 Packet fact                |
| soft failure 才允许 retry       | 仅 ungrounded claim / prohibited keyword 可通过重写修复 |
| 最大重试次数 = 2                   | 防止死循环                                           |


**文件**：`agents/guard_agent.py`, `graph/workflow.py`

### 9.7 防线效果矩阵


| 防线                        | 拦截的幻觉类型                   | LLM 依赖            | 误杀率 | 当前状态 |
| ------------------------- | ------------------------- | ----------------- | --- | ---- |
| Layer 0 Evidence Builder  | 冷启动纯 LLM 分析               | 非 LLM 规则 + 数据工具   | 低   | ✅ 生效 |
| Layer 1 Fact Schema       | 无来源事实、字段不完整               | Pydantic          | 极低  | ✅ 生效 |
| Layer 2 Output Level      | 证据不足时强结论                  | 纯 Python 规则       | 低   | ✅ 生效 |
| Layer 3 Agent Packet-only | Agent 私自采集/编造事实           | prompt + tools=[] | 中   | ✅ 生效 |
| Layer 4 Guard hard rules  | 未追溯事实、目标价、symbol mismatch、**未 grounding 文档引用** | 纯 Python 规则为主 + embedding | 中   | ✅ 生效 |


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
      Data Providers  FAISS RAG        LLM APIs
      multi-provider  facts + docs    DeepSeek / Gemini / Grok
      Fact Store      FTS5 index
      HKEX/SEC/News
      scheduler
```

---

## 12. 文档感知 RAG（v4.3，Phase 1–4）

详细方案与差距说明见项目根目录 [`Docs/文档提取与RAG功能.md`](../../Docs/文档提取与RAG功能.md)。

### 12.1 双轨证据

```
EvidencePacket
├── facts: list[Fact]                    # 结构化字段（价格、PE、增长率…）
└── document_evidence: list[DocumentChunk]  # 非结构化文档摘录（年报、公告、研报、用户上传）
```

### 12.2 数据流

```
公开来源                          用户上传
HKEX / SEC / News ──scheduler──►  document_ingest ──► FAISS (_type=document_chunk)
POST /upload/document ──────────►       │                    │
  (JWT, user_session_id)                ├── sensitive_scanner ([REDACTED])
                                        └── chunk_fts (FTS5)

分析请求 (user_session_id = user_id)
    → attach_document_evidence()
    → hybrid_retrieve(query, symbol, user_session_id, doc_type?)
    → 公开 chunk + 本人私有 chunk（混合）
    → render_packet_for_agent() → Agent / Guard
```

### 12.3 关键模块

| 模块 | 路径 | 职责 |
| ---- | ---- | ---- |
| 分块 | `knowledge/document_chunker.py` | 按 doc_type 结构/语义分块 |
| 解析 | `knowledge/pdf_parser.py` | PDF 文本（pymupdf / markitdown） |
| 入库 | `knowledge/document_ingest.py` | 统一 ingest；用户上传跳过全局 20 文档 prune |
| 抓取 | `knowledge/fetchers/*`, `scheduler.py` | 定时摄取；`DOC_FETCH_ENABLED=true` |
| 检索 | `rag/retriever.py`, `rag/chunk_fts.py` | `hybrid_retrieve`, section/doc_type boost, `doc_type` 后过滤 |
| 保留 | `rag/doc_registry.py` | 每 symbol 最多 20 份公开文档 |
| 私有 | `knowledge/sensitive_scanner.py` | 身份证/银行卡/电话/邮箱打码 |
| 接入 | `graph/document_evidence.py` | workflow 与测试共用 |
| API | `api/main.py` `/upload/document`, `api/upload.py` | 登录上传 |
| 验收 | `scripts/verify_p4.py` | 上传 + 隔离 + 打码一键测试 |

### 12.4 环境变量（文档抓取）

```bash
DOC_FETCH_ENABLED=true
DOC_FETCH_SYMBOLS=TSLA,AAPL,0700.HK
DOC_FETCH_INTERVAL_HOURS=6
```

### 12.5 尚未实现（见 RAG 文档 §10）

A/B 测试框架、document 级 `superseded`、BGE-large-zh 向量升级、完整 analysis 审计表、上传合规确认 UI 等。

---

## 13. 数据层演进：Fact Store 与多 Provider（进行中）

当前 v4.3 已具备 **Fact Store（SQLite）+ 多 Provider 适配 + 文档 RAG**。后续重点为冲突检测、评测指标与审计链路，而非从零搭建 Fact Store：

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

### 13.1 Provider 优先级（当前）


| 数据类型      | 主源                      | 备用源                      | 说明                                              |
| --------- | ----------------------- | ------------------------ | ----------------------------------------------- |
| 美股财报与增长率  | SEC EDGAR               | Alpha Vantage / Polygon  | 官方来源优先，用于 `revenue_growth_yoy`、`eps_growth_yoy` |
| 实时/延迟行情   | Polygon / Tiingo        | yfinance / Alpha Vantage | 减少 yfinance 单点失败                                |
| 基础估值      | Alpha Vantage / Polygon | yfinance                 | 补 `pe_ratio`、`market_cap`、`pb_ratio`            |
| 港股公告与公司资料 | HKEX                    | yfinance                 | 港股 yfinance 覆盖不稳定                               |
| 新闻        | Tiingo / Polygon        | yfinance news            | 新闻单源需标记未交叉验证                                    |


### 13.2 冷启动与证据构造（当前）

1. 先查 **Fact Store**：目标 symbol 的 required fields 是否未过期。
2. 并行 **文档 RAG**：`hybrid_retrieve` 补充定性上下文。
3. 字段覆盖不足时按 provider priority 补采。
4. 多源冲突时进入 `packet.conflicts`，不用于强结论。
5. RAG similarity 低且无 Fact Store 命中时仍可能标记 cold start。

这样可以减少重复下载，并在结构化事实与文档证据之间分工明确。