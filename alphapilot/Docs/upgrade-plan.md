# AlphaPilot 企业级 Web 应用升级计划

> **版本**: v2.0 | **创建日期**: 2026-05-29 | **目标**: FastAPI + Docker → 完整企业级 Web 应用

---

## 一、项目背景与现状

### 1.1 当前架构

```
┌──────────────────────────────────────────────────────┐
│  Docker Compose (单容器)                              │
│  ┌────────────────────────────────────────────────┐  │
│  │  FastAPI (:8000)                               │  │
│  │  ├── /analyze    POST  同步，一次性返回          │  │
│  │  ├── /compare    POST  同步                     │  │
│  │  ├── /backtest   POST  同步                     │  │
│  │  ├── /alert      POST  同步                     │  │
│  │  ├── /optimize   POST  同步                     │  │
│  │  └── /health     GET                            │  │
│  │                                                │  │
│  │  依赖：                                         │  │
│  │  ├── LangGraph Multi-Agent (12个Agent)          │  │
│  │  ├── SQLite Checkpoint (checkpoints/*.db)       │  │
│  │  ├── JSON Memory (data/memory.json)             │  │
│  │  ├── FAISS RAG (rag_data/)                     │  │
│  │  └── HuggingFace Cache (hf_cache/)             │  │
│  └────────────────────────────────────────────────┘  │
│  UI: Gradio (ui/app.py) — 仅本地开发使用              │
│  CI/CD: 无                                           │
│  认证: 无                                             │
│  流式: 不支持                                         │
└──────────────────────────────────────────────────────┘
```

### 1.2 当前痛点

| 痛点 | 影响 |
|------|------|
| API 全部同步阻塞 | 用户需等待 15-60s 才能看到结果，体验差 |
| 无用户系统 | 无法区分用户、无法保存个人历史 |
| 无前端仪表盘 | Gradio 仅适合调试，不适合对外提供服务 |
| 手动部署 | 每次更新需 SSH 到服务器手动执行命令 |
| JSON 文件存储 | 不支持并发、无查询能力、无法扩展 |
| 无流式输出 | 分析过程中用户看不到任何进度 |

### 1.3 目标架构

```
┌──────────────────────────────────────────────────────────────┐
│  Docker Compose (双容器)                                      │
│                                                              │
│  ┌──────────────────────┐    ┌─────────────────────────────┐ │
│  │  Frontend (Nginx)    │    │  Backend (FastAPI)          │ │
│  │  :80                 │◄──►│  :8000                      │ │
│  │                      │    │                             │ │
│  │  React + Vite        │    │  ├── /auth/*      JWT 认证   │ │
│  │  ├── Dashboard       │    │  ├── /analyze     SSE 流式  │ │
│  │  ├── Analyze (实时)   │    │  ├── /compare     SSE 流式  │ │
│  │  ├── History         │    │  ├── /backtest    SSE 流式  │ │
│  │  ├── Login/Register  │    │  ├── /alert       SSE 流式  │ │
│  │  └── Recharts 图表    │    │  ├── /optimize    SSE 流式  │ │
│  │                      │    │  ├── /history/*   历史记录   │ │
│  └──────────────────────┘    │  └── /health                │ │
│                              │                             │ │
│                              │  持久化：                    │ │
│                              │  ├── SQLite (app.db)        │ │
│                              │  ├── Checkpoints (checkpoints/)│ │
│                              │  ├── RAG (rag_data/)        │ │
│                              │  └── HF Cache (hf_cache/)   │ │
│                              └─────────────────────────────┘ │
│                                                              │
│  CI/CD: GitHub Actions → ghcr.io → 服务器 pull + restart     │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、技术选型总览

| 层级 | 技术 | 理由 |
|------|------|------|
| 前端框架 | React 18 + TypeScript + Vite | 企业级标准，类型安全，HMR 极快 |
| UI 库 | Tailwind CSS + Shadcn/ui | 原子化 CSS + 高质量可定制组件 |
| 图表 | Recharts | React 原生，声明式 API |
| 路由 | React Router v6 | 标准 SPA 路由 |
| 状态管理 | React Context + useReducer | 轻量，无需额外依赖 |
| HTTP 客户端 | Fetch API + EventSource | 零依赖，原生支持 SSE 流式 |
| 后端 | FastAPI (已有) | 保持不变，增强功能 |
| 流式推送 | sse-starlette | FastAPI 原生 SSE 支持 |
| 认证 | JWT (python-jose + passlib) | 无状态，适合 API 服务 |
| 数据库 | SQLite (aiosqlite) | 零配置，Docker 卷持久化 |
| CI/CD | GitHub Actions | 与 GitHub 深度集成，免费 |

---

## 三、数据库设计

### 3.1 ER 图

```
┌──────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│    users     │       │  analysis_history    │       │  analysis_events     │
├──────────────┤       ├──────────────────────┤       ├──────────────────────┤
│ id (PK)      │──┐    │ id (PK)              │       │ id (PK)              │
│ username (UQ)│  │    │ user_id (FK→users)   │──┐    │ analysis_id          │
│ password_hash│  └───►│ stock_symbol         │  │    │  (FK→history)        │
│ display_name │       │ analysis_type        │  └───►│ seq_num              │
│ created_at   │       │ report (TEXT)        │       │ agent_name           │
│ last_login   │       │ recommendation       │       │ event_type           │
└──────────────┘       │ final_score          │       │   (start/output/done)│
                       │ status               │       │ content (TEXT)       │
                       │ started_at           │       │ created_at           │
                       │ completed_at         │       └──────────────────────┘
                       │ created_at           │
                       └──────────────────────┘
