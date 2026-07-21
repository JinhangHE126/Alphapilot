# AlphaPilot — AWS EC2 远程部署详细架构

**服务器**：EC2 g4dn.2xlarge (ap-southeast-1 新加坡)  
**公网 IP**：13.229.242.132  
**访问地址**：http://13.229.242.132  
**最后更新**：2026-06-04  
**编制人**：何金航

---

## 一、整体架构拓扑
```text
                 互联网用户 (浏览器)
                        │
                        │ http://13.229.242.132:80
                        ▼
          ┌─────────────────────────┐
          │    AWS EC2 g4dn.2xlarge │
          │    ap-southeast-1       │
          │    IP: 13.229.242.132   │
          │                         │
          │  ┌───────────────────┐  │
          │  │  Docker: 前端容器   │  │
          │  │  (Nginx, port 80)  │  │
          │  │                    │  │
          │  │  /          → 静态页面│
          │  │  /api/*     → 反代到│  │
          │  │               :8001 │  │
          │  └────────┬──────────┘  │
          │           │             │
          │  ┌────────▼──────────┐  │
          │  │  Docker: API 容器  │  │
          │  │  (FastAPI, :8001) │  │
          │  │                   │  │
          │  │  LangGraph 编排器  │  │
          │  │  + 14 个 Agent    │  │
          │  │  + RAG 向量检索   │  │
          │  └────────┬──────────┘  │
          │           │             │
          │  ┌────────▼──────────┐  │
          │  │  宿主机进程:       │  │
          │  │  Qwen API (:8000) │  │
          │  │  Flask + bitsandbytes 8bit │
          │  │  GPU: ~8 GB 显存   │  │
          │  └───────────────────┘  │
          │                         │
          │  T4 GPU: 16 GB         │
          │  CPU: 8 vCPU           │
          │  RAM: 32 GB            │
          │  EBS: 120 GB gp3       │
          └─────────────────────────┘

```

## 二、三层服务详解

### 第 1 层：前端 Nginx（Docker 容器 `alphapilot-web`）

| 项目 | 详情 |
|------|------|
| **镜像** | `alphapilot-web:local` |
| **基础镜像** | `nginx:1.27-alpine` |
| **端口映射** | 宿主机 80 → 容器 80 |
| **前端框架** | React + TypeScript + Vite |
| **构建方式** | 多阶段构建：先 `node:20-alpine` 编译，产物拷入 nginx |
| **配置文件** | `/opt/Alphapilot/frontend/nginx.conf` |

**Nginx 路由规则**：

| 路径 | 行为 |
|------|------|
| `/` | 返回 React SPA 静态页面 (`/usr/share/nginx/html`) |
| `/api/` | 反向代理到 `http://host.docker.internal:8001/`（即宿主机 8001 端口的 FastAPI） |
| 其他 | `try_files` 回退到 `index.html`（SPA 客户端路由） |

**请求链路示例**：
```text
浏览器 → http://13.229.242.132/api/auth/login → Nginx (Docker, port 80)
→ proxy_pass http://host.docker.internal:8001/ → 宿主机 FastAPI (port 8001)
```


---

### 第 2 层：FastAPI 后端（Docker 容器 `alphapilot-api`）

| 项目 | 详情 |
|------|------|
| **镜像** | `alphapilot-api:local` |
| **基础镜像** | `python:3.12-slim-bookworm` |
| **网络模式** | `host`（直接使用宿主机网络，监听 8001） |
| **框架** | FastAPI + Uvicorn |
| **启动命令** | `uvicorn api.main:api --host 0.0.0.0 --port 8001` |
| **持久化** | SQLite（`checkpoints/app.db`）+ ChromaDB（`rag_data/`） |

**主要 API 端点**：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查，返回 `{"status":"healthy"}` |
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 用户登录，返回 JWT token |
| `/auth/me` | GET | 获取当前用户信息 |
| `/sessions` | POST | 创建分析会话 |
| `/analyze` | POST | 同步分析（调试用） |
| `/analyze/stream` | POST | **核心接口**：流式 SSE 分析 |
| `/compare` | POST | 多股票对比分析 |
| `/backtest` | POST | 策略回测 |
| `/optimize` | POST | 投资组合优化 |
| `/dashboard/stats` | GET | 仪表盘统计数据 |

