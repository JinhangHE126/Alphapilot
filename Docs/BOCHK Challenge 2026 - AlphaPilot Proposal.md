# BOCHK Innovation Pioneers Challenge 2026 — Proposal

**Project Name:** AlphaPilot — Evidence-Grounded Multi-Agent Wealth Advisory Copilot for Hong Kong Banks  
**Category:** Student Group  
**Technology Themes:** Generative AI + Big Data  
**Scene Themes:** Risk Management, Inclusive Finance  
**Submission Date:** June 2026

---

## 1. Proposal Overview / 方案概述

### Project Summary

AlphaPilot is an evidence-grounded GenAI wealth advisory copilot designed for Hong Kong banks. It assists Relationship Managers (RMs), investment consultants, and compliance teams in generating clear, traceable analysis of Hong Kong-listed equities and market developments, while supporting better-informed conversations with retail customers.

The system is built around an **Evidence Packet** mechanism. Before producing any output, AlphaPilot collects and structures information from multiple sources, assigns confidence metadata, and links conclusions back to original evidence. When available evidence is insufficient, the system downgrades the depth of analysis or surfaces limitations instead of generating unsupported statements.

The current prototype implements a LangGraph-based multi-agent workflow that separates market analysis, risk assessment, suitability reasoning, and compliance validation. It incorporates RAG retrieval, evidence scoring, output-level gating, deterministic guardrails, and real-time SSE streaming for progressive visualization. This design aims to reduce hallucination risk and improve transparency in AI-assisted advisory workflows.

The proposed pilot focuses on adapting the prototype into a controlled sandbox environment suitable for banking use cases, with emphasis on human-in-the-loop review, audit trails, and secure integration pathways.

The system is intended for education, research support, and RM-assisted advisory preparation, **not** for fully automated investment recommendation or order execution.

### Key Design Elements (Internally Validated Prototype)

- **Evidence Packet** with source, timestamp, and confidence metadata for field-level traceability.
- **Five-Layer Anti-Hallucination Defense-in-Depth** design combining pre-construction of evidence, schema enforcement, output gating, agent-level constraints, and hard-rule validation.
- **Prototype Evaluation:** In 30 controlled cold-start and edge-case test scenarios, AlphaPilot produced fully traceable outputs with no observed unsupported investment claims.
- **Real-time SSE Streaming** to support human review during analysis.
- **Multi-source data collection** with normalization and fallback logic (HKEX announcements, market data providers, news sources).

---

## 2. Target Market & Customer Groups / 目标市场及客户

**Primary Focus:** Hong Kong retail banking and wealth management sector.

**Key User Groups:**

- **Relationship Managers and Investment Consultants** who need faster preparation of client briefings with traceable supporting evidence.
- **Compliance and Risk Teams** requiring auditable AI-generated content and clear reasoning around suitability.
- **Retail Customers** (through RM-assisted or digital channels) who benefit from clearer explanations of Hong Kong market products, including those who invest in Hong Kong and mainland-related market products.

The solution supports more inclusive access to structured financial information for time-constrained professionals and customers who may not have institutional research resources.

---

## 3. Business Issues / Customers’ Pain Points Addressed

### 拟解决的业务问题或客户痛点

### Pain Point 1: Fragmented information slows down advisory work

RMs and customers often need to manually gather and cross-reference announcements, financials, news, and risk disclosures.

**Solution:** AlphaPilot consolidates relevant data into a structured Evidence Packet and generates referenced summaries with visible source attribution and real-time progress via SSE streaming.

### Pain Point 2: High time cost for RMs preparing client materials

Manual research for client meetings is repetitive and inconsistent across different RMs.

**Solution:** The multi-agent workflow (market overview, fundamental context, news sentiment, risk factors, suitability considerations) helps RMs obtain structured, evidence-linked briefings more efficiently, with human review checkpoints built in.

### Pain Point 3: Hallucination risk undermines trust in AI-assisted advisory

Uncontrolled generative outputs can introduce unsupported claims.

**Solution:** The Five-Layer defense design (Evidence Packet pre-construction, schema enforcement, output gating, agent constraints, and guardrail validation) aims to minimize unsupported claims. In controlled prototype testing, no unsupported investment claims were observed across 30 test scenarios.

### Pain Point 4: Difficulty scaling suitability and compliance considerations digitally

Advisory content must consider customer risk profiles and disclosure practices.

**Solution:** A dedicated suitability reasoning layer compares available customer profile indicators with equity/product characteristics and produces reasoned outputs with human-in-the-loop review points and full audit trail capability. The system is designed with Hong Kong’s suitability and disclosure practices in mind.

---

## 4. Expected Results / Revenue Stream Forecast

