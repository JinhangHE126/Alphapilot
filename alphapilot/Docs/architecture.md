# AlphaPilot 系统架构 v3.0

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
│              LangGraph Supervisor 多智能体工作流                    │
│                                                                  │
│  Orchestrator → Market → Fundamental → News                      │
│              → Strategy → Risk → Portfolio → Backtest          │
│              → Recommendation → Guard (事实核查)                  │
│                                                                  │
│  持久化: SQLite (checkpointer + 业务表)                           │
│  知识库: FAISS + ChromaDB (RAG)                                  │
│  用户画像: JSON 文件 (risk_preference, horizon)                   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 技术栈总览

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 18 + Vite + TypeScript | SPA, Vite proxy 代理 API |
| 样式 | 手写 CSS 暗色主题 | 无第三方 UI 库依赖 |
| 后端框架 | FastAPI + Uvicorn | 异步 REST + SSE 流式 |
| 多智能体 | LangGraph (StateGraph) | Supervisor 编排 12 Agent |
| LLM 路由 | Gemini / DeepSeek / Grok | 按 Agent 类型分模型 |
| 数据库 | SQLite (WAL 模式) | 业务表 + LangGraph checkpointer |
| 向量检索 | FAISS (all-MiniLM-L6-v2) + ChromaDB | 双 RAG 引擎 |
| 认证 | JWT (HS256) | register / login / refresh / me |
| 实时通信 | SSE (Server-Sent Events) | agent_start / agent_output / agent_done |
| 市场数据 | yfinance | 实时行情 + 技术指标 |
| CI/CD | GitHub Actions + GHCR + Docker | 前后端独立镜像 + SSH 部署 |

## 3. 12 智能体体系

### 3.1 Agent 角色矩阵

| Agent | 节点名 | LLM | 工具 | 结构化输出 |
|-------|--------|-----|------|-----------|
| **Market** | `market_data_expert` | DeepSeek | yfinance (RSI, MACD, 波动率) + RAG | ❌ 自然语言 |
| **Fundamental** | `fundamental_expert` | DeepSeek | PDF 财报解析 + RAG | ✅ Pydantic (FundamentalData) |
| **News** | `news_sentiment_expert` | DeepSeek | yfinance 新闻 + 情感分析 + RAG | ✅ Pydantic (NewsSentimentData) |
| **Strategy** | `strategy_expert` | DeepSeek | 无（纯推理） | ✅ Pydantic (StrategyRecommendation) |
| **Risk** | `risk_expert` | DeepSeek | 无（纯推理） | ✅ Pydantic (RiskAssessment) |
| **Portfolio** | `portfolio_agent` | DeepSeek | 仓位计算 | ❌ 自然语言 |
| **Backtesting** | `backtesting_agent` | DeepSeek | 历史回测 | ❌ 自然语言 |
| **Comparison** | `comparison_agent` | DeepSeek | 多股对比 | ❌ 自然语言 |
| **Alert** | `alert_agent` | DeepSeek | 价格/指标监控 | ❌ 自然语言 |
| **Portfolio Opt** | `portfolio_optimization_agent` | DeepSeek | 组合优化 (Sharpe, 权重) | ❌ 自然语言 |
| **Recommendation** | `recommendation_agent` | DeepSeek | 无（综合推理 + 用户画像） | ❌ 自然语言 |
| **Guard** | `guard_agent` | DeepSeek | RAG 交叉验证 | ✅ JSON (is_valid, confidence, corrections) |

### 3.2 Agent 依赖拓扑