> **认证方式**：JWT Token（Bearer），密钥存储在 `deploy/.env.prod` 的 `JWT_SECRET` 中。

**流式分析请求链路**：
```text
POST /analyze/stream
│
├─ 1. 创建/获取 Session
├─ 2. 调用 stream_analysis_events()
│      ├─ 启动 LangGraph workflow
│      │   (evidence_packet_builder → orchestrator → 各 Agent)
│      └─ 每个 Agent 输出通过 SSE (text/event-stream) 实时推送
└─ 3. 结果写入 SQLite (checkpoints/app.db)
```


**SSE 事件类型**：

| 事件 | 含义 | 数据内容 |
|------|------|---------|
| `analysis_start` | 分析开始 | session_id, thread_id, stock_symbol |
| `agent_start` | 某个 Agent 开始执行 | agent 名称, label, icon |
| `agent_output` | Agent 输出内容（流式） | agent 名称, content（增量文本） |
| `agent_done` | Agent 执行完毕 | agent 名称 |
| `analysis_complete` | 全部分析完成 | final_report, recommendation, guard_check |
| `error` | 出错 | detail 错误信息 |

---

### 第 3 层：Qwen LLM 推理服务（宿主机进程）

| 项目 | 详情 |
|------|------|
| **运行方式** | 宿主机 Python 3.10 进程，后台常驻 (`nohup`) |
| **脚本位置** | `/tmp/qwen_api_server.py` |
| **监听端口** | 8000 |
| **框架** | Flask（`threaded=True` 多线程） |
| **模型** | `Qwen/Qwen2.5-7B-Instruct` |
| **量化方式** | bitsandbytes 8bit |
| **显存占用** | ~8 GB / 16 GB（T4） |
| **API 格式** | OpenAI 兼容：`/v1/chat/completions`、`/v1/models`、`/health` |
| **支持特性** | 流式输出 (SSE)、非流式输出 |

**为什么没有用 vLLM？**
- vLLM 0.22.0 在 T4（compute capability 7.5）上有 torch.compile + CUDA Graph 兼容性 bug
- FP16 版本 14.29 GB → T4 显存不足 (14.75 GB 总量)
- AWQ 量化版 EngineCore 推理时崩溃
- bitsandbytes 8bit 是唯一验证通过的方案（你的 `test_qwen_inference.py` 已验证）
- 代价：推理速度慢 5-10%，面试 DEMO 完全够用

**LLM 调用链路**：
```text
Agent (FastAPI 容器, host network)
│
├─ llm.py: get_llm("strategy")
├─ 配置: LLM_BASE_URL= http://localhost:8000/v1 ├─ 模型: LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
│
└─ HTTP POST → http://localhost:8000/v1/chat/completions → Qwen API (宿主机, Flask threaded)
→ bitsandbytes 8bit 推理
→ 返回 JSON / SSE 流
```

---

## 三、Agent 体系（核心分析引擎）

系统通过 **LangGraph StateGraph** 编排 14 个 Agent：

```text
用户输入
│
▼
┌─────────────────────┐
│ evidence_packet_     │  ← 收集所有数据（RAG + yfinance + 新闻）
│ builder              │     构造防幻觉 Evidence Packet
│ (无 LLM 调用)        │
└─────────┬───────────┘
▼
┌─────────────────────┐
│ orchestrator          │  ← 决策路由器：根据数据完整度决定 Agent 执行顺序
│ (调 Qwen 做路由决策)   │     Evidence Score < 50 → 跳 Guard
└─────────┬───────────┘
▼
┌───────────────────────────────────────────┐
│        Stage 1: 数据采集（3 个 Agent 并行） │
│  market_data_expert   ← 行情技术分析         │
│  fundamental_expert   ← 基本面/财报          │
│  news_sentiment_expert ← 新闻舆情情绪        │
└───────────────┬───────────────────────────┘
▼
┌───────────────────────────────────────────┐
│        Stage 2: 策略分析                    │
│  strategy_expert      ← 综合前 3 者数据     │
└───────────────┬───────────────────────────┘
▼
┌───────────────────────────────────────────┐
│        Stage 3: 风险评估                    │
│  risk_expert          ← 波动率/回撤/VaR     │
└───────────────┬───────────────────────────┘
▼
┌───────────────────────────────────────────┐
│        Stage 4: 组合 + 回测                 │
│  portfolio_agent      ← 仓位管理           │
│  backtesting_agent    ← 历史策略回测        │
└───────────────┬───────────────────────────┘
▼
┌───────────────────────────────────────────┐
│        Stage 5: 输出与校验                  │
│  recommendation_agent ← 个性化 Buy/Hold/Sell │
│  guard_agent          ← 幻觉校验（最多重试 2 次）│
└───────────────────────────────────────────┘

```


