# Assets

Place generated study materials here.

## Expected files

| Path | Description |
|------|-------------|
| `G1_S1.png` … `G1_S4.png` | No-Audit UI screenshots |
| `G2_S1.png` … `G2_S4.png` | Facts-Only UI screenshots |
| `G3_S1.png` … `G3_S4.png` | Full-Audit UI screenshots |
| `technical_log_AAPL.json` | Machine-readable MER/RDR log |
| `clean_baseline.json` | Day 2 clean baseline (CLEAN_001, 20260711_172255) |
| `s2_news_perturbations.md` | Day 3 S2 attack drafts (MisGen Sentiment + Flipping) |
| `s2_news_perturbations.json` | Machine-readable S2 candidates |
| `s4_filing_perturbations.md` | Day 4 S4 attack drafts (MisGen Numerical + Concept) |
| `s4_filing_perturbations.json` | Machine-readable S4 candidates |
| `attacked_prerun_results.json` | Day 5 MER/RDR summary (4 runs) |
| `stimuli/` | **Week 2 Day 1–2** · S1–S4 markdown/HTML + `stimuli_manifest.json` |
| See [../week1_deliverables.md](../week1_deliverables.md) | Full Week 1 file index |
| `preliminary_figures/` | Analysis plots for memo |

## Attack placement (Week 1)

| Stimulus | Injection target | Notes |
|----------|------------------|-------|
| S2 | `news_headline` fact in evidence packet | FAISS news chunks excluded (ingest noise) |
| S4 | `AAPL_annual_report_Risk_Factors_i03` | CLEAN_001 `[doc:3]`; filing RAG path |

See [`06_technical_log_template.md`](../06_technical_log_template.md) §0 for ingest caveat.

## Sources

- Export from AlphaPilot web UI after analysis, or
- Render from `Docs/demo/AAPL_analysis_sample.md` with manual Guard/Citation sections for G3

**Note:** Mark all attacked stimuli as `SYNTHETIC — RESEARCH ONLY` in filename or watermark.
