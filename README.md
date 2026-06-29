# AlphaPilot

[![EN](https://img.shields.io/badge/lang-English-blue)](READEME_EN.md)

多智能体股票投资分析平台 — 生产级 Web 应用

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + TypeScript |
| 后端 | FastAPI + Python 3.12 |
| 多智能体 | LangGraph StateGraph + Evidence Packet 前置 + Bull vs Bear 辩论子图 + 14 个专业 Agent |
| 防幻觉 | Evidence Packet 字段溯源 + Guard 硬规则校验 + 冷启动评测 + 输出等级门控 |
| 数据源 | 多 Provider 并行采集（yfinance / SEC / Finnhub / EastMoney / AKShare 等）+ Fact Store 字段缓存 + 自动降级与字段级来源去重 |
| 知识库 | FAISS 双轨索引：结构化事实缓存 + **文档 chunk RAG**（hybrid 向量+FTS5、时效加权、HKEX/SEC/News 自动摄取、用户私有上传） |
| 数据库 | SQLite WAL 模式（分析记录、用户、会话、消息） |
| 认证 | JWT（注册 / 登录 / 刷新） |
| 国际化 | React i18n Context（English / 简体中文 / 粤语），自动检测浏览器语言 |
| 实时通信 | SSE (Server-Sent Events) 流式推送，Agent 产出渐进可视化 |
| CI/CD | GitHub Actions + Docker + GHCR |
| 部署 | Docker Compose（前端 Nginx + 后端 FastAPI） |

## 快速开始

### 后端

```bash
cd alphapilot
cp .env.example .env   # 编辑填入 API Keys（DeepSeek / Google 等）
pip install -r requirements.txt
# 文档自动抓取（可选）: 在 .env 中设置 DOC_FETCH_ENABLED=true
python -m api.main
# API 运行在 http://localhost:8000
```

可选：Phase 4 验收脚本（需后端已启动 + 登录账号）

```bash
python scripts/verify_p4.py --username <user> --password <pass>
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 开发服务器运行在 http://localhost:5173，自动代理 API 到 8000
```

### Docker 一键部署

```bash
docker compose -f alphapilot/docker-compose.yml up -d
# 后端: http://localhost:8000
# 前端（需单独构建或配合 deploy/docker-compose.prod.yml）
```

## 系统架构

```
用户 → React 前端 (i18n EN/ZH/Yue) → FastAPI → LangGraph StateGraph
                                      │
                                      ▼
                            Evidence Packet Builder
                            ├── FAISS 结构化事实检索 + Fact Store 字段缓存
                            ├── 文档感知 RAG（hybrid_retrieve: 向量 + FTS5 + 时效加权）
                            ├── 冷启动判断（symbol / similarity / coverage）
                            ├── 多 Provider 并行采集
                            ├── 双轨证据：structured facts + document_evidence
                            └── 高质量 facts 回写 FAISS（去重 + TTL）
                                      │
                                      ▼
                                 Orchestrator
                            ├── insufficient → Guard 拒答 → END
                            ├── limited → Market + Fundamental + News
                            │            → Strategy → Risk → Guard → END
                            └── full    → Market + Fundamental + News
                                         → Bull vs Bear 辩论子图（最多 2 轮）
                                         → Strategy → Risk
                                         → Portfolio → Backtest → Recommendation
                                         → Guard → END
                                      │
                                      ▼
                               SQLite + Checkpointer
```

**架构核心**：Agent 不直接调用工具或 RAG，只消费 `state.evidence_packet` 中的结构化事实与 **Document Evidence**（年报/公告/用户上传文档 chunk，带 `[doc:N]` 引用）。数据采集与文档检索统一前置到 Evidence Packet Builder；Guard 对输出执行确定性硬规则校验（含文档 grounding L1/L2/L3），不通过则带 corrections 重试（最多 2 次）。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/register | 用户注册 |
| POST | /auth/login | 用户登录 |
| POST | /auth/refresh | 刷新 Token |
| GET | /auth/me | 当前用户信息 |
| GET/PUT | /profile | 用户画像（风险偏好、投资周期） |
| GET/POST | /sessions | 会话管理 |
| POST | /analyze | 核心分析（同步） |
| POST | /analyze/stream | 核心分析（SSE 流式） |
| POST | /compare | 股票对比分析 |
| POST | /backtest | 历史回测 |
| POST | /alert | 实时监控告警 |
| POST | /optimize | 投资组合优化 |
| POST | /upload/document | 上传研究文档（PDF/Word/HTML/TXT，需登录，写入用户私有 RAG 空间） |
| GET | /history | 分析历史列表 |
| GET | /dashboard/stats | 仪表盘统计 |
| GET | /health | 健康检查 |

## 项目结构

```
alphapilot/
├── api/main.py              # FastAPI 路由 & 中间件
├── agents/                   # 14 个专业 Agent（含 Bull/Bear 辩论、Guard 硬规则）
├── graph/                    # LangGraph StateGraph 工作流 & 辩论子图
├── services/                 # 分析服务（SSE 流式 & 同步）
├── db/                       # SQLite 模型 & 仓储层
├── tools/                    # 多 Provider 数据采集（yfinance/HKEX/EastMoney/AKShare）
├── knowledge/                # 文档解析、分块、摄取、敏感扫描、定时抓取
│   ├── document_chunker.py   # 结构/语义分块
│   ├── pdf_parser.py         # PDF 解析（pymupdf / markitdown）
│   ├── document_ingest.py    # 统一入库（公开抓取 + 用户上传）
│   ├── sensitive_scanner.py  # 上传内容 PII 打码
│   ├── scheduler.py          # HKEX/SEC/News 定时抓取
│   └── fetchers/             # hkex / sec / news
├── rag/                      # FAISS 检索、FTS5、文档注册与保留策略
├── scripts/verify_p4.py      # Phase 4 一键验收（上传/隔离/打码）
├── schemas/                  # Evidence Packet / Fact / Coverage / GuardResult
├── evaluation/               # 冷启动评测集、指标、结构化报告
├── monitoring/               # Evidence/Guard 运行指标
├── prompts/                  # Supervisor 提示词
├── Dockerfile & compose
frontend/
├── src/pages/                # Dashboard, Analyze, History, Settings, Login
├── src/services/             # API 客户端 & SSE 流式解析
├── src/i18n/                 # 国际化（English / 简体中文 / 粤语）
├── Dockerfile & nginx.conf
deploy/                        # 生产部署脚本
.github/workflows/             # CI/CD 流水线
```

## 用户画像

每个用户可以配置：
- **风险偏好**: 低 / 中 / 高 — 影响推荐策略的激进程度
- **投资周期**: 短期 / 中期 / 长期 — 影响选股逻辑和时间框架

画像通过 `GET/PUT /profile` API 管理，分析时自动注入 LangGraph 工作流。

## CI/CD

- **CI** (pull_request / push): 后端 Ruff Lint + Pytest、前端 ESLint + TypeScript + Vitest + Build
- **CD** (push main): Quality gate → Docker 构建前后端镜像 → 推送 GHCR → SSH 远程部署

## 文档

- [架构设计](alphapilot/Docs/architecture.md)
- [文档感知 RAG 方案与实现状态](Docs/文档提取与RAG功能.md)
- [HK Fintech 竞争力优化方案](Docs/HK-Fintech-AI-竞争力优化方案.md)
- [HK Fintech 开发方案（排期与任务）](Docs/HK-Fintech-AI-开发方案.md)
- [Week 1-8 总结](alphapilot/Docs/Week_summary.md)

## Demo

基于 M1–M6 全链路（PDF 解析 → 语义分块 → Section Boost 检索 → Evidence Packet → 多 Agent 分析 → Guard 校验 → `[doc:N]` 审计追踪）的实际运行产出：

| 标的 | 市场 | 报告 | 说明 |
|------|------|------|------|
| **0700.HK** 腾讯控股 | 港股 | [查看报告](Docs/demo/0700.HK_analysis_sample.md) | Q1 2026 季报；Executive Synthesis + 多 `[doc:N]`；Guard 97 |
| **AAPL** Apple Inc. | 美股 | [查看报告](Docs/demo/AAPL_analysis_sample.md) | SEC 10-K；Risk Factors 引用 + Executive Synthesis |

> 面试材料：Demo 截图（分析页 / 报告 / Guard）待补入 `Docs/demo/screenshots/`。

**复现步骤**（在 `alphapilot` 目录执行，脚本会自动挂载 `PYTHONPATH`）：

```bash
cd alphapilot

# 1. 重建 / 验证 ingest
PYTHONPATH=. python ../scripts/reingest_0700.py
PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL

# 2. 全链路分析
PYTHONPATH=. python ../scripts/run_analysis_direct.py 0700.HK
# 或（需 API 已启动）: bash ../scripts/run_demo_analysis.sh 0700.HK

# 3. 离线评估（可选）
PYTHONPATH=. python ../scripts/eval_doc_recall.py
PYTHONPATH=. python ../evaluation/guard_grounding_report.py

# 4. P4 回归（需 API + 测试账号）
python scripts/verify_p4.py
```