```

### 3.2 建表 SQL

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password_hash TEXT  NOT NULL,
    display_name TEXT   DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now')),
    last_login  TEXT
);

-- 分析历史记录表
CREATE TABLE IF NOT EXISTS analysis_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    stock_symbol    TEXT    NOT NULL,
    analysis_type   TEXT    NOT NULL DEFAULT 'analyze',
    report          TEXT,
    recommendation  TEXT,
    final_score     REAL    DEFAULT 0.0,
    status          TEXT    DEFAULT 'running',
    started_at      TEXT    DEFAULT (datetime('now')),
    completed_at    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_history_user ON analysis_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_time  ON analysis_history(created_at DESC);

-- Agent 事件表（用于回放分析过程）
CREATE TABLE IF NOT EXISTS analysis_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES analysis_history(id),
    seq_num     INTEGER NOT NULL,
    agent_name  TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    content     TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_analysis ON analysis_events(analysis_id);
```

---

## 四、API 设计

### 4.1 响应格式统一规范

所有接口统一返回：

```json
{
    "code": 0,
    "message": "success",
    "data": { }
}
```

| code | 含义 |
|------|------|
| 0    | 成功 |
| 401  | 未认证 / Token 过期 |
| 403  | 无权限 |
| 404  | 资源不存在 |
| 422  | 参数校验失败 |
| 500  | 服务器内部错误 |

### 4.2 认证模块 `/auth`

```
POST /auth/register
  Body: { "username": "alice", "password": "***", "display_name": "Alice" }
  200: { "code": 0, "data": { "user_id": 1, "access_token": "eyJ..." } }

POST /auth/login
  Body: { "username": "alice", "password": "***" }
  200: { "code": 0, "data": { "access_token": "eyJ...", "token_type": "bearer" } }

POST /auth/refresh
  Header: Authorization: Bearer {token}
  200: { "code": 0, "data": { "access_token": "eyJ..." } }

GET  /auth/me
  Header: Authorization: Bearer {token}
  200: { "code": 0, "data": { "id": 1, "username": "alice", "display_name": "Alice" } }
```

### 4.3 分析模块 `/api`（需认证）

```
GET  /api/analyze/stream?message=分析TSLA&stock_symbol=TSLA
  Header: Authorization: Bearer {token}
  200: text/event-stream (SSE)

POST /api/compare
  Body: { "stock_symbols": ["TSLA", "NVDA"] }
  200: { "code": 0, "data": { "analysis_id": 42 } }

GET  /api/compare/stream?stock_symbols=TSLA,NVDA
  200: text/event-stream (SSE)

POST /api/backtest  →  同上 POST + GET /stream 模式
POST /api/alert     →  同上
POST /api/optimize  →  同上
```

> 流式端点统一使用 GET + query params，因为浏览器 `EventSource` 仅支持 GET。

### 4.4 历史记录模块 `/api/history`（需认证）

```
GET    /api/history?page=1&page_size=20&stock_symbol=TSLA
  200: { "code": 0, "data": { "items": [...], "total": 100, "page": 1, "page_size": 20 } }

GET    /api/history/{analysis_id}
  200: { "code": 0, "data": { "id": 42, "report": "...", "events": [...] } }

DELETE /api/history/{analysis_id}
  200: { "code": 0, "message": "deleted" }
```

### 4.5 SSE 流式协议规范

每个分析请求启动后，客户端通过 SSE 接收事件流：