### 预期结果 / 收入来源预测

### Pilot Phase Objectives (controlled sandbox environment)

- Demonstrate reduction in RM briefing preparation time, with a **target of 30–50%** improvement in pilot use cases.
- Achieve high source traceability, with a **target of >95%** of major generated claims linked to verifiable evidence.
- Maintain a **target of zero critical unsupported investment claims** during pilot testing through evidence gating and guardrail validation.
- Establish an auditable workflow suitable for compliance review.
- Validate secure integration approach with bank internal systems in later stages.

### Potential Commercial Directions (Post-Pilot)

- B2B SaaS licensing to banks and wealth management firms.
- Per-seat subscription model for RMs and investment consultants.
- API-based usage for evidence retrieval and summarized analysis.
- Enterprise integration services for connection to internal knowledge bases and compliance systems.
- Optional premium modules for enhanced audit logging and suitability reporting.

The near-term priority is successful pilot validation with a banking partner.

### Next-Stage Enhancement Roadmap

Beyond the current prototype, AlphaPilot will be further enhanced in the following directions during the pilot phase:

- **Suitability Checker:** match customer risk profiles, investment horizon, and experience level against equity/product risk characteristics.
- **Evidence Trace Panel:** display source URL, timestamp, confidence level, and missing-data flags for major generated claims.
- **RM Briefing Export:** generate structured client briefing reports including market facts, recent announcements, risk factors, suitability notes, and disclaimers.
- **Compliance Mode:** provide a conservative output mode that restricts unsupported target prices, strong buy/sell language, and unverified claims.
- **Bank Knowledge Integration:** connect to approved internal product documents, compliance rules, FAQ, and CRM profile data through secure APIs in later phases.

---

## 5. Cost and Benefit Analysis / 成本效益分析

**Pilot-Phase Costs** include data integration, secure cloud infrastructure, compliance-oriented testing, UI components for RM workflows, and security/access control measures.

**Expected Benefits:**

- Improved efficiency for RMs in preparing evidence-based client briefings.
- Greater consistency in customer-facing explanations.
- Stronger traceability and audit capability for compliance teams.
- Lower risk profile for AI adoption compared to ungrounded generative tools, through human-in-the-loop design and evidence gating.
- Support for more inclusive delivery of structured financial information to retail customers via digital channels or RM assistance.

This approach prioritizes responsible, auditable AI support rather than full automation of advisory decisions.

---

## 6. Anticipated Challenges & Solutions

### 预期挑战与对应的解决方案


| Challenge                                        | Solution                                                                                                                                                                                                                          |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Data consistency across providers**            | Multi-source collection with source prioritization, confidence scoring, and explicit flagging of gaps or conflicts. Official sources such as HKEX announcements are given priority weighting.                                     |
| **Risk of unsupported AI-generated claims**      | Five-Layer defense design with Evidence Packet pre-construction and output-level gating. Internal prototype testing showed no observed unsupported claims across 30 controlled scenarios.                                         |
| **Regulatory and suitability requirements**      | The system is designed as advisory support with explicit suitability reasoning, risk context, human review checkpoints, and audit trail generation. It is designed with Hong Kong’s suitability and disclosure practices in mind. |
| **Integration with bank environments**           | Pilot begins in a sandbox with public data. Subsequent phases can connect through secure APIs to approved internal knowledge bases and customer profile systems.                                                                  |
| **Building trust with RMs and compliance teams** | Every output includes source references, confidence indicators, and reasoning summaries. The workflow is intentionally transparent and reviewable by human professionals.                                                         |


---

## 7. Why AlphaPilot for BOCHK?

AlphaPilot is designed to support BOCHK’s objectives in digital banking and responsible technology adoption:

- It offers RMs a structured, evidence-linked workflow that can reduce time spent on routine research while maintaining human oversight.
- It provides clearer, more consistent information support for retail customers, including those who need explanations of Hong Kong market products.
- The combination of Evidence Packet traceability, output gating, and suitability reasoning creates an auditable foundation aligned with expectations for AI use in advisory contexts.
- The human-in-the-loop architecture keeps licensed professionals in control while AI handles data synthesis and evidence organization.
- The modular design supports a phased approach: starting with a controlled sandbox pilot and progressing to secure integration with bank systems.

AlphaPilot does **not** aim to replace relationship managers or licensed advisors. It aims to give them a reliable, transparent co-pilot that makes complex market information more accessible and reviewable.

---

## Team

The team combines strengths in data science, AI engineering, and software development. We have built and internally validated a working multi-agent prototype with evidence-grounded guardrails. The architecture uses commonly used engineering components (LangGraph, FastAPI, React with SSE) and is structured for controlled deployment and future enterprise integration.