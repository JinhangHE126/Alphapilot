# Stimuli (Week 2 Day 1–2)

Participant-facing report bodies for the human-trust pilot.

## Files

| Stimulus | Markdown | HTML | Source run | Condition |
|----------|----------|------|------------|-----------|
| **S1** | [S1_news_clean.md](./S1_news_clean.md) | [S1_news_clean.html](./S1_news_clean.html) | CLEAN_001 | news · clean |
| **S2** | [S2_news_attacked.md](./S2_news_attacked.md) | [S2_news_attacked.html](./S2_news_attacked.html) | ATT_S2_002 | news · attacked |
| **S3** | [S3_filing_clean.md](./S3_filing_clean.md) | [S3_filing_clean.html](./S3_filing_clean.html) | CLEAN_001 | filing · clean |
| **S4** | [S4_filing_attacked.md](./S4_filing_attacked.md) | [S4_filing_attacked.html](./S4_filing_attacked.html) | ATT_S4_002 | filing · attacked |

Machine-readable index: [stimuli_manifest.json](./stimuli_manifest.json)

## Design notes

- **S1 / S3** share the same CLEAN_001 report body; they differ only by `source_type` label (news vs filing channel badge in header).
- **S2** attack: bearish `news_headline` fact injection (flipping, S2_CANDIDATE_B).
- **S4** attack: concept shift in `Risk_Factors_i03` via `[doc:3]` (S4_CANDIDATE_B).
- Body language: **zh-CN** (pipeline output). Experiment metadata in header is bilingual.
- **G1 body only** — no facts panel, Guard panel, or evidence provenance table (those go in G2/G3 screenshots, Week 2 Day 3–5).
- All files watermarked: `SYNTHETIC — RESEARCH ONLY`.

## Regenerate

```bash
python scripts/package_stimuli.py
python scripts/export_g2_screenshots.py
python scripts/export_g3_screenshots.py
```

## Day 3 Output

- `../G1_S1.png` … `../G1_S4.png` — exported (report only)

## Day 4 Output

- `G2_S1.html` … `G2_S4.html` — G2 composite pages (facts panel + report)
- `../G2_S1.png` … `../G2_S4.png` — exported screenshots

## Day 5 Output

- `G3_S1.html` … `G3_S4.html` — G3 composite pages (facts panel + Guard + citation audit + report)
- `../G3_S1.png` … `../G3_S4.png` — exported screenshots
