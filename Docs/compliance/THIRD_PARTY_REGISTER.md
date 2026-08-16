# Third-Party Register (Demo)

> AlphaPilot demonstrates engineering controls aligned with selected SFC regulatory expectations. This document is part of a technical demonstration and does not constitute legal advice, SFC certification, regulatory approval, or a determination of compliance.

## Purpose

- Record external providers used by AlphaPilot demo workflows.
- Track data exposure, operational reliance, and ownership follow-ups.

## Provider Inventory

| Provider / Service | Usage | Data Shared | Control Notes | Owner |
| --- | --- | --- | --- | --- |
| DeepSeek API endpoints | LLM inference across agent nodes | Prompt text, synthesized evidence context | Guard, claim validation, approval gate, fallback handling | TBD |
| Hugging Face model hub | Embedding model artifact retrieval/caching | Model metadata requests; optional download traffic | Local caching; consider authenticated token policy | TBD |
| Market/fundamental/news sources (`sec_edgar`, `akshare`, `tushare`, `finnhub`, `yfinance`, `sina_tencent`, `eastmoney`) | Data ingestion for evidence packet | Symbol queries and market/fundamental/news data fetches | Source prioritization, dedup, evidence packet scoring | TBD |

## Data Handling Notes

- No API keys, passwords, or raw auth tokens should be written to audit records.
- Sensitive prompt content is filtered/redacted by prompt-security controls before model calls.
- Final retention period and storage region requirements are pending business/legal confirmation.

## Open Compliance Follow-Ups

- Assign named owner per provider integration.
- Complete vendor due-diligence and contractual control mapping.
- Document data residency and retention commitments for production use.