### 14 个 Agent 详细说明

| # | Agent 名称 | 功能 | 数据来源 | 输出文件 |
|---|-----------|------|---------|---------|
| 1 | **market_data_expert** | 行情技术分析（价格、均线、MACD、RSI、成交量） | yfinance | `agents/market_agent.py` |
| 2 | **fundamental_expert** | 基本面分析（PE、PB、ROE、营收增长率） | yfinance + RAG | `agents/fundamental_agent.py` |
| 3 | **news_sentiment_expert** | 新闻舆情与市场情绪分析 | RAG + 新闻检索 | `agents/news_agent.py` |
| 4 | **strategy_expert** | 综合前三者，生成中线投资策略 | 前 3 个 Agent 的输出 | `agents/strategy_agent.py` |
| 5 | **risk_expert** | 风险评估（波动率、最大回撤、VaR、Beta） | 行情数据 | `agents/risk_agent.py` |
| 6 | **portfolio_agent** | 仓位管理与资产配置建议 | 策略 + 风险输出 | `agents/portfolio_agent.py` |
| 7 | **backtesting_agent** | 历史策略回测与绩效分析 | 历史行情 | `agents/backtesting_agent.py` |
| 8 | **recommendation_agent** | 最终投资建议（Buy/Hold/Sell + 理由） | 所有上游 Agent | `agents/recommendation_agent.py` |
| 9 | **guard_agent** | 幻觉检测：校验分析中的事实和数据 | Evidence Packet | `agents/guard_agent.py` |
| 10 | **comparison_agent** | 多股票横向对比（如 TSLA vs NVDA） | 多只股票数据 | `agents/comparison_agent.py` |
| 11 | **alert_agent** | 实时价格预警与监控 | 实时行情 | `agents/alert_agent.py` |
| 12 | **portfolio_optimization_agent** | 马科维茨均值-方差优化 | 多资产历史数据 | `agents/portfolio_optimization_agent.py` |
| 13 | **orchestrator** | LangGraph 路由器：决策 Agent 执行顺序 | 全局状态 | `graph/orchestrator.py` |
| 14 | **evidence_packet_builder** | 数据采集 + 防幻觉证据包 | RAG + yfinance | `graph/workflow.py` |

**LLM 配置切换**：

当前 `LLM_LOCAL_MODE=true`，所有 Agent 统一走 `local_qwen` profile：
```python
# alphapilot/config/llm.py
LLM_BASE_URL = "http://localhost:8000/v1"
LLM_MODEL    = "Qwen/Qwen2.5-7B-Instruct"
```

若设置 `LLM_LOCAL_MODE=false`，则各 Agent 走各自配置的外部 API（DeepSeek、Gemini、Grok），**不需要 GPU**。

---

## 四、数据流全景
```text
                     ┌────────────────────┐
                     │   前端 React SPA    │
                     │   http://IP:80      │
                     └────────┬───────────┘
                              │ POST /api/analyze/stream
                              ▼
                     ┌────────────────────┐
                     │   FastAPI 后端      │
                     │   :8001            │
                     └────────┬───────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  RAG     │  │ yfinance │  │ 新闻检索  │
        │ ChromaDB │  │ 行情数据  │  │          │
        │ + FAISS  │  └──────────┘  └──────────┘
        │ 本地嵌入  │
        └────┬─────┘
             ▼
        ┌──────────────────────┐
        │ Evidence Packet      │
        │ (防幻觉数据校验)      │
        │ Evidence Score 0-100 │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │   LangGraph 编排      │
        │   orchestrator 路由   │
        │   14 个 Agent 调度    │
        └──────────┬───────────┘
                   │ 每个 Agent 调 LLM
                   ▼
        ┌──────────────────────┐
        │   Qwen API :8000     │
        │   bitsandbytes 8bit  │
        │   T4 GPU 推理        │
        └──────────┬───────────┘
                   │ SSE 流式响应
                   ▼
        ┌──────────────────────┐
        │   前端实时渲染       │
        │   Agent 逐步输出     │
        │   agent_start/agent_ │
        │   output/agent_done  │
        └──────────────────────┘

```


