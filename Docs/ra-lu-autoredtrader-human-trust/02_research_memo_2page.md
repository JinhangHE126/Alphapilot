# Research Memo (2 Pages — Draft for Dr. Zhuoran Lu)

**When Agents Are Steered, Do Humans Over-Trust?**  
Source Authority, Misinformation, and Reliance Calibration in Agentic Financial Human-AI Teaming

**From:** [Your Name]  
**Date:** July 2026  
**Status:** Technical pilot in progress (Week 1: clean baseline + attack drafts; N≈18 human study planned)

---

## 1. Motivation

Recent work on **AutoRedTrader** (Liu et al., arXiv:2605.09185) shows that subtle, finance-specific misinformation can substantially affect LLM-based trading agents: the framework achieves a **26.67% attack success rate (ASR)**—the fraction of decisions flipped relative to a clean-information baseline—and a **69.00% misinformation exposure rate (MER)** in retrieval. Supplying agents with **time-series-informed grounding** reduces ASR to **18.33%**, but a meaningful fraction of decisions remain vulnerable.

What this agent-side benchmark does **not** yet address is the **human downstream cost**. When an agent's research output is steered by misinformation, do human analysts detect the manipulation? Does their **trust** and **reliance** on the system change appropriately—or do they **over-adopt** flawed recommendations?

Your prior research is directly relevant. The Markovian trust/reliance model (Lu & Yin, AAAI 2023, Oral) formalizes how humans dynamically calibrate dependence on AI advice. Work on **strategic adversarial attacks on trust** (Lu et al., AAAI) and **adversarial social influences** in information spread (Lu et al., CHI) demonstrates that presentation and source cues can systematically shift human judgment—yet these insights have not been empirically linked to **finance-specific agent red-teaming**.

I propose to bridge these two research lines.

---

## 2. Research Questions

**RQ1 (Trust & reliance):** How do human trust, reliance, and adoption intent change when agent reports are generated under MisGen-style attacks vs. clean baselines?

**RQ2 (Source authority):** Does misinformation **source**—**news headlines** vs. **SEC filing excerpts**—moderate adoption, even when semantic perturbation strength is held constant?

**RQ3 (UI calibration):** Can **citation-auditable, guard-gated interfaces** act as **reliance-calibration mechanisms**, reducing erroneous adoption under attack?

**Hypotheses (exploratory):** (H1) Attacked reports lower trust on average, but subtle attacks may produce **false trust** in a subset of trials. (H2) Filing-sourced attacks increase adoption vs. news-sourced attacks. (H3) Full-audit UI attenuates both effects.

---

## 3. Method

### 3.1 Testbed: AlphaPilot

I developed **AlphaPilot**, an evidence-first, multi-agent equity research platform. Unlike single-loop trading agents, AlphaPilot enforces an **Evidence Packet** (structured market facts + hybrid-retrieved documents) **before** any agent reasoning, then runs specialized agents under LangGraph orchestration, and applies a deterministic **Guard** with **`[doc:N]` citation audit trails** persisted to SQLite.

This architecture provides:

- A realistic **retrieval-based attack surface** (FAISS + FTS5 over SEC/HKEX filings and news)  
- **Source-stratified evidence** (`structured_facts` vs. `document_evidence`) for RQ2  
- **Three UI conditions** naturally mapped to reliance-calibration levels  

### 3.2 Stimuli & attack

**Symbol:** AAPL (existing SEC 10-K ingest pipeline).  
**Four stimuli per participant (within-subjects):** Clean/Attacked × News/Filing.

Attacks follow AutoRedTrader's MisGen taxonomy (sentiment / numerical / concept perturbations), injected into the evidence packet or retrieval pool. Agent-side **MER** and **RDR** (report-level decision divergence vs. clean run) are logged for each stimulus.