```
Layer 1 (并行):  Market ─┬─┐
                Fundamental ─┤──→ Strategy → Risk → Portfolio → Backtest
                News ───────┘                                    │
                                                                 ▼
                                                        Recommendation
                                                                 │
                                                                 ▼
                                                          Guard Agent
                                                       (事实核查 + 重试)
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

`orchestrator_node` 位于 `graph/workflow.py`，采用**确定性路由 + LLM 辅助决策**的混合策略：

```
输入检测 → 关键词匹配分流:
  ├── "警报/alert/监控"     → alert_agent
  ├── "优化/portfolio opt"   → portfolio_optimization_agent
  ├── "个性化/我的偏好"       → recommendation_agent
  └── "全面/完整/comprehensive" → 完整链:
        Stage 1 (并行): market + fundamental + news
        Stage 2: strategy
        Stage 3: risk
        Stage 4: portfolio
        Stage 5: backtesting
        Stage 6: recommendation
        Stage 7: guard → 校验 → END 或重试
```

### 5.2 LangGraph 工作流图

```
START → orchestrator
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
                  ├── is_valid │ retry>=2 → END
                  └── retry<2  → orchestrator (带 corrections)
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

## 9. 企业级防 LLM 致幻体系

AlphaPilot 采用**纵深防御**策略，从 5 个层级拦截 LLM 幻觉：

### 9.1 防线总览

```
  Layer 0  来源锚定
    ↓      每个 Claim 绑定 Tool 调用源
  Layer 1  结构化输出
    ↓      Pydantic Schema 强制约束
  Layer 2  数值边界检查
    ↓      纯 Python 程序化校验
  Layer 3  交叉验证
    ↓      Strategy 校验 Market/Fundamental/News 一致性
  Layer 4  Guard Agent 后验 + 自动重试
    ↓      RAG 交叉验证 → 不通过则重跑策略链
       最终输出（带置信度评分）
```

### 9.2 Layer 0：来源锚定 (Source Anchoring)

**原理**：不允许 Agent 凭空生成结论，强制每条声明必须来自 Tool 调用结果或 RAG 检索内容。

**实现**：
- Market / Fundamental / News Agent 的 system prompt 要求 **"Base everything strictly on tool data and RAG knowledge"**
- Agent 先调 `retrieve_knowledge` 获取背景知识，再调业务 tool
- Guard Agent 校验时对比 RAG 来源

**文件**：[market_agent.py](alphapilot/agents/market_agent.py), [fundamental_agent.py](alphapilot/agents/fundamental_agent.py), [news_agent.py](alphapilot/agents/news_agent.py)

### 9.3 Layer 1：结构化输出 (Pydantic Schema Enforcement)

**原理**：用 Pydantic BaseModel 定义 Agent 输出格式，确保关键字段类型正确、范围合法。

**已实现结构化输出的 Agent**：

```python
# Strategy Agent
class StrategyRecommendation(BaseModel):
    recommendation: Literal["Buy", "Hold", "Sell"]
    confidence_score: float  # 0-100
    reasoning: str
    weight_summary: str

# Risk Agent
class RiskAssessment(BaseModel):
    volatility_risk: str       # Low / Medium / High
    macro_risk: str
    stop_loss_suggestion: str
    position_suggestion: str
    overall_risk_score: int    # 0-100

# Fundamental Agent
class FundamentalData(BaseModel):
    symbol: str
    revenue_growth: float
    eps_growth: float
    gross_margin: float
    net_margin: float
    ...

# News Agent
class NewsSentimentData(BaseModel):
    overall_sentiment: str     # Positive / Neutral / Negative
    sentiment_score: float     # -1.0 to 1.0
    key_events: list[str]
    summary: str
```

**LLM 输出不符合 Schema → `ValidationError` → 异常被上层捕获**，不会悄悄通过。

**文件**：[strategy_agent.py](alphapilot/agents/strategy_agent.py), [risk_agent.py](alphapilot/agents/risk_agent.py), [fundamental_tools.py](alphapilot/tools/fundamental_tools.py), [news_tools.py](alphapilot/tools/news_tools.py)

### 9.4 Layer 2：数值边界检查 (Numerical Sanity Check) — 计划中

**原理**：非 LLM 的纯 Python 程序化校验，零幻觉风险。

**检查规则（计划实现）**：