### RAG 系统

| 组件 | 技术 | 详情 |
|------|------|------|
| 向量数据库 | ChromaDB | 本地持久化，路径 `/app/rag_data` |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` | 本地 CPU 运行，~80MB |
| 检索算法 | FAISS + 余弦相似度 | score 阈值 0.55（低于则标记冷启动） |
| 数据源 | HKEX 公告、SEC EDGAR、财经新闻 | 港股 + 美股覆盖 |

### Evidence Packet（防幻觉核心）

在 Agent 分析之前，先构造证据包：
- **RAG 检索**：从向量库匹配历史分析数据
- **冷启动判定**：RAG score < 0.55 → 触发外部数据采集（yfinance + news）
- **数据完整性评分**：0-100 分（< 50 → 跳过分析，直接走 Guard）
- **事实清单**：列出已验证的数据点，Agent 只能基于这些数据输出

---

## 五、Docker Compose 编排

文件：`/opt/Alphapilot/deploy/docker-compose.prod.yml`

```yaml
services:
  api:
    image: alphapilot-api:local
    container_name: alphapilot-api
    restart: unless-stopped
    network_mode: host          # 直接使用宿主机网络
    env_file: .env.prod
    environment:
      - LLM_LOCAL_MODE=true
      - LLM_BASE_URL=http://localhost:8000/v1
      - LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
    volumes:
      - ./runtime/rag_data:/app/rag_data
      - ./runtime/data:/app/data
      - ./runtime/checkpoints:/app/checkpoints
      - ./runtime/hf_cache:/app/hf_cache
      - ./runtime/backups:/app/backups
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]

  frontend:
    image: alphapilot-web:local
    container_name: alphapilot-web
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "80:80"
    depends_on:
      api:
        condition: service_healthy
```

> **注意**：Qwen API 不在 Docker Compose 中。原因 —— Flask + bitsandbytes 8bit 模型，多 worker 共享显存会冲突。当前 `threaded=True` 单进程多线程是 T4 上的唯一稳定方案。

---

## 六、EC2 文件系统布局
```text

/opt/Alphapilot/                        ← Git 仓库根目录
├── alphapilot/                         ← 后端 Python 代码
│   ├── api/main.py                     ← FastAPI 应用（所有 HTTP 端点）
│   ├── config/
│   │   ├── llm.py                      ← LLM 配置（Agent → profile 映射）
│   │   └── proxy.py                    ← 代理配置
│   ├── graph/
│   │   ├── workflow.py                 ← LangGraph 工作流定义
│   │   ├── state.py                    ← 全局状态 TypedDict（52 个字段）
│   │   ├── orchestrator.py             ← 路由决策逻辑
│   │   ├── checkpointer.py             ← LangGraph 状态持久化
│   │   ├── memory.py                   ← 长期记忆管理
│   │   └── user_profile.py             ← 用户画像加载
│   ├── agents/                         ← 14 个 Agent 实现
│   │   ├── market_agent.py
│   │   ├── fundamental_agent.py
│   │   ├── news_agent.py
│   │   ├── strategy_agent.py
│   │   ├── risk_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── backtesting_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── guard_agent.py
│   │   ├── comparison_agent.py
│   │   ├── alert_agent.py
│   │   └── portfolio_optimization_agent.py
│   ├── tools/                          ← 数据采集工具
│   │   ├── data_collector.py           ← 数据采集调度
│   │   ├── market_tools.py             ← 行情工具
│   │   ├── fundamental_tools.py        ← 基本面工具
│   │   ├── news_tools.py               ← 新闻工具
│   │   ├── rag_tools.py                ← RAG 工具
│   │   ├── hkex_tools.py               ← 港交所工具
│   │   ├── hk_stock_fallback.py        ← 港股备用数据源
│   │   └── sec_edgar_tools.py          ← SEC EDGAR 工具
│   ├── rag/                            ← RAG 检索增强模块
│   │   ├── vectorstore.py              ← ChromaDB + FAISS 向量库
│   │   ├── retriever.py                ← 检索器
│   │   └── embeddings_google.py        ← 嵌入函数（本地 sentence-transformers）
│   ├── schemas/                        ← 数据模型
│   │   └── evidence_packet.py          ← 防幻觉证据包结构
│   ├── services/
│   │   └── analysis_service.py         ← 分析服务（流式 + 同步）
│   ├── requirements.txt                ← Python 依赖
│   └── Dockerfile                      ← API 容器构建文件
│
├── frontend/                           ← 前端 React 代码
│   ├── src/
│   │   ├── services/
│   │   │   ├── sse.ts                  ← SSE 流式事件解析
│   │   │   └── api.ts                  ← API 调用 + JWT 认证
│   │   └── ...
│   ├── nginx.conf                      ← Nginx 反代 + 安全头配置
│   └── Dockerfile                      ← 前端容器构建（多阶段）
│
├── deploy/                             ← 部署配置
│   ├── docker-compose.prod.yml         ← Docker Compose 编排
│   ├── .env.prod                       ← 生产环境变量（不入 Git）
│   ├── .env.prod.example               ← 环境变量模板
│   └── runtime/                        ← 运行时持久化数据
│       ├── rag_data/                   ← ChromaDB 向量库（持久化）
│       ├── data/                       ← yfinance 数据缓存
│       ├── checkpoints/                ← LangGraph 状态 + SQLite
│       ├── hf_cache/                   ← HuggingFace 模型缓存
│       └── backups/                    ← 数据备份
│
└── Docs/                               ← 项目文档

