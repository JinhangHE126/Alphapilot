# AlphaPilot

[![中文](https://img.shields.io/badge/lang-简体中文-red)](README.md)

Multi-Agent Stock Investment Analysis Platform — Production-Grade Web Application

## Highlights

- **Anti-hallucination by design**: Evidence Packet pre-construction + deterministic Guard hard-rule validation — agents consume verified facts, not raw LLM guesswork.
- **Bull vs Bear debate subgraph**: Multi-round adversarial reasoning embedded in the LangGraph workflow, with Strategy synthesizing both sides into a final Buy/Hold/Sell recommendation.
- **Multi-market data pipeline**: Parallel collection from yfinance, HKEX, EastMoney, and AKShare, with automatic fallback and field-level source attribution across HK & US markets.
- **Cold-start evaluation suite**: Automated evals measuring output-level accuracy, hallucination rate, and guard compliance — runnable before every release.
- **Full-stack delivery**: Dockerized FastAPI + React + JWT + SQLite, with SSE streaming, i18n (EN/ZH/Yue), dashboard, and CI/CD.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite + TypeScript |
| Backend | FastAPI + Python 3.12 |
| Multi-Agent | LangGraph StateGraph + Evidence Packet Pre-construction + Bull vs Bear Debate Subgraph + 14 Specialized Agents |
| Anti-Hallucination | Evidence Packet field-level traceability + Guard hard-rule validation + Cold-start evaluation + Output-level gating |
| Data Sources | Multi-provider parallel collection (yfinance / HKEX / EastMoney / AKShare) with automatic fallback and field-level source deduplication, covering HK & US markets |
| Knowledge Base | FAISS dynamic fact cache (doc_id dedup, TTL filtering, cold-start write-back) |
| Database | SQLite WAL mode (analysis records, users, sessions, messages) |
| Authentication | JWT (register / login / refresh) |
| Internationalization | React i18n Context (English / Simplified Chinese / Cantonese) with automatic browser language detection |
| Real-time | SSE (Server-Sent Events) streaming with progressive agent visualization |
| CI/CD | GitHub Actions + Docker + GHCR |
| Deployment | Docker Compose (Nginx frontend + FastAPI backend) |

## Quick Start

### Backend

```bash
cd alphapilot
cp .env.example .env   # edit and fill in API Keys
pip install -r requirements.txt
python -m api.main
# API running at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Dev server at http://localhost:5173, automatically proxies API to 8000
```

### Docker (One-Command)

```bash
docker compose -f alphapilot/docker-compose.yml up -d
# Backend: http://localhost:8000
# Frontend: use deploy/docker-compose.prod.yml for production with Nginx
```

## Architecture

```text
User → React Frontend (i18n EN/ZH/Yue) → FastAPI → LangGraph StateGraph
                                           │
                                           ▼
                                 Evidence Packet Builder
                                 ├── FAISS RAG retrieval (score + metadata)
                                 ├── Cold-start detection (symbol / similarity / coverage)
                                 ├── Multi-provider parallel collection
                                 │   (yfinance / HKEX / EastMoney / AKShare)
                                 ├── Field-level source dedup & Evidence Packet scoring
                                 └── High-quality fact write-back to FAISS (dedup + TTL)
                                           │
                                           ▼
                                      Orchestrator
                                 ├── insufficient → Guard reject → END
                                 ├── limited → Market + Fundamental + News
                                 │           → Strategy → Risk → Guard → END
                                 └── full    → Market + Fundamental + News
                                              → Bull vs Bear Debate Subgraph (max 2 rounds)
                                              → Strategy → Risk
                                              → Portfolio → Backtest → Recommendation
                                              → Guard → END
                                           │
                                           ▼
                                    SQLite + Checkpointer
```

**Core principle**: agents never call tools or RAG directly — they consume structured facts from `state.evidence_packet`. Data collection is centralized in the Evidence Packet Builder before any agent runs. The Guard agent performs deterministic hard-rule validation (not LLM-based judgment) and triggers up to 2 correction retries on failure. The Bull vs Bear debate runs as an embedded subgraph, triggered only at the `full_analysis` output level.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | User registration |
| POST | `/auth/login` | User login |
| POST | `/auth/refresh` | Refresh JWT token |
| GET | `/auth/me` | Current user info |
| GET / PUT | `/profile` | User profile (risk preference, investment horizon) |
| GET / POST | `/sessions` | Session management |
| POST | `/analyze` | Core analysis (synchronous) |
| POST | `/analyze/stream` | Core analysis (SSE streaming) |
| POST | `/compare` | Stock comparison |
| POST | `/backtest` | Historical backtesting |
| POST | `/alert` | Real-time monitoring alerts |
| POST | `/optimize` | Portfolio optimization |
| GET | `/history` | Analysis history |
| GET | `/dashboard/stats` | Dashboard statistics |
| GET | `/health` | Health check |

## Project Structure

```text
alphapilot/
├── api/main.py              # FastAPI routes & middleware
├── agents/                   # 14 specialized agents (incl. Bull/Bear debate & Guard)
├── graph/                    # LangGraph StateGraph workflow & debate subgraph
├── services/                 # Analysis service (SSE streaming & synchronous)
├── db/                       # SQLite models & repository layer
├── tools/                    # Multi-provider data collection (yfinance/HKEX/EastMoney/AKShare)
├── knowledge/                # Evidence Packet ingestion governance (quality gate, TTL, dedup)
├── rag/                      # FAISS dynamic fact cache + Chroma auxiliary
├── schemas/                  # Evidence Packet / Fact / Coverage / GuardResult
├── evaluation/               # Cold-start eval set, metrics, structured reports
├── monitoring/               # Evidence/Guard runtime counters
├── prompts/                  # Supervisor prompts
├── Dockerfile & compose
frontend/
├── src/pages/                # Dashboard, Analyze, History, Settings, Login
├── src/services/             # API client & SSE stream parser
├── src/i18n/                 # i18n (English / 简体中文 / 粤语)
├── Dockerfile & nginx.conf
deploy/                        # Production deployment scripts
.github/workflows/             # CI/CD pipelines
```

## User Profile

Each user can configure:

- **Risk Preference**: Low / Medium / High — affects recommendation aggressiveness
- **Investment Horizon**: Short-term / Medium-term / Long-term — influences stock selection logic and time frame

Profile is managed via `GET/PUT /profile` and automatically injected into the LangGraph workflow.

## CI/CD

- **CI** (pull_request / push): Backend Ruff Lint + Pytest, Frontend ESLint + TypeScript + Vitest + Build
- **CD** (push to main): Quality gate → Docker build (frontend + backend) → Push to GHCR → SSH remote deploy

## Documents

- [Architecture Design](alphapilot/Docs/architecture.md) (Chinese)
- [中文 README](README.md)
