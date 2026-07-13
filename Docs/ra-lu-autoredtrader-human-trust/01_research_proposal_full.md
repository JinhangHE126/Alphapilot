# Research Proposal (Full Revised Version)

**Title:** When Agents Are Steered, Do Humans Over-Trust?  
**Subtitle:** Source Authority, Misinformation, and Reliance Calibration in Agentic Financial Human-AI Teaming

**Target:** RA collaboration with Dr. Zhuoran Lu (Purdue / Accenture Advanced AI)  
**Platform:** AlphaPilot — evidence-first multi-agent equity research system  
**Anchor paper:** [AutoRedTrader (arXiv:2605.09185)](https://arxiv.org/html/2605.09185v1)

**Version:** 1.0 · 2026-07-11  
**Pilot type:** Exploratory (N≈18); effect directions and UI trends, not confirmatory significance.

---

## 1. Executive Summary

AutoRedTrader demonstrates that subtle finance-specific misinformation can flip retrieval-based trading agent decisions (**ASR 26.67%**), and that time-series grounding only partially mitigates the risk (**ASR still 18.33%**). The paper does **not** measure the **human downstream cost**: whether analysts over-trust or over-adopt steered agent outputs.

Dr. Lu's prior work on **trust, reliance, and adversarial social influence** in AI-assisted decision making suggests humans are highly sensitive to perceived source credibility and presentation—but these insights have not been connected to **finance-specific agent red-teaming**.

This proposal bridges the two lines using **AlphaPilot** as a human-AI teaming testbed:

1. MisGen-style perturbations on **news** vs. **filing** evidence channels  
2. Exploratory human pilot crossing **UI condition** (No-Audit / Facts-Only / Full-Audit)  
3. Joint analysis of agent metrics (MER, RDR) and human metrics (trust, reliance, adoption)

---

## 2. Motivation & Gap

### 2.1 What AutoRedTrader establishes (agent side)

- Financial misinformation is often **subtle** (sentiment, framing, minor numeric edits), not outright fabrication.  
- Attacks unfold over **sequential decisions** (trajectory-level), not single outputs.  
- Closed-loop red-teaming: MisGen → inject retrieval pool → measure **MER** (exposure) and **ASR** (decision flip).  
- Time-series grounding reduces but does not eliminate vulnerability.

### 2.2 What remains open (human side)

| Gap | Relevance to Lu's research |
|-----|---------------------------|
| No human trust/reliance measurement after agent steering | AAAI 2023 Markovian trust/reliance model |
| No test of whether **source authority** (news vs. 10-K) moderates adoption | CHI adversarial social influence |
| No evaluation of **audit UI** as reliance calibration | CHI *From Text to Trust*; IUI Devil's Advocate |
| Single-agent FinMem trading; not multi-agent research workflow | Agentic Human-AI Teaming |

### 2.3 Explicit links to Lu et al.

| Prior work (representative) | Bridge to this proposal |
|-----------------------------|-------------------------|
| *Modeling Human Trust and Reliance in AI-assisted Decision Making: A Markovian Approach* (AAAI 2023, Oral) | Measure whether attacked agent outputs trigger **miscalibrated reliance** |
| *Strategic Adversarial Attacks in AI-assisted Decision Making to Reduce Human Trust and Reliance* (AAAI) | Test **false trust** under subtle (non-obvious) financial attacks |
| *LLM-driven Adversarial Social Influences in Online Information Spread* (CHI) | **Source type** (news vs. filing) as credibility moderator |
| *From Text to Trust* / Devil's Advocate (CHI / IUI) | **Citation-auditable UI** as reliance-calibration mechanism |

---

## 3. Research Questions & Hypotheses

### RQ1 (A): Trust & reliance under attack

| ID | Hypothesis |
|----|------------|
| H1a | Attacked reports receive **lower trust** than clean reports (trust drop). |
| H1b | Subtle attacks may cause **false trust** (trust ≥ clean baseline for same source). |
| H1c | **Full-Audit UI** (Guard + CitationsPanel) reduces **adoption error** vs. No-Audit. |

### RQ2 (C): Source authority moderation

| ID | Hypothesis |
|----|------------|
| H2a | **Filing-sourced** attacks yield **higher adoption intent** than news-sourced attacks (equal perturbation strength). |
| H2b | Participants with higher financial knowledge show lower adoption when attacked text **conflicts with structured_facts**. |
| H2c | Full-Audit UI **weakens** the filing authority premium (source effect attenuation). |

### RQ3: Agent → human transmission

| ID | Hypothesis |
|----|------------|
| H3 | Higher **RDR** (agent recommendation flip) predicts higher human alignment with attacked recommendation under **No-Audit**. |
| H3' | Full-Audit UI **flattens** the RDR → adoption relationship. |

---

## 4. Experimental Design

### 4.1 Design type

**3 × 2 × 2 mixed design**

| Factor | Type | Levels |
|--------|------|--------|
| UI Condition | Between-subjects | G1 No-Audit · G2 Facts-Only · G3 Full-Audit |
| Source Type | Within-subjects | News · Filing (10-K) |
| Attack | Within-subjects | Clean · Attacked |

Each participant reads **4 reports** (2×2 source × attack); order balanced via Latin square.

### 4.2 Participants

- **N = 18** (6 per UI group; minimum acceptable N = 16)  
- Finance / economics / CS / business undergraduates or graduate students  
- Session length: 25–35 minutes  
- Exploratory pilot: report **estimates + 95% CI**, not p-value-driven claims  

### 4.3 UI conditions

| Group | Content shown | Benchmark |
|-------|---------------|-----------|
| **G1 No-Audit** | Final report only (summary, recommendation, rationale) | Black-box AI research brief |
| **G2 Facts-Only** | G1 + structured fundamentals panel (`structured_facts`) | AutoRedTrader time-series / structured grounding |
| **G3 Full-Audit** | G2 + Guard checks + citation audit table (`[doc:N]`) + output level badge | AlphaPilot reliance-calibration UI |

Delivery: static HTML/PDF screenshots (no live system required for participants).

### 4.4 Stimuli (AAPL)

| ID | Source | Attack | Perturbation | Agent-side goal |
|----|--------|--------|--------------|-----------------|
| S1 | News | Clean | — | Baseline |
| S2 | News | Attacked | Sentiment shift / flipping | Sentiment offset; possible RDR |
| S3 | Filing (10-K) | Clean | — | Baseline |
| S4 | Filing | Attacked | Numerical / concept shift | MD&A or Risk Factors tampering |

**Pilot implementation (Week 1, July 2026):** Clean baseline shows asymmetric channels—filing RAG dominated citations; news entered via live `news_headline` facts. **S2** attacks target the headline fact path; **S4** targets `AAPL_annual_report_Risk_Factors_i03` (cited in clean run). FAISS news-index noise documented as limitation (see `06_technical_log_template.md` §0).

**Quality gates:**

- Attacked text reads naturally (no obvious AI artifacts)  
- ≥40% of S2/S4 preruns show RDR or clear narrative shift  
- G3 shows Guard warning on attacked stimuli (or document degraded output level)

---

## 5. Technical Pipeline (AlphaPilot)

> *Compressed for external memo; full steps in [05_timeline_8week.md](./05_timeline_8week.md) and [06_technical_log_template.md](./06_technical_log_template.md).*

### 5.1 Clean baseline

```bash
cd alphapilot
PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL
PYTHONPATH=. python ../scripts/run_analysis_direct.py AAPL
```

### 5.2 Attack generation (MisGen-style, simplified)

Use AutoRedTrader Appendix E prompt templates; pilot may hand-curate + LLM rewrite.

| Channel | Perturbation |
|---------|--------------|
| News | Sentiment shift or directional flipping |
| Filing | Numerical edits or concept substitution (revenue → operating income) |

**Injection (pilot):** patch target chunks in `evidence_packet.document_evidence`, then rerun analysis graph.  
**Follow-up:** inject into FAISS/FTS index for end-to-end retrieval realism.

### 5.3 Agent-side metrics

```
MER = |injected chunks in evidence used| / |total chunks used|

RDR = 1 if recommendation_attacked ≠ recommendation_clean else 0
```

Also log: `sentiment_delta`, `guard_status`, `allowed_output_level`.

---

## 6. Human Study Protocol

See [04_questionnaire.md](./04_questionnaire.md) for full instrument.

**Flow:** Consent → Pre-survey → Instruction → 4 trials (read + immediate questionnaire) → Post-survey → Debrief.

**Primary DVs:** Trust (Q1), Adoption intent (Q2), Reliance (Q3), Source credibility (Q4).

**Derived metrics:**

- Trust drop (clean − attacked, within source)  
- Adoption error (human decision aligns with attacked but not clean recommendation)  
- Detection rate (Q6 Yes)  
- False trust rate (attacked trust ≥ clean reference)

---

## 7. Analysis Plan

**Model (exploratory):**

```
DV ~ attack * source_type * ui_condition + financial_knowledge + (1|participant)
```

**Reporting:** effect directions, 95% CI, interaction plots (Attack × Source by UI panel).  
**Exploratory:** Spearman correlation RDR ↔ adoption under G1 only.

---

## 8. Ethics

- Low risk: no real trading, no sensitive financial data collected  
- Mild deception: misinformation not disclosed until debrief  
- Informed consent; voluntary withdrawal  
- IRB / exempt review to be pursued if study is scaled beyond classroom pilot  
- Attack texts marked SYNTHETIC; not for external distribution

---

## 9. Expected Contributions

1. **Empirical:** Preliminary evidence on whether **source authority** (news vs. SEC filings) moderates human adoption of attacked agent outputs.  
2. **Design:** Evidence on **citation-auditable + guard-gated interfaces** as **reliance-calibration mechanisms** in agentic financial systems.  
3. **Methodological:** A replicable bridge between **automated red-teaming** and **human-subject evaluation** in high-stakes financial AI, using AlphaPilot as an open testbed.

*To our knowledge, among the first studies connecting finance-specific agent red-teaming (AutoRedTrader-style) with human trust/reliance calibration via auditable agent interfaces.*

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| No RDR on attacked runs | Stronger numerical perturbation; swap chunk |
| Participants detect all attacks | Pretest n=3; reduce obviousness |
| Guard blocks all attacked content in G3 | Show warning + degraded report; measure calibration |
| Low recruitment | Minimum N=14; report limitations honestly |

---

## 11. Relation to AlphaPilot Components

| AlphaPilot feature | Role in study |
|--------------------|---------------|
| `structured_facts` | G2/G3 grounding; conflict check for H2b |
| `document_evidence` | Filing attack surface; MER |
| Guard agent | G3 reliance calibration |
| `[doc:N]` + `analysis_citations` | G3 citation audit |
| `allowed_output_level` | Evidence gating under insufficient evidence |
| Bull/Bear debate (optional extension) | Future work: does debate amplify or correct misinformation? |

---

## References

- Liu, Z., et al. (2026). AutoRedTrader. arXiv:2605.09185.  
- Lu, Z., Yin, M., et al. (2023). Modeling Human Trust and Reliance in AI-assisted Decision Making: A Markovian Approach. AAAI (Oral).  
- Lu, Z., et al. Strategic Adversarial Attacks in AI-assisted Decision Making to Reduce Human Trust and Reliance. AAAI.  
- Lu, Z., et al. LLM-driven Adversarial Social Influences in Online Information Spread. CHI.  
- AlphaPilot repository & [Architecture Overview](../Alphapilot_Architecture_Overview.md).