```


### 宿主机额外文件

| 路径 | 说明 |
|------|------|
| `/tmp/qwen_api_server.py` | Qwen API 服务脚本（Flask + bitsandbytes） |
| `/tmp/qwen_api.log` | Qwen API 运行日志 |
| `~/.cache/huggingface/` | HuggingFace 模型缓存（Qwen2.5-7B + all-MiniLM-L6-v2） |

---

## 七、关键环境变量

文件：`deploy/.env.prod`

| 变量 | 值 | 作用 |
|------|-----|------|
| `LLM_LOCAL_MODE` | `true` | 启用本地 LLM → 所有 Agent 走 Qwen |
| `LLM_BASE_URL` | `http://localhost:8000/v1` | Qwen API 地址（OpenAI 兼容） |
| `LLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | 传给 ChatOpenAI 的 model 参数 |
| `JWT_SECRET` | (随机字符串) | JWT Token 签名密钥（建议 32 字节以上） |
| `ALLOWED_ORIGINS` | `*` | CORS 跨域白名单 |
| `HF_HOME` | `/app/hf_cache` | HuggingFace 模型缓存目录(容器内) |
| `DEEPSEEK_API_KEY` | (可选) | DeepSeek API Key（`LLM_LOCAL_MODE=false` 时使用） |
| `GOOGLE_API_KEY` | (可选) | Google Gemini API Key |
| `XAI_API_KEY` | (可选) | Grok API Key |

---

## 八、启动与运维

### 首次部署完整流程

```bash
# ===== Step 1: 启动 Qwen API（宿主机进程）=====
nohup python /tmp/qwen_api_server.py > /tmp/qwen_api.log 2>&1 &

# 等待 45 秒，确认模型加载完成
tail -f /tmp/qwen_api.log
# 看到 "Running on http://127.0.0.1:8000" 后 Ctrl+C

# 验证
curl -s http://localhost:8000/health
# 预期: {"status":"ok"}

# ===== Step 2: 构建 Docker 镜像 =====
cd /opt/Alphapilot
docker build -t alphapilot-api:local -f alphapilot/Dockerfile alphapilot
docker build -t alphapilot-web:local -f frontend/Dockerfile frontend

# ===== Step 3: 启动 Docker 服务 =====
cd deploy
BACKEND_IMAGE=alphapilot-api:local \
FRONTEND_IMAGE=alphapilot-web:local \
  docker compose -f docker-compose.prod.yml up -d

# ===== Step 4: 全链路验证 =====
curl http://localhost:8001/health      # API 健康检查
curl -s -o /dev/null -w "%{http_code}" http://localhost/  # 前端 200

