# AlphaPilot System Architecture Overview

**AlphaPilot** is an evidence-first, multi-agent financial research platform designed for high-stakes analytical workflows. Unlike conventional chatbot-style LLM applications, AlphaPilot follows an **“evidence before reasoning”** design: all external data and document evidence are collected, normalized, and scored before any agent performs analysis.

> See also: [`Alphapilot_Architecture_En.jpg`](./Alphapilot_Architecture_En.jpg)

The system is organized into **four layers**:

---

## 1. Frontend & API Layer

Users interact with a **React (Vite + TypeScript)** web application supporting:

- Dashboard overview
- Real-time analysis (SSE)
- History review
- Settings
- Authentication

The frontend communicates with a **FastAPI** backend through **HTTP** and **SSE (Server-Sent Events)** for progressive visualization of agent execution. **JWT-based authentication** secures user sessions, profiles, document uploads, and analysis history.

| Endpoint | Purpose |
|----------|---------|
| `/auth/*` | Register / login / refresh |
| `/profile` | User risk preference & horizon |
| `/sessions` | Analysis session management |
| `/analyze/stream` | SSE streaming analysis |
| `/upload/document` | User document upload |
| `/history/{id}` | Report & citation audit |

---

## 2. LangGraph Multi-Agent Workflow

At the core of AlphaPilot is a **LangGraph StateGraph** workflow composed of three major stages.

### 2.1 Evidence Packet Builder

Before any agent runs, the system constructs a unified **Evidence Packet** containing:

- Structured market, fundamental, and news facts from multiple providers
- Retrieved document evidence from filings, announcements, and user-uploaded materials
- Evidence scoring and `allowed_output_level` gating

### 2.2 Orchestrator

The orchestrator routes the workflow based on evidence quality:

| Level | Route |
|-------|-------|
| **Insufficient evidence** | Conservative termination through Guard |
| **Limited analysis** | Market → Fundamental → News agents |
| **Full analysis** | Full multi-agent pipeline (see below) |

**Full-analysis path:**

```
Market + Fundamental + News
  → Bull vs Bear Debate (≤2 rounds)
  → Strategy → Risk
  → Portfolio → Backtest → Recommendation
  → Guard → END
```

### 2.3 Specialized Agents

More than ten domain-specific agents collaborate under orchestration. In full-analysis mode, the system runs market, fundamental, and news analysis, followed by a **Bull vs Bear debate subgraph** (up to two rounds), then strategy and risk synthesis.

A final **Recommendation Agent** produces an executive synthesis with document citations, and a deterministic **Guard Agent** validates the output.

> **Key principle:** All agents consume a shared `evidence_packet` and do **not** independently call external APIs or retrieval tools, improving consistency and traceability.

**LLM routing:** DeepSeek / Gemini / Grok — assigned per agent via `config/llm.py`.

---

## 3. Knowledge, Retrieval, and Data Collection

AlphaPilot uses a **dual-track knowledge architecture**:

| Track | Storage | Content |
|-------|---------|---------|
| Structured facts | SQLite Fact Store + FAISS | Market / fundamental / news fields |
| Document chunks | FAISS + FTS5 | Filings, announcements, user uploads |

**Retrieval:** Vector search + keyword search via **RRF hybrid fusion**, with recency weighting and session-level document isolation.

**Data providers:** yfinance · SEC · Finnhub · EastMoney · AKShare · Sina/Tencent — with field-level TTL and priority-based deduplication.

**Document ingestion:** Scheduled pipelines (HKEX / SEC / News) and user uploads (PDF / Word / HTML / TXT).

---

## 4. Persistence, Auditability, and Trust Controls

The platform emphasizes **trustworthy AI** through:

- **Output-level gating** based on evidence sufficiency
- **Deterministic Guard checks** — field grounding, document grounding, unsafe pattern detection
- **`[doc:N]` citation markers** mapped to chunk IDs in SQLite `analysis_citations`
- **CitationsPanel** on the frontend for audit trail review

Persisted in **SQLite (WAL mode):**

- Users, sessions, analysis history
- `analysis_citations` audit table
- Fact Store & LangGraph checkpointer
- User profiles (JSON: risk preference, investment horizon)

---

## Design Philosophy

AlphaPilot is built as a **workflow system**, not a chatbot.

| Principle | Description |
|-----------|-------------|
| Evidence-first reasoning | Collect and score evidence before agent execution |
| Controlled multi-agent collaboration | Specialized agents under explicit orchestration |
| Explicit degradation paths | Downgrade or reject when data is insufficient |
| Human-reviewable outputs | Citations, guard checks, and audit trails |

This makes the platform suitable for research on **grounded agent systems**, **decision-support AI**, and **reliable LLM workflows** in high-stakes domains such as finance.

---

*For engineering details, see [`alphapilot/Docs/architecture.md`](../alphapilot/Docs/architecture.md).*