```
event: analysis_start
data: {"analysis_id": 42, "stock_symbol": "TSLA", "analysis_type": "analyze"}

event: agent_start
data: {"agent": "market_data_expert", "label": "Market", "icon": "📈"}

event: agent_output
data: {"agent": "market_data_expert", "content": "TSLA 当前价格 245.30 USD..."}

event: agent_done
data: {"agent": "market_data_expert"}

event: agent_start
data: {"agent": "fundamental_expert", "label": "Fundamental", "icon": "📊"}

... (更多 agent)

event: analysis_complete
data: {"analysis_id": 42, "final_score": 78.5, "recommendation": "Hold", "report": "完整报告..."}

event: error
data: {"message": "分析超时"}
```

---

## 五、前端设计

### 5.1 路由结构

| 路由 | 页面 | 说明 |
|------|------|------|
| `/login` | LoginPage | 登录页 |
| `/register` | RegisterPage | 注册页 |
| `/` | DashboardPage | 仪表盘（首页） |
| `/analyze` | AnalyzePage | 实时分析（核心交互页） |
| `/history` | HistoryPage | 历史记录列表 |
| `/history/:id` | AnalysisDetail | 单次分析详情 + 回放 |

### 5.2 组件树

```
App
├── AuthProvider (Context)
│   ├── LoginPage
│   │   └── LoginForm
│   └── RegisterPage
│       └── RegisterForm
│
├── ProtectedRoute
│   ├── AppLayout (侧边栏 + 顶栏)
│   │   ├── Sidebar
│   │   │   ├── NavItem: 仪表盘
│   │   │   ├── NavItem: 分析
│   │   │   ├── NavItem: 历史
│   │   │   └── UserMenu
│   │   │
│   │   ├── DashboardPage
│   │   │   ├── StatCards (4 卡片)
│   │   │   │   ├── 总分析次数
│   │   │   │   ├── 分析股票数
│   │   │   │   ├── 平均得分
│   │   │   │   └── 最近活跃
│   │   │   ├── RecentAnalyses (表格)
│   │   │   └── QuickAnalyze (快捷入口)
│   │   │
│   │   ├── AnalyzePage ★核心★
│   │   │   ├── StockSearch (搜索 + 选择)
│   │   │   ├── AgentPanelGrid (6宫格)
│   │   │   │   └── AgentCard × 6
│   │   │   │       └── 状态: idle | running | done
│   │   │   ├── ProgressBar (总进度条)
│   │   │   ├── SSEStreamViewer (流式报告区)
│   │   │   └── FinalReport (最终报告)
│   │   │
│   │   ├── HistoryPage
│   │   │   ├── FilterBar (搜索 + 筛选)
│   │   │   ├── HistoryTable (分页表格)
│   │   │   └── Pagination
│   │   │
│   │   └── AnalysisDetail
│   │       ├── ReportViewer
│       └── EventReplay (步骤回放)
```

### 5.3 核心交互流程 — AnalyzePage

```
用户输入股票代码 "TSLA"
│
├─ 1. 点击「开始分析」
│
├─ 2. POST /api/analyze → 创建分析任务 → 获得 analysis_id
│
├─ 3. GET /api/analyze/stream → 建立 SSE 连接
│     │
│     ├── analysis_start → 显示整体进度条 (0%)
│     ├── agent_start(market) → 📈 Market 卡片亮起 (脉冲动画)
│     ├── agent_output(market, "TSLA当前...") → 流式文本逐字显示
│     ├── agent_done(market) → 📈 Market 卡片变绿 ✓
│     ├── agent_start(fundamental) → 📊 Fundamental 卡片亮起
│     │   ...
│     ├── analysis_complete → 所有卡片变绿，展示最终报告 + 评分
│     └── error → 红色提示，允许重试
│
└─ 4. 分析结果自动存入 /api/history
```

### 5.4 UI 设计原则

- **暗色主题**：延续现有 Gradio UI 的深蓝渐变风格
- **实时反馈**：每个 Agent 执行时卡片有脉冲动画 + 进度指示
- **渐进展示**：逐块展示每个 Agent 的输出，而非一次性大段文本
- **移动端适配**：6宫格在小屏幕上变为 2 列 + 滚动
- **骨架屏**：历史记录加载时显示骨架占位

---

## 六、CI/CD 流水线

### 6.1 触发条件与阶段

```
触发:
  - push → main 分支
  - 手动触发 (workflow_dispatch)

流水线阶段:
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│  Lint   │───►│  Test    │───►│  Build    │───►│  Publish  │
│ Python  │    │ pytest   │    │  Docker   │    │  ghcr.io  │
└─────────┘    └──────────┘    └───────────┘    └──────────┘
```