# 浏览器访问 http://13.229.242.132
# → 注册账号 → 登录 → 输入股票代码分析
```

### EC2 关机后再开机（日常重启）

```bash
# 1. 启动 Qwen API
nohup python /tmp/qwen_api_server.py > /tmp/qwen_api.log 2>&1 &
# 等 ~45 秒模型加载

# 2. Docker 容器（设置了 restart: unless-stopped，通常自动启动）
docker start alphapilot-api alphapilot-web

# 或 Compose 启动：
cd /opt/Alphapilot/deploy
BACKEND_IMAGE=alphapilot-api:local \
FRONTEND_IMAGE=alphapilot-web:local \
  docker compose -f docker-compose.prod.yml up -d
```

### 代码更新后重新部署

```bash
cd /opt/Alphapilot
git pull

# 重新构建 + 重启
docker build -t alphapilot-api:local -f alphapilot/Dockerfile alphapilot
docker build -t alphapilot-web:local -f frontend/Dockerfile frontend

cd deploy
BACKEND_IMAGE=alphapilot-api:local \
FRONTEND_IMAGE=alphapilot-web:local \
  docker compose -f docker-compose.prod.yml up -d --force-recreate
```

---

## 九、常见问题排查

| 现象 | 原因 | 排查步骤 |
|------|------|---------|
| **浏览器无法访问** | 安全组未开放端口 80 | AWS Console → EC2 → 安全组 → 入站规则加 HTTP 80 |
| **502 Bad Gateway** | API 容器未启动 / nginx 反代不通 | `docker ps`, `curl localhost:8001/health` |
| **401 Unauthorized** | 未注册用户或 JWT 密钥不匹配 | 先点注册按钮注册账户 |
| **500 Internal Server Error** | Agent 代码异常 | `docker logs alphapilot-api \| tail -50` |
| **ERR_INCOMPLETE_CHUNKED_ENCODING** | Qwen API 单线程阻塞 | `ps aux \| grep qwen_api` 确认进程在跑，确认 `threaded=True` |
| **Qwen 返回 500** | 模型推理异常 | `tail -20 /tmp/qwen_api.log` |
| **分析卡住不动** | Qwen API 超时重试中 | 等待 LangChain 内置 5 次重试完成（约 2 分钟） |
| **"no price data found"** | yfinance 港股代码格式问题 | 港股用 `XXXX.HK`（如 `0700.HK`），首次下载可能需要 1-2 次重试 |

---

## 十、架构优势（面试可讲）

| 特性 | 实现方式 |
|------|---------|
| **全本地 LLM 推理** | bitsandbytes 8bit Qwen2.5-7B，不依赖任何外部 API |
| **Agent 编排** | LangGraph StateGraph，14 个 Agent 协同分析，支持动态路由 |
| **防幻觉机制** | Evidence Packet + Guard Agent + 来源追踪 + 最多 2 次重试修正 |
| **流式体验** | SSE (Server-Sent Events) 实时推送，Agent 逐步输出 |
| **港股 + 美股双覆盖** | yfinance + HKEX + SEC EDGAR + RAG 多数据源 |
| **容器化部署** | Docker Compose 一键编排，持久化挂在宿主机 |
| **单机全栈** | 一台 g4dn.2xlarge 跑全部：Qwen API + FastAPI + Nginx |
| **LLM 自主切换** | 一键切换 `LLM_LOCAL_MODE` → 本地 Qwen 或外部 DeepSeek/Gemini |

---

## 十一、当前限制（坦诚说明）

1. **Flask dev server**：非生产级 WSGI（如 gunicorn）。原因是 bitsandbytes 8bit 模型加载后多 worker 共享 GPU 显存存在冲突，`threaded=True` 单进程多线程是 T4 上的唯一稳定解。

2. **单 GPU 单点**：T4 故障会导致 LLM 链路中断。可设置 `LLM_LOCAL_MODE=false` 一键切到外部 API 作为备选。

3. **HTTP 明文**：生产应加 Let's Encrypt HTTPS 证书。

4. **流式偶发超时**：多 Agent 并发调 Qwen 时偶发重试，LangChain 内置 5 次重试自动兜底。

