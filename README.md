# AlphaPilot

多智能体股票投资分析平台 — 生产级 Web 应用

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + TypeScript |
| 后端 | FastAPI + Python 3.12 |
| 多智能体 | LangGraph StateGraph + Evidence Packet 前置节点 + 12 个专业 Agent |
| 防幻觉 | Hybrid RAG + Evidence Packet + Guard 硬规则 + 冷启动评测 |
| 数据源 | yfinance 主链路 + SEC/HKEX 辅助采集（规划接入 Polygon / Tiingo / Alpha Vantage） |
| 知识库 | FAISS 动态事实缓存（doc_id 去重、TTL 过滤、冷启动回写） |
| 数据库 | SQLite（分析记录、用户、会话、消息） |
| 认证 | JWT（注册/登录/刷新） |
| 实时流 | SSE (Server-Sent Events) |
| CI/CD | GitHub Actions + Docker + GHCR |
| 部署 | Docker Compose（前端 Nginx + 后端 FastAPI） |

## 快速开始

### 后端

```bash
cd alphapilot
cp .env.example .env   # 编辑填入 API Keys
pip install -r requirements.txt
python -m api.main
# API 运行在 http://localhost:8000
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
用户 → React 前端 → FastAPI → LangGraph StateGraph
                                │
                                ▼
                      Evidence Packet Builder
                      ├── FAISS RAG 检索（score + metadata）
                      ├── 冷启动判断（symbol / similarity / coverage）
                      ├── collect_all 数据采集（yfinance + SEC/HKEX 辅助）
                      ├── Evidence Packet 评分与输出等级
                      └── 高质量 facts 回写 FAISS（去重 + TTL）
                                │
                                ▼
                           Orchestrator
                      ├── insufficient/data_summary → Guard 拒答
                      ├── limited_analysis → Market/Fundamental/News → Strategy/Risk → Guard
                      └── full_analysis → 完整链路 + Guard
                                │
                                ▼
                         SQLite + Checkpointer
```

当前 Agent 的职责已经收敛：Market / Fundamental / News 等 Agent 不再直接调用 RAG 或外部数据工具，而是消费 `state.evidence_packet` 中的结构化事实。数据采集统一前置到 `evidence_packet_builder`，Guard 负责输出前的确定性校验。

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
| GET | /history | 分析历史列表 |
| GET | /dashboard/stats | 仪表盘统计 |
| GET | /health | 健康检查 |

## 项目结构

```
alphapilot/
├── api/main.py              # FastAPI 路由 & 中间件
├── agents/                   # 12 个专业 Agent
├── graph/                    # LangGraph 工作流 & 状态定义
├── services/                 # 分析服务（流式 & 同步）
├── db/                       # SQLite 模型 & 仓储层
├── tools/                    # 市场数据、新闻、RAG 工具
├── knowledge/                # Evidence Packet 入库治理（质量门槛、TTL、去重）
├── rag/                      # FAISS 动态事实缓存 + 兼容 Chroma 辅助模块
├── schemas/                  # Evidence Packet / Fact / Coverage / GuardResult
├── evaluation/               # 冷启动评测集、指标、结构化报告
├── monitoring/               # Evidence/Guard 运行指标
├── prompts/                  # Supervisor 提示词
├── Dockerfile & compose
frontend/
├── src/pages/                # Dashboard, Analyze, History, Settings, Login
├── src/services/             # API 客户端 & SSE 流式解析
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
- [Week 1-8 总结](alphapilot/Docs/Week_summary.md)