### 6.2 GitHub Actions 工作流

```yaml
# .github/workflows/deploy.yml
name: Build & Publish

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Frontend
        run: |
          cd frontend
          npm ci
          npm run build

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build & Push Backend
        uses: docker/build-push-action@v5
        with:
          context: ./alphapilot
          push: true
          tags: ghcr.io/${{ github.repository }}/alphapilot-backend:latest

      - name: Build & Push Frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ghcr.io/${{ github.repository }}/alphapilot-frontend:latest
```

---

## 七、Docker 部署升级

### 7.1 新 docker-compose.yml

```yaml
services:
  backend:
    build:
      context: ./alphapilot
      pull: false
    container_name: alphapilot-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - ./alphapilot/.env
    volumes:
      - ./alphapilot/rag_data:/app/rag_data
      - ./alphapilot/data:/app/data
      - ./alphapilot/checkpoints:/app/checkpoints
      - ./alphapilot/hf_cache:/app/hf_cache
      - app_data:/app/app_data
    environment:
      - PYTHONUNBUFFERED=1
      - HF_HOME=/app/hf_cache
      - REASONER_PROXY=
      - NEWS_PROXY=
      - LLM_PROXY=
      - DATABASE_URL=sqlite+aiosqlite:////app/app_data/alphapilot.db
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - JWT_ALGORITHM=HS256
      - JWT_EXPIRE_MINUTES=1440
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    build:
      context: ./frontend
    container_name: alphapilot-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      backend:
        condition: service_healthy

volumes:
  app_data:
```

### 7.1.1 前端目录结构

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── nginx.conf
├── Dockerfile
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css
    │
    ├── api/
    │   ├── client.ts          # fetch wrapper (带 JWT 拦截)
    │   ├── auth.ts            # login / register / me
    │   ├── analyze.ts         # SSE EventSource 封装
    │   └── history.ts         # 历史记录 CRUD
    │
    ├── auth/
    │   ├── AuthContext.tsx     # JWT Token 管理
    │   └── ProtectedRoute.tsx  # 路由守卫
    │
    ├── hooks/
    │   ├── useSSE.ts          # 通用 SSE Hook
    │   └── useAnalysis.ts     # 分析流程编排 Hook
    │
    ├── components/
    │   ├── ui/                # shadcn/ui 基础组件
    │   │   ├── button.tsx
    │   │   ├── card.tsx
    │   │   ├── input.tsx
    │   │   └── ...
    │   ├── layout/
    │   │   ├── AppLayout.tsx
    │   │   ├── Sidebar.tsx
    │   │   └── TopBar.tsx
    │   ├── analyze/
    │   │   ├── AgentPanelGrid.tsx
    │   │   ├── AgentCard.tsx
    │   │   ├── SSEViewer.tsx
    │   │   └── ProgressBar.tsx
    │   └── dashboard/
    │       ├── StatCard.tsx
    │       └── RecentAnalyses.tsx
    │
    ├── pages/
    │   ├── LoginPage.tsx
    │   ├── RegisterPage.tsx
    │   ├── DashboardPage.tsx
    │   ├── AnalyzePage.tsx
    │   ├── HistoryPage.tsx
    │   └── AnalysisDetailPage.tsx
    │
    └── types/
        └── index.ts           # 共享类型定义