**Pilot implementation note (AAPL, July 2026):** The clean baseline shows **asymmetric evidence channels**: hybrid RAG retrieved high-quality SEC Risk Factors (dominating document citations), while news entered primarily via live headline facts rather than the vector index. Accordingly, **S2 (news)** attacks target the `news_headline` evidence path; **S4 (filing)** attacks target a cited 10-K chunk (`Risk_Factors_i03`). This channel-aware placement follows a realistic threat model—perturbing evidence the pipeline actually consumes—rather than indiscriminate index poisoning. News-index ingest noise is reported as a **limitation**, not a design feature.

### 3.3 Human pilot design

| Factor | Levels |
|--------|--------|
| UI (between-subjects, n≈6/group) | **G1** No-Audit report · **G2** + structured facts · **G3** + Guard + citation audit |
| Source × Attack (within-subjects) | News/Filing × Clean/Attacked |

**N ≈ 18** graduate/upper-level students; session ≈30 min.  
**DVs:** Trust, adoption intent, reliance (7-point Likert); anomaly detection; personal Buy/Hold/Sell inclination.

**Analysis:** Mixed models with attack × source × UI; exploratory emphasis on **effect directions and CIs**, not confirmatory significance.

### 3.4 Limitations (exploratory pilot)

- Single symbol (AAPL); N≈18; effect directions and CIs, not confirmatory significance claims.
- Clean news stimuli (S1) are thinner than filing stimuli (S3) in the baseline report; **H2a compares attacked news vs. attacked filing**, not assumed symmetric clean baselines.
- Vector-indexed news exhibited third-party scrape noise; attacks were routed to the headline fact channel used in the debate pipeline.

### 3.5 Ethics

Low-risk classroom/online pilot; mild deception with full debrief; no real investment behavior solicited. IRB review if scaled.

---

## 4. Expected Contributions

1. **Empirical:** Preliminary evidence on whether **source authority** moderates human adoption of **attacked agent outputs** in financial research workflows.  
2. **Design:** Evaluation of **citation-auditable interfaces** as **reliance-calibration tools** in agentic human-AI teaming.  
3. **Methodological:** A reproducible pipeline linking **automated red-teaming metrics** (MER/RDR) to **human trust/reliance outcomes**—extending AutoRedTrader toward human-centered robustness evaluation.

*To our knowledge, this is among the first studies connecting finance-specific agent red-teaming with human trust/reliance calibration via auditable agent interfaces.*

---

## 5. Timeline & Ask

| Week | Milestone |
|------|-----------|
| 1–2 | Generate clean/attacked AAPL stimuli; log MER/RDR |
| 3 | Questionnaire + cognitive walkthrough (n=3) |
| 4–6 | Human pilot (N≈18) |
| 7–8 | Analysis, 1-page preliminary findings, discussion |

I would welcome the opportunity to discuss whether this direction could support your ongoing work on **agentic human-AI teaming** and **trust/reliance** in high-stakes decision support. I can share AlphaPilot demo artifacts and a technical pilot log immediately, with human pilot results to follow on the timeline above.

**Demo:** [GitHub URL] · **Sample report:** `Docs/demo/AAPL_analysis_sample.md`

---

## References (selected)

- Liu, Z., Yu, Y., Cao, Y., Jiang, Y., Li, H., **Lu, Z.**, Wang, Y., et al. (2026). AutoRedTrader: Autonomous Red Teaming of Trading Agents through Synthetic Misinformation Injection. arXiv:2605.09185.  
- **Lu, Z.**, Yin, M., et al. (2023). Modeling Human Trust and Reliance in AI-assisted Decision Making: A Markovian Approach. AAAI (Oral).  
- **Lu, Z.**, et al. Strategic Adversarial Attacks in AI-assisted Decision Making to Reduce Human Trust and Reliance. AAAI.  
- **Lu, Z.**, et al. Large Language Model (LLM)-driven Adversarial Social Influences in Online Information Spread. CHI.  
- AlphaPilot: [repository link]