| 检查项 | 规则 | 说明 |
|--------|------|------|
| 价格偏离 | `|claim - real_price| / real_price > 20%` | 用 yfinance 实时价对比 |
| RSI 范围 | `0 ≤ RSI ≤ 100` | 超出即幻觉 |
| P/E 符号 | `P/E > 0` (正常情况) | 负 P/E 需特别标注 |
| 增长率合理性 | `-100% < growth < 1000%` | 超出范围标记可疑 |
| 置信度范围 | `0 ≤ confidence ≤ 100` | 越界即异常 |

**此层在 GraphState 中已预留 `sources`、`confidence_score` 字段，Guard Agent 之前执行**。

### 9.5 Layer 3：交叉验证 (Cross-Agent Consensus)

**原理**：Strategy Agent 生成最终推荐前，必须校验依赖的三个上游 Agent 输出是否自洽。

**Strategy Agent prompt 中的硬性要求**：

```
Before finalizing, check:
1. Does fundamental data (P/E, revenue growth) support the technical signal?
2. Does news sentiment align with the technical trend?
3. If conflict (bullish tech + bearish fundamental), flag HIGH-RISK.
```

**文件**：[strategy_agent.py](alphapilot/agents/strategy_agent.py) prompt 部分

### 9.6 Layer 4：Guard Agent 后验 + 自动重试循环 ★核心防线

**这是 AlphaPilot 防致幻体系的核心**，位于工作流的最后一道关。

#### 工作流程

```
recommendation_agent 输出
         ↓
    guard_agent 介入
         │
    ┌────┴────┐
    │ RAG 交叉 │ ← retrieve_knowledge() 检索事实依据
    │ 验证     │
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
    │ is_valid = true     │ is_valid = false
    │ → END               │ → orchestrator
    │                     │   注入 corrections → 消息流
    │                     │   清除旧的 guard_check
    │                     │   重跑: strategy → risk → recommendation
    │                     │   guard_retry_count += 1
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
| 最大重试次数 = 2 | 防止死循环；2 次足够覆盖大部分修正场景 |
| 重试时清除 guard_check | 避免旧校验结果污染新一轮 |
| 重试时清除 executed_agents | 让 strategy/risk/recommendation 重新执行 |
| corrections 注入消息流 | Agent 能直接"看到"需要修正的问题 |
| retry ≥ 2 直接 END | 避免无限循环，宁可输出低置信度结果也不阻塞 |

#### JSON 提取容错

Guard Agent 输出解析 (`_extract_guard_json`) 具备三层容错：
1. 直接 JSON 解析
2. Markdown code block 提取
3. 正则匹配首尾 `{...}` 对象
4. 解析失败 → 格式化重试 prompt → **再次调用 Agent**
5. 仍失败 → 兜底结构 (is_valid=false, confidence=50)

**文件**：[guard_agent.py](alphapilot/agents/guard_agent.py), [workflow.py](alphapilot/graph/workflow.py)

### 9.7 防线效果矩阵

| 防线 | 拦截的幻觉类型 | LLM 依赖 | 误杀率 | 当前状态 |
|------|---------------|---------|--------|---------|
| Layer 0 来源锚定 | 凭空编造事实 | 依赖 prompt 约束 | 低 | ✅ 生效 |
| Layer 1 结构化输出 | 格式错误、类型错误 | 依赖 Pydantic 校验 | 极低 | ✅ 部分生效 (4/12 Agent) |
| Layer 2 数值边界 | 编造数字 (价格/PE/RSI) | **零依赖** | 极低 | 📋 计划中 |
| Layer 3 交叉验证 | 逻辑矛盾、信号冲突 | 依赖 prompt 约束 | 中 | ✅ 生效 (Strategy prompt) |
| Layer 4 Guard 重试 | 事实错误、数据造假 | 依赖 RAG + LLM | 中 | ✅ 刚接入 workflow |

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
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      yfinance    Gemini API   DeepSeek API
      (市场数据)   (LLM)        (LLM)
```