```

### 7.2 前端 Dockerfile

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 7.3 Nginx 配置（反向代理 + SSE）

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /auth {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 八、实施路线图

### Phase 1：后端基础设施

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 1.1 创建数据库 ORM 层 | `api/database.py` + `api/models.py` | P0 |
| 1.2 实现 JWT 认证模块 | `api/auth.py` + `/auth/*` 端点 | P0 |
| 1.3 改造 `/analyze` 为 SSE 流式 | `api/main.py` 新增流式端点 | P0 |
| 1.4 实现历史记录 CRUD | `/api/history/*` 端点 | P1 |
| 1.5 统一响应格式中间件 | 所有接口统一 `{code, message, data}` | P0 |
| 1.6 更新 `requirements.txt` | 添加认证、SSE、数据库依赖 | P0 |

### Phase 2：前端核心开发

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 2.1 项目脚手架 | Vite + React + TS + Tailwind + Shadcn | P0 |
| 2.2 路由 + 布局框架 | React Router + AppLayout | P0 |
| 2.3 登录/注册页 | JWT 认证流程完整打通 | P0 |
| 2.4 Dashboard 页 | 统计卡片 + 快捷入口 | P1 |
| 2.5 Analyze 页 ★核心★ | Agent 面板 + SSE 流式 + 报告 | P0 |
| 2.6 History 页 | 分页列表 + 详情查看 | P1 |
| 2.7 分析详情 + 回放页 | Event 时间线回放 | P2 |

### Phase 3：CI/CD + 部署

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 3.1 GitHub Actions 流水线 | `.github/workflows/deploy.yml` | P0 |
| 3.2 前端 Nginx + Dockerfile | `frontend/Dockerfile` + `nginx.conf` | P0 |
| 3.3 改造 docker-compose.yml | 双容器编排 + 健康检查 | P0 |
| 3.4 端到端联调测试 | 全部流程走通 | P0 |

---

## 九、关键技术决策

### 9.1 为什么 SSE 而非 WebSocket？

| 对比 | SSE | WebSocket |
|------|-----|-----------|
| 方向 | 单向（Server→Client） | 双向 |
| 复杂度 | 极低，原生 EventSource API | 需要库（如 Socket.io） |
| 断线重连 | 浏览器自动重连 | 需要手动实现 |
| 适用场景 | ✅ 分析结果推送（本场景） | 聊天室、协作编辑 |

### 9.2 为什么 SQLite 而非 PostgreSQL？

- **零运维**：无需额外容器、无需配置
- **足够用**：单用户/小团队场景，SQLite 写入性能 1000+ TPS
- **Docker 友好**：单文件数据库，卷挂载即可持久化
- **迁移成本低**：未来只需改连接串 + install psycopg2

### 9.3 为什么 JWT 而非 Session？

- **无状态**：不依赖服务端存储，水平扩展友好
- **Token 可携带信息**：user_id、expire_time 编码在 Token 中
- **前端友好**：存储在 localStorage，每次请求携带 Authorization Header

### 9.4 JWT Secret Key 安全管理

```
开发环境: .env 文件 (已加入 .gitignore)
生产环境: docker-compose.yml 中通过 ${JWT_SECRET_KEY} 引用宿主机环境变量
CI/CD:    通过 GitHub Secrets 注入
```

---

## 十、安全清单

| 项目 | 措施 |
|------|------|
| 密码存储 | bcrypt 哈希，绝不明文 |
| JWT Secret | 256-bit 随机密钥，通过环境变量注入 |
| Token 过期 | Access Token 24h，可配置 |
| CORS | 生产环境限制具体域名 |
| SQL 注入 | 使用参数化查询（aiosqlite） |
| XSS | React 默认转义 + CSP Header |
| 速率限制 | `/auth/login` 5次/分钟/IP（可选 Phase 2） |
| HTTPS | 生产环境配合 Nginx + Let's Encrypt |

---

## 十一、可观测性（可选 Phase 2）

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  FastAPI     │────►│  Prometheus  │────►│  Grafana  │
│  /metrics    │     │  (采集+存储)  │     │  (可视化)  │
└─────────────┘     └──────────────┘     └───────────┘
```

- `prometheus-fastapi-instrumentator` 一键暴露 `/metrics`
- Grafana 仪表盘模板：请求量、延迟 P95、错误率、Agent 耗时分布

---

## 十二、风险与预案

| 风险 | 概率 | 影响 | 预案 |
|------|------|------|------|
| SSE 长连接超时 | 中 | 高 | 前端 30s 无事件自动重连；后端心跳 15s |
| LangGraph 流式改造复杂 | 中 | 高 | `astream_events` API 原生支持事件流，降级方案为轮询 |
| EventSource 不支持 POST | 确知 | 低 | 已设计为 GET + query params，token 走 header 或 query |
| Docker Hub 拉取镜像失败 | 高 | 中 | GHCR 国内可访问；或用阿里云镜像仓库 |
| SQLite 并发写入瓶颈 | 低 | 低 | aiosqlite 单线程写入足够；未来可迁移 PostgreSQL |

---

## 十三、验收标准

- [ ] 用户可注册、登录、Token 刷新
- [ ] 登录后 `/analyze` 看到 6 个 Agent 实时执行动画
- [ ] 分析结果实时流式展示，不等到最后才显示
- [ ] 分析历史可查询、查看详情、回放
- [ ] Dashboard 展示用户统计
- [ ] `git push main` 后 GitHub Actions 自动构建并推送镜像
- [ ] `docker compose pull && docker compose up -d` 即可部署最新版本
- [ ] 前端通过 Nginx 反向代理访问后端（同域，无 CORS 问题）