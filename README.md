# AlphaPilot

[![EN](https://img.shields.io/badge/lang-English-blue)](READEME_EN.md)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](alphapilot/requirements.txt)
[![React 18](https://img.shields.io/badge/react-18-61dafb)](frontend/package.json)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-412991)](alphapilot/graph/)

**多智能体、证据前置的股票研究平台** — Evidence Packet · 文档 RAG · Guard 硬规则 · `[doc:N]` 审计追踪

<p align="center">
  <img src="Docs/demo/screenshots/0628.gif" width="49%" alt="0700.HK 分析页：K 线、Agent 协作与核心结论" />
  <img src="Docs/demo/screenshots/0629.gif" width="49%" alt="0700.HK 全链路 SSE 分析演示" />
</p>

**完整演示（约 3 分钟）**

| 平台 | 链接 |
|------|------|
| Bilibili | [0700.HK 全链路演示（约 3 分钟）](https://www.bilibili.com/video/BV1b6KX67ES3/) |
| LinkedIn | [Full demo walkthrough (EN)](https://www.linkedin.com/feed/update/urn:li:activity:7477410007341244416/) |

> **免责声明**：本系统仅供研究与工程演示，输出不构成任何投资建议。使用前请阅读分析页底部免责声明；上传私有文档需勾选确认。

---

## 这是什么

AlphaPilot 将「数据采集 → 文档检索 → 多 Agent 推理 → 事实校验 → 报告落库」串成一条可审计链路：

1. **Evidence Packet Builder** 在 Orchestrator 之前统一拉取行情/基本面/新闻，并从年报、公告、用户上传 PDF 中检索 **Document Evidence**。
2. **十余个专业 Agent**（含 Bull vs Bear 辩论）只消费同一份 `evidence_packet`，避免各 Agent 各自调工具导致证据不一致。
3. **Guard Agent** 用确定性硬规则校验输出（字段 grounding、标的匹配、文档 `[doc:N]` grounding），不通过可带 corrections 重试。
4. **Audit Trail** 将报告中 `[doc:N]` 映射为向量库 `chunk_id`，写入 SQLite，History API 与前端可回溯。

与「单轮 Chat + 外挂 RAG」相比，本项目强调 **可控性、可追溯、可降级**（`insufficient` / `limited` / `full_analysis`），适合 Fintech 对 grounding 与 compliance narrative 的考察。

---

## 核心亮点

| 能力 | 说明 |
|------|------|
| **Evidence Packet 前置** | 采集、混合检索、证据评分、`allowed_output_level` 均在 Agent 编排前完成 |
| **双轨证据** | `structured_facts`（yfinance / EastMoney / AKShare 等）+ `document_evidence`（HKEX / SEC / 用户上传） |
| **文档感知 RAG** | FAISS + FTS5 混合检索、section / doc_type boost、时效加权、`user_session_id` 私有隔离 |
| **Bull vs Bear 辩论** | `full_analysis` 时触发子图，Strategy 按 Market 25% + Fundamental 35% + News 15% + Debate 25% 加权 |
| **Executive Synthesis** | Recommendation 输出跨 Agent 综合与矛盾分析，非逐 Agent 复述 |
| **Guard 防幻觉** | 字段级 / 文档 L1–L3 grounding、输出等级门控、冷启动拒答或 limited 路径 |
| **Audit Trail** | `analysis_citations` 表持久化 `chunk_ids`；分析页与历史详情展示 **文档引用审计** 表格 |

---

## Demo

基于 **M1–M6** 全链路实际运行产出（PDF 解析 → 分块 → Section Boost 检索 → Evidence Packet → 多 Agent → Guard → `[doc:N]` 审计）：

| 标的 | 市场 | 样本报告 | 典型指标（full_analysis） |
|------|------|----------|---------------------------|
| **0700.HK** 腾讯控股 | 港股 | [0700.HK_analysis_sample.md](Docs/demo/0700.HK_analysis_sample.md) | Evidence **97** · Guard ✅ · Strategy **Hold** (65) |
| **AAPL** Apple Inc. | 美股 | [AAPL_analysis_sample.md](Docs/demo/AAPL_analysis_sample.md) | SEC 10-K · Risk Factors / MD&A · Executive Synthesis |

**前端能力**：财务基本面快照、多空博弈、估值与结论摘要、风险仪表盘、Guard 检查项、**文档引用审计（Audit Trail）**。动图与完整录屏见文首。

<details>
<summary><strong>复现 Demo（展开）</strong></summary>

在仓库根目录执行，脚本会自动将 `alphapilot` 加入 `PYTHONPATH`：

```bash
cd alphapilot

# 1. 重建 / 验证文档 ingest
PYTHONPATH=. python ../scripts/reingest_0700.py
PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL

# 2. 全链路分析（无需 HTTP，输出 JSON + Markdown）
PYTHONPATH=. python ../scripts/run_analysis_direct.py 0700.HK

# 3. 或通过 Web UI（需 API + 前端已启动）
# bash ../scripts/run_demo_analysis.sh 0700.HK

# 4. 离线评估（可选）
PYTHONPATH=. python ../scripts/eval_doc_recall.py
PYTHONPATH=. python ../evaluation/guard_grounding_report.py

# 5. P4 回归：上传 / session 隔离 / 敏感打码（需 API + 测试账号）
python scripts/verify_p4.py --username <user> --password <pass>
# 或使用环境变量 VERIFY_P4_USERNAME / VERIFY_P4_PASSWORD
```

</details>

---

## 系统架构

```
用户 → React 前端 (EN / 简中 / 粤语) → FastAPI → LangGraph StateGraph
                                      │
                                      ▼
                            Evidence Packet Builder
                            ├── FAISS 结构化事实 + Fact Store 字段缓存
                            ├── hybrid_retrieve（向量 + FTS5 + 时效加权）
                            ├── 多 Provider 并行采集与字段级去重
                            ├── document_evidence（公开抓取 + 用户上传）
                            └── 证据评分 → allowed_output_level
                                      │
                                      ▼
                                 Orchestrator
                            ├── insufficient → Guard → END
                            ├── limited    → Market + Fundamental + News
                            │               → Strategy → Risk → Guard → END
                            └── full       → Market + Fundamental + News
                                            → Bull vs Bear 辩论（≤2 轮）
                                            → Strategy → Risk
                                            → Portfolio → Backtest → Recommendation
                                            → Guard → END
                                      │
                                      ▼
                    SQLite（分析记录 · events · analysis_citations · 会话）
```

**设计原则**：Agent **不直接**调用行情 API 或 RAG；只读 `state.evidence_packet`。Guard 对最终报告做确定性校验；流式分析通过 **SSE** 推送 `agent_start` / `agent_output` / `analysis_complete`（含 `citations`）。

更完整的架构说明见 [alphapilot/Docs/architecture.md](alphapilot/Docs/architecture.md)。

---

## 智能体一览

| Agent | 节点名 | 职责 | 工具策略 |
|-------|--------|------|----------|
| Market | `market_data_expert` | 技术面摘要 | 只读 Packet |
| Fundamental | `fundamental_expert` | 基本面分析 | 只读 Packet |
| News | `news_sentiment_expert` | 新闻与情绪 | 只读 Packet |
| Bull / Bear | `debate_stage` 子图 | 多空辩论 | 只读 Packet |
| Strategy | `strategy_expert` | 综合裁决 Buy/Hold/Sell | 只读 Packet |
| Risk | `risk_expert` | 风险评分与止损建议 | 只读 Packet |
| Portfolio | `portfolio_agent` | 仓位与分批策略 | 仅 full_analysis |
| Backtesting | `backtesting_agent` | 历史回测解读 | 仅 full_analysis |
| Recommendation | `recommendation_agent` | Executive Synthesis 终稿 | 仅 full / 个性化入口 |
| Guard | `guard_agent` | 硬规则校验（无 LLM） | 确定性 Python |

系统节点：`evidence_packet_builder`、`orchestrator`。

---

## 证据审计（Audit Trail）

每次分析完成后：

1. `services/citations.build_citations()` 从 `final_report` 正则提取 `[doc:N]`；
2. 映射 `evidence_packet.document_evidence[N-1].chunk_id`；
3. 写入 SQLite 表 `analysis_citations`（`chunk_ids`、`doc_markers`、`evidence_snapshot`）；
4. **分析页** Guard 区块下方展示 **文档引用审计**；**历史详情** `GET /history/{id}` 返回 `citations`。

```json
{
  "citations": {
    "chunk_ids": ["0700.HK_Q1_2026_..._Financial_Statements_p12_i01"],
    "doc_markers": ["doc:3"],
    "evidence_snapshot": [
      { "chunk_id": "...", "section": "Financial Statements", "source": "HKEX" }
    ]
  }
}
```

> Guard 区的「数据来源 (40)」列出的是 **结构化 fact 来源**（yfinance、Reuters 等），与 Audit Trail 的 **文档 chunk 引用** 不同。

---

## 快速开始

### 环境要求

- Python **3.12+**
- Node.js **18+**（前端）
- 至少一个 LLM API Key（推荐 **DeepSeek**；可选 Gemini）

### 1. 后端

```bash
cd alphapilot
pip install -r requirements.txt
# 推荐表格解析: pip install pdfplumber

# 在 alphapilot/.env 中配置（勿提交密钥），参考 deploy/.env.prod.example
# 必填: DEEPSEEK_API_KEY, JWT_SECRET（生产环境 ≥32 字节随机串）
python -m api.main
# → http://localhost:8000  （开发模式带 --reload）
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173  （Vite 代理 /api → 8000）
```

### 3. Docker（可选）

```bash
docker compose -f alphapilot/docker-compose.yml up -d
# 生产前后端见 deploy/docker-compose.prod.yml
```

### 环境变量（常用）

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | 主 LLM（多 Agent 路由） |
| `GOOGLE_API_KEY` | 可选 Gemini / embedding |
| `JWT_SECRET` | JWT 签名；**勿使用默认值** `change_this_in_prod` |
| `ENABLED_DATA_PROVIDERS` | 逗号分隔数据源，如 `yfinance,sec_edgar,akshare,eastmoney` |
| `DOC_FETCH_ENABLED` | `true` 启用 HKEX/SEC/News 定时抓取 |
| `DOC_FETCH_SYMBOLS` | 如 `TSLA,AAPL,0700.HK` |
| `HF_TOKEN` | 可选；减少 Guard 文档 grounding 拉取 HF 模型时的限速告警 |
| `VERIFY_P4_*` | P4 验收脚本账号与 API URL |

代理（国内环境）：见 `alphapilot/config/proxy.py` 中 `MARKET_PROXY` / `LLM_PROXY` 等。

---

## 质量评估与验收

| 脚本 | 用途 |
|------|------|
| `scripts/eval_doc_recall.py` | 文档检索 Recall@5 / @15（人工标注 query 集） |
| `evaluation/guard_grounding_report.py` | Guard grounding、`[doc:N]` 与 chunk 对齐 |
| `alphapilot/scripts/verify_p4.py` | HTTP 上传、session 隔离、敏感信息打码、工作流 |
| `alphapilot/test/test_analysis_citations.py` | Audit Trail 单元测试 |

说明与复测步骤见 [Docs/M6-评估脚本开发文档.md](Docs/M6-评估脚本开发文档.md)。

---

## API 概览

前缀：`/api`（前端 Vite 代理）。需登录的接口携带 `Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` · `/auth/login` · `/auth/refresh` | 认证 |
| GET/PUT | `/profile` | 用户画像（风险偏好、投资周期） |
| GET/POST | `/sessions` | 会话与消息 |
| POST | `/analyze` | 同步分析 |
| POST | `/analyze/stream` | **SSE 流式分析**（推荐） |
| POST | `/upload/document` | 上传 PDF 等；需 `consent_at` 确认时间戳 |
| GET | `/history` | 分析历史列表 |
| GET | `/history/{id}` | 详情含 `events` + **`citations`** |
| GET | `/dashboard/stats` | 仪表盘统计 |
| GET | `/health` | 健康检查 |

另有 `/compare`、`/backtest`、`/alert`、`/optimize` 等专项入口。

---

## 合规与产品

- **报告免责声明**：分析页报告底部展示；不构成投资建议。
- **上传确认**：上传私有文档前需勾选同意；API 记录 `consent_at` 审计字段。
- **SFC GenAI 叙事（工程侧）**：高风险 use case 通过 Evidence Packet 统一证据源、Guard 硬规则、Audit Trail 与人工可读报告降低幻觉与不可追溯风险（非法律意见）。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + TypeScript + 手写暗色 CSS |
| 后端 | FastAPI + Uvicorn + Python 3.12 |
| 编排 | LangGraph StateGraph + SQLite Checkpointer |
| LLM | DeepSeek / Gemini（按 Agent 分 profile，见 `config/llm.py`） |
| 向量库 | FAISS（`all-MiniLM-L6-v2`）+ FTS5 全文 |
| 数据库 | SQLite WAL（用户、会话、分析、events、citations） |
| 实时 | SSE（`agent_*` / `analysis_complete`） |
| i18n | English / 简体中文 / 粤语 |
| CI/CD | GitHub Actions + Docker + GHCR |

---

## 项目结构

```
Alphapilot/
├── alphapilot/                 # Python 后端
│   ├── api/main.py             # FastAPI 路由
│   ├── agents/                 # 14 Agent + Guard
│   ├── graph/                  # LangGraph 工作流与辩论子图
│   ├── services/               # analysis_service、citations
│   ├── knowledge/              # PDF 解析、ingest、scheduler
│   ├── rag/                    # hybrid_retrieve、FAISS
│   ├── db/                     # SQLite 模型与 repository
│   └── scripts/verify_p4.py    # P4 验收
├── frontend/                   # React SPA
├── scripts/                    # Demo / eval / reingest（仓库根目录）
├── evaluation/                 # guard_grounding_report 等
├── Docs/                       # 方案、验收、demo 样本
└── deploy/                     # 生产 compose 与 env 示例
```

---

## 用户画像

在 **设置** 页或通过 `GET/PUT /profile` 配置：

- **风险偏好**：低 / 中 / 高 — 影响 Recommendation 仓位与语气
- **投资周期**：短期 / 中期 / 长期 — 注入 LangGraph 初始状态

---

## CI/CD

- **CI**（PR / push）：后端 Ruff + Pytest；前端 ESLint + TypeScript + Vitest + Build
- **CD**（push main）：镜像构建 → GHCR → SSH 部署（见 `.github/workflows/`）

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [architecture.md](alphapilot/Docs/architecture.md) | 系统架构、Agent 编排、SSE、GraphState |
| [文档提取与RAG功能.md](Docs/文档提取与RAG功能.md) | 文档感知 RAG 方案与实现状态 |
| [HK-Fintech-AI-竞争力优化方案.md](Docs/HK-Fintech-AI-竞争力优化方案.md) | 投递叙事与优化优先级（面试可选阅读） |

里程碑、验收报告与评估脚本说明见 [`Docs/`](Docs/) 目录。

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 启动日志 `pdfplumber=False` | `pip install pdfplumber` 改善表格解析 |
| Guard 前大量 HuggingFace HEAD | 首次加载 embedding；可设 `HF_TOKEN` 或预下载模型 |
| `InsecureKeyLengthWarning` (JWT) | 将 `JWT_SECRET` 改为 ≥32 字节随机串 |
| 分析无 document chunks | 先 `reingest_0700.py` 或 `prepare_demo_ingest.py` |
| 终端无 Agent 正文 | 正文走 SSE；看浏览器分析页或 `GET /history/{id}` |
| dev 模式分析中断 | 避免分析过程中改代码触发 `--reload` |

---

## License

本项目用于个人作品集与工程演示。部署前请自行配置密钥、域名与合规策略。
