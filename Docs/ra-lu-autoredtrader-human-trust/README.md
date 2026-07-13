# RA Research — Zhuoran Lu × AutoRedTrader × Human Trust

**Purpose:** Research proposal and application materials for RA outreach to Dr. Zhuoran Lu, bridging [AutoRedTrader](https://arxiv.org/html/2605.09185v1) (agent red-teaming) with human trust/reliance calibration using **AlphaPilot** as the testbed.

**Status:** `Week 1 complete` · Week 2 stimuli packaging next · branch: `research/ra-lu-human-trust-pilot`

**Week 1 index:** [week1_deliverables.md](./week1_deliverables.md)

**Attack placement:** S2 → `news_headline` fact · S4 → `Risk_Factors_i03` chunk (see [06_technical_log_template.md](./06_technical_log_template.md) §0 caveat)

---

## Document Index

| File | Description |
|------|-------------|
| [00_research_proposal_detailed_zh.md](./00_research_proposal_detailed_zh.md) | **自用** · 中文详细规划（最完整，含假设/设计/分析/风险） |
| [assets/clean_baseline.json](./assets/clean_baseline.json) | Day 2 clean run 机器可读基准（CLEAN_001） |
| [01_research_proposal_full.md](./01_research_proposal_full.md) | Full revised proposal (A+C merged: trust + source authority) |
| [02_research_memo_2page.md](./02_research_memo_2page.md) | 2-page English memo for Dr. Lu |
| [03_outreach_email_draft.md](./03_outreach_email_draft.md) | Cold-email draft (<300 words) |
| [04_questionnaire.md](./04_questionnaire.md) | Human pilot survey (pre / per-trial / post) |
| [05_timeline_8week.md](./05_timeline_8week.md) | 8-week standard timeline + 2-week mini pilot |
| [06_technical_log_template.md](./06_technical_log_template.md) | MER / RDR / Guard logging template |
| [week1_deliverables.md](./week1_deliverables.md) | **Week 1 交付物文件清单** |
| [assets/](./assets/) | Screenshots, stimulus PDFs, figures (add as generated) |

---

## Quick Links

| Resource | Path |
|----------|------|
| AlphaPilot demo (AAPL) | [Docs/demo/AAPL_analysis_sample.md](../demo/AAPL_analysis_sample.md) |
| Architecture overview | [Docs/Alphapilot_Architecture_Overview.md](../Alphapilot_Architecture_Overview.md) |
| Doc recall eval | [scripts/eval_doc_recall.py](../../scripts/eval_doc_recall.py) |
| Lu's homepage | https://zhuoranlu.github.io/ |
| AutoRedTrader paper | https://arxiv.org/html/2605.09185v1 |

---

## Research One-Liner

> AutoRedTrader shows agents can be silently steered by subtle misinformation (ASR 26.67%); this project asks whether humans over-trust those steered outputs—and whether citation-auditable UI calibrates reliance—especially when attacks appear in authoritative filing sources vs. news.

---

## Next Actions

- [x] Verify AAPL ingest (`prepare_demo_ingest.py --symbol AAPL`) — 2026-07-11
- [x] Run AAPL clean baseline (`run_analysis_direct.py`) — 20260711_172255
- [x] Day 3: Draft News perturbation (S2) — `assets/s2_news_perturbations.md`
- [x] Day 3: Document FAISS news ingest caveat + channel-aware attack plan — `06_technical_log_template.md` §0
- [x] Day 4: Draft Filing perturbation (S4) — `assets/s4_filing_perturbations.md`
- [x] Day 5: Prerun S2-B + S4-B — `assets/attacked_prerun_results.json` (2026-07-13)
- [x] Week 1 file index — [week1_deliverables.md](./week1_deliverables.md)
- [ ] Week 2: Export G1 / G2 / G3 UI views to `assets/`
- [ ] Pilot cognitive walkthrough (n=3)
- [ ] Collect human data (target N≈18)
- [ ] Finalize [02_research_memo_2page.md](./02_research_memo_2page.md) with preliminary findings
- [ ] Send [03_outreach_email_draft.md](./03_outreach_email_draft.md)

---

*Last updated: 2026-07-13 (Week 1 complete)*
