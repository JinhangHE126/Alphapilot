# Timeline — 8-Week Standard + 2-Week Mini Pilot

---

## Overview

| Track | Duration | Best for |
|-------|----------|----------|
| **Standard** | 8 weeks | Full G1/G2/G3 + N≈18 before sending memo with results |
| **Mini** | 2 weeks | Fast feasibility + email with "pilot in progress / preliminary" |

---

## Track A: 8-Week Standard

### Week 1 — Technical baseline & attacks

| Day | Task | Output |
|-----|------|--------|
| 1 | `prepare_demo_ingest.py --symbol AAPL` | Ingest verified |
| 2 | Run clean `run_analysis_direct.py AAPL` | `clean_baseline.json` |
| 3 | Draft News perturbation (S2) using MisGen-style prompts | 2 candidate texts |
| 4 | Draft Filing perturbation (S4): numerical + concept | 2 candidate texts |
| 5 | Prerun attacked pipeline; measure RDR | Pick best S2, S4 variants |

**Gate:** S2 or S4 shows RDR=1 or clear narrative shift in ≥1 of 2 preruns. **✅ Passed 2026-07-13** — see [week1_deliverables.md](./week1_deliverables.md).

**Week 1 outputs on disk:**

| Category | Key files |
|----------|-----------|
| Baseline | `assets/clean_baseline.json`, `Docs/demo/AAPL_analysis_sample.md` |
| Perturbations | `assets/s2_*`, `assets/s4_*` |
| Prerun | `assets/attacked_prerun_results.json`, `Docs/demo/AAPL_analysis_ATT_*.json` |
| Log | `06_technical_log_template.md` |
| Code | `scripts/run_attacked_prerun.py`, `alphapilot/research/evidence_attack.py` |

---

### Week 2 — Stimuli packaging & UI export

| Day | Task | Output |
|-----|------|--------|
| 1–2 | Finalize S1–S4 report markdown/HTML | 4 clean/attacked bodies | **✅** [assets/stimuli/](./assets/stimuli/) |
| 3 | Export **G1** views (report only) | `assets/G1_S1–S4.png` |
| 4 | Export **G2** (+ facts panel) | `assets/G2_S1–S4.png` |
| 5 | Export **G3** (+ Guard + citations) | `assets/G3_S1–S4.png` |
| 6–7 | Fill [06_technical_log_template.md](./06_technical_log_template.md) | MER/RDR table complete |

---

### Week 3 — Instrumentation & pretest

| Day | Task | Output |
|-----|------|--------|
| 1–2 | Build Google Form from [04_questionnaire.md](./04_questionnaire.md) | Live form link |
| 3 | Recruit script + scheduling (Calendly / Doodle) | — |
| 4–5 | Cognitive walkthrough **n=3** | Revise wording |
| 6–7 | Fix stimuli if walkthrough shows obvious attacks | v2 assets if needed |

---

### Week 4 — Recruitment

| Task | Target |
|------|--------|
| Post in dept Slack / mailing list / Reddit r/SampleSize | 18+ signups |
| Balance `ui_group` assignment (6 per group) | G1, G2, G3 |
| Send consent + session link | — |

---

### Weeks 5–6 — Data collection

| Task | Notes |
|------|-------|
| Run sessions (remote or in-person) | 25–35 min each |
| Monitor `ui_group` balance | Adjust recruitment if skewed |
| Weekly data export backup | CSV per week |
| Target **N = 18** (min 14) | — |

---

### Week 7 — Analysis

| Task | Output |
|------|--------|
| Clean & merge human + technical logs | `analysis_merged.csv` |
| Fit mixed model / plot Attack×Source×UI | 3 main figures |
| Compute: trust drop, adoption error, detection rate, false trust | Summary table |
| Draft 1-page **Preliminary Findings** | For email attachment |

---

### Week 8 — Application package

| Task | Output |
|------|--------|
| Update [02_research_memo_2page.md](./02_research_memo_2page.md) with results | Memo v2 |
| Finalize [03_outreach_email_draft.md](./03_outreach_email_draft.md) | Send to Dr. Lu |
| Update [README.md](./README.md) status | `pilot_complete` |

---

## Track B: 2-Week Mini Pilot

**Scope:** N=16 · G1 vs G3 only · News-attacked + Filing-attacked (2 trials/participant) + optional clean priming

| Day | Task |
|-----|------|
| **D1** | AAPL clean baseline + log |
| **D2** | Generate S2 (News attacked) + S4 (Filing attacked) |
| **D3** | Export G1 and G3 for S2, S4 only (4 views) |
| **D4** | Short form (T1–T7 × 2 trials) + pretest n=2 |
| **D5–D10** | Collect N=16 (8 per UI group) |
| **D11** | Quick analysis: G1 vs G3 trust/adoption; News vs Filing |
| **D12** | 1-page findings + send email |

**Mini trade-offs:**

- Skip G2 (Facts-Only)  
- Fewer trials per person (2 instead of 4)  
- Report **directional trends** only  
- Still tests **H1c** (UI) and **H2a** (source) at exploratory level  

---

## Weekly Checklist Template

```markdown
## Week __ Check-in

- [ ] Technical milestones met?
- [ ] Blockers: ___
- [ ] Next week priority: ___
- [ ] RA email status: not_sent / sent / replied
```

---

## Commands Reference

```bash
cd alphapilot

# Ingest & clean run
PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL
PYTHONPATH=. python ../scripts/run_analysis_direct.py AAPL

# Optional eval
PYTHONPATH=. python ../scripts/eval_doc_recall.py
```

---

## Deliverables by Track

| Deliverable | 8-week | 2-week mini |
|-------------|--------|-------------|
| Technical log (MER/RDR) | 4 stimuli | 2 attacked |
| UI assets | 12 images | 4 images |
| Human N | 18 | 16 |
| UI conditions | G1, G2, G3 | G1, G3 |
| Memo with results | Week 8 | Day 12 |
