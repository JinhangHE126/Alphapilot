#!/usr/bin/env python3
"""Export Week 2 Day 5 G3 screenshots (facts panel + Guard + citation audit + report)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from export_g2_screenshots import (
    ASSETS_DIR,
    STIMULI_DIR,
    build_facts_panel_html,
    markdown_report_html,
    resolve_chrome_binary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOW_SIZE = "1400,5200"

STIMULI = [
    ("S1", "S1_news_clean.md", "G3_S1.html", "G3_S1.png", "CLEAN_001"),
    ("S2", "S2_news_attacked.md", "G3_S2.html", "G3_S2.png", "ATT_S2_002"),
    ("S3", "S3_filing_clean.md", "G3_S3.html", "G3_S3.png", "CLEAN_001"),
    ("S4", "S4_filing_attacked.md", "G3_S4.html", "G3_S4.png", "ATT_S4_002"),
]

RUN_JSON = {
    "CLEAN_001": REPO_ROOT / "Docs/demo/AAPL_analysis_20260711_172255.json",
    "ATT_S2_002": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S2_002_20260713_160524.json",
    "ATT_S4_002": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S4_002_20260713_161637.json",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_run_bundle(run_key: str) -> dict:
    data = load_json(RUN_JSON[run_key])
    if run_key == "CLEAN_001":
        clean_meta = load_json(REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets/clean_baseline.json")
        return {
            "kind": "clean",
            "report": data.get("report", ""),
            "guard_valid": data.get("guard", {}).get("is_valid"),
            "guard_confidence": data.get("guard", {}).get("confidence"),
            "output_level": data.get("guard", {}).get("output_level"),
            "final_reasoning": "all checks passed" if data.get("guard", {}).get("is_valid") else "",
            "warnings": (data.get("guard", {}).get("warnings") or []) + (data.get("guard", {}).get("grounding_warnings") or []),
            "checks": {
                "document_evidence": {
                    "passed": True,
                    "detail": f"{data.get('document_evidence_chunks', 0)} cited chunks in clean baseline",
                },
                "citation_coverage": {
                    "passed": True,
                    "detail": f"Distinct markers: {', '.join(data.get('citations', {}).get('doc_markers', [])) or 'none'}",
                },
            },
            "facts": [],
            "citation_rows": [
                {
                    "marker": marker,
                    "chunk_id": chunk_id,
                    "section": "Risk Factors",
                    "source": "SEC",
                    "publish_date": "2025-10-31",
                }
                for marker, chunk_id in zip(
                    data.get("citations", {}).get("doc_markers", []),
                    data.get("citations", {}).get("chunk_ids", []),
                )
            ],
            "clean_meta": clean_meta,
        }

    guard = data.get("guard_full", {}) or {}
    packet = guard.get("evidence_packet", {}) or {}
    doc_evidence = packet.get("document_evidence", []) or []
    cited_markers = sorted(set(re.findall(r"\[doc:(\d+)\]", data.get("report", ""))), key=int)
    citation_rows = []
    for marker in cited_markers:
        idx = int(marker) - 1
        row = doc_evidence[idx] if 0 <= idx < len(doc_evidence) else {}
        citation_rows.append(
            {
                "marker": f"doc:{marker}",
                "chunk_id": row.get("chunk_id", "unknown"),
                "section": row.get("section", "unknown"),
                "source": row.get("source", "unknown"),
                "publish_date": row.get("publish_date", "-"),
            }
        )

    return {
        "kind": "attacked",
        "report": data.get("report", ""),
        "guard_valid": guard.get("is_valid"),
        "guard_confidence": guard.get("confidence_score"),
        "output_level": guard.get("output_level"),
        "final_reasoning": guard.get("final_reasoning", ""),
        "warnings": (guard.get("warnings") or []) + (guard.get("grounding_warnings") or []),
        "checks": guard.get("checks") or {},
        "facts": packet.get("facts") or [],
        "citation_rows": citation_rows,
        "document_evidence_count": len(doc_evidence),
    }


def guard_status_badge(is_valid: bool | None, confidence: int | None, output_level: str | None) -> str:
    tone = "pass" if is_valid else "warn"
    label = "Pass" if is_valid else "Warn"
    conf = f" · confidence={confidence}" if confidence is not None else ""
    level = f" · {output_level}" if output_level else ""
    return f'<span class="guard-status {tone}">Guard {label}{conf}{level}</span>'


def render_check_row(label: str, passed: bool | None, detail: str) -> str:
    tone = "pass" if passed else "warn"
    status = "通过" if passed else "关注"
    return (
        "<tr>"
        f"<td>{label}</td>"
        f'<td><span class="guard-chip {tone}">{status}</span></td>'
        f"<td>{detail or '-'}</td>"
        "</tr>"
    )


def build_guard_panel_html(bundle: dict) -> str:
    checks = bundle.get("checks") or {}
    rows = []
    label_map = {
        "data_coverage": "数据覆盖",
        "symbol_match": "标的匹配",
        "unsupported_claim": "无依据声明",
        "document_evidence": "文档证据",
        "citation_coverage": "引用覆盖",
    }
    for key, payload in checks.items():
        if isinstance(payload, dict):
            rows.append(
                render_check_row(
                    label_map.get(key, key),
                    payload.get("passed"),
                    payload.get("detail", ""),
                )
            )

    warnings = bundle.get("warnings") or []
    warnings_html = "".join(f"<li>{w}</li>" for w in warnings) if warnings else "<li>No warnings</li>"
    reasoning = bundle.get("final_reasoning") or "No additional reasoning."

    return f"""
<section class="card audit-card">
  <div class="g3-badge">G3 · Full-Audit UI</div>
  <div class="audit-section-header">
    <div>
      <div class="audit-title">Guard 校验</div>
      <div class="audit-subtitle">展示输出级别、检查项和 groundedness 警告，帮助被试校准对 AI 报告的依赖。</div>
    </div>
    {guard_status_badge(bundle.get("guard_valid"), bundle.get("guard_confidence"), bundle.get("output_level"))}
  </div>
  <table class="audit-table">
    <thead><tr><th>检查项</th><th>状态</th><th>详情</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <div class="audit-warnings">
    <div class="audit-mini-title">Warnings</div>
    <ul>{warnings_html}</ul>
  </div>
  <div class="audit-reasoning">
    <span class="audit-mini-title">Final reasoning</span>
    <p>{reasoning}</p>
  </div>
</section>
"""


def build_citation_audit_html(bundle: dict) -> str:
    rows = bundle.get("citation_rows") or []
    if not rows:
        body = "<tr><td colspan='5'>No citation rows available.</td></tr>"
    else:
        body = "".join(
            "<tr>"
            f"<td><code>{row.get('marker', '-')}</code></td>"
            f"<td><code>{row.get('chunk_id', '-')}</code></td>"
            f"<td>{row.get('section', '-')}</td>"
            f"<td>{row.get('source', '-')}</td>"
            f"<td>{row.get('publish_date', '-')}</td>"
            "</tr>"
            for row in rows
        )

    return f"""
<section class="card citation-card">
  <div class="audit-section-header">
    <div>
      <div class="audit-title">Citation audit</div>
      <div class="audit-subtitle">把报告中的 `[doc:N]` 映射到实际 chunk，显示 section / source / publish date。</div>
    </div>
  </div>
  <table class="audit-table">
    <thead><tr><th>Marker</th><th>Chunk ID</th><th>Section</th><th>Source</th><th>Publish date</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""


G3_CSS = """
body { margin: 0; background: #0b1220; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.shell { max-width: 1080px; margin: 0 auto; padding: 1.5rem 1.25rem 2rem; }
.card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 1rem; }
.g3-badge { display:inline-block; font-size:0.62rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:#c4b5fd; border:1px solid rgba(167,139,250,0.25); background:rgba(139,92,246,0.08); border-radius:999px; padding:0.18rem 0.55rem; margin-bottom:0.75rem; }
.report-card { line-height: 1.7; font-size: 0.92rem; color: rgba(240,244,255,0.9); }
.report-card h1, .report-card h2, .report-card h3 { color: #f1f5f9; }
.report-card h2 { font-size: 1.1rem; margin-top: 1.4rem; }
.report-card blockquote { color: #f59e0b; border-left: 3px solid #f59e0b; margin: 0 0 1rem; padding-left: 0.75rem; }
.report-card strong { color: #f8fafc; }
.doc-ref { color: #60a5fa; font-size: 0.75rem; }
.fin-trends { display:flex; flex-direction:column; gap:0.9rem; }
.fin-trends-header, .audit-section-header { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
.fin-trends-badge { font-size:0.58rem; letter-spacing:0.06em; text-transform:uppercase; color:#93c5fd; border:1px solid rgba(96,165,250,0.2); border-radius:999px; padding:0.16rem 0.5rem; }
.fin-trends-subtitle, .audit-subtitle { margin:0.2rem 0 0; color:rgba(148,163,184,0.8); font-size:0.72rem; }
.fin-metrics-row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0.55rem; }
.fin-metric-card { display:flex; gap:0.45rem; padding:0.65rem; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); }
.fin-metric-card.positive { border-color:rgba(34,197,94,0.12); }
.fin-metric-card.negative { border-color:rgba(248,113,113,0.14); }
.fin-metric-icon { width:28px; height:28px; display:flex; align-items:center; justify-content:center; border-radius:7px; background:rgba(255,255,255,0.06); color:rgba(255,255,255,0.45); }
.fin-metric-label { font-size:0.62rem; color:rgba(255,255,255,0.38); text-transform:uppercase; letter-spacing:0.04em; }
.fin-metric-value { font-size:0.9rem; font-weight:700; }
.fin-metric-sub { font-size:0.62rem; color:rgba(255,255,255,0.45); }
.fin-metric-sub.positive { color:#4ade80; }
.fin-metric-sub.negative { color:#f87171; }
.fin-metric-source { font-size:0.56rem; color:rgba(255,255,255,0.25); }
.fin-section-label { font-size:0.68rem; font-weight:600; color:rgba(255,255,255,0.42); text-transform:uppercase; margin-bottom:0.4rem; }
.fin-gauges-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.55rem 0.8rem; }
.fin-gauge-label { font-size:0.66rem; color:rgba(255,255,255,0.48); }
.fin-gauge-value { font-size:0.78rem; font-weight:700; }
.fin-gauge-header { display:flex; justify-content:space-between; margin-bottom:0.2rem; }
.fin-gauge-bar-wrap { height:6px; border-radius:999px; background:rgba(255,255,255,0.06); overflow:hidden; }
.fin-gauge-bar { height:100%; border-radius:999px; }
.fin-health-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0.55rem; }
.fin-health-item, .fin-health-score { padding:0.55rem 0.65rem; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); }
.fin-health-label, .fin-health-score-label { font-size:0.62rem; color:rgba(255,255,255,0.42); text-transform:uppercase; }
.fin-health-value { font-size:0.86rem; font-weight:700; }
.fin-health-score.positive, .fin-health-item.positive { border-color:rgba(34,197,94,0.14); }
.fin-health-score.negative, .fin-health-item.negative { border-color:rgba(248,113,113,0.16); }
.fin-sources { margin-top:0.8rem; display:flex; flex-wrap:wrap; gap:0.35rem; align-items:center; }
.fin-sources-label { font-size:0.62rem; color:rgba(255,255,255,0.38); margin-right:0.25rem; }
.fin-source-badge { font-size:0.62rem; color:#bfdbfe; background:rgba(59,130,246,0.12); border:1px solid rgba(96,165,250,0.18); border-radius:999px; padding:0.12rem 0.45rem; }
.audit-title { font-size: 0.92rem; font-weight: 700; color: rgba(255,255,255,0.92); }
.guard-status { display:inline-flex; align-items:center; gap:0.3rem; font-size:0.64rem; font-weight:700; border-radius:999px; padding:0.2rem 0.55rem; white-space:nowrap; }
.guard-status.pass { color:#86efac; background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.2); }
.guard-status.warn { color:#fcd34d; background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.2); }
.audit-table { width:100%; border-collapse:collapse; margin-top:0.85rem; font-size:0.74rem; }
.audit-table th, .audit-table td { border-bottom:1px solid rgba(255,255,255,0.08); padding:0.55rem 0.45rem; text-align:left; vertical-align:top; }
.audit-table th { color:rgba(148,163,184,0.92); font-size:0.64rem; text-transform:uppercase; letter-spacing:0.04em; }
.guard-chip { display:inline-flex; align-items:center; font-size:0.62rem; font-weight:700; border-radius:999px; padding:0.14rem 0.42rem; }
.guard-chip.pass { color:#86efac; background:rgba(34,197,94,0.1); }
.guard-chip.warn { color:#fcd34d; background:rgba(245,158,11,0.1); }
.audit-warnings ul { margin:0.55rem 0 0; padding-left:1.15rem; }
.audit-warnings li { margin:0.32rem 0; color:rgba(248,250,252,0.86); }
.audit-mini-title { display:block; font-size:0.66rem; font-weight:700; color:rgba(196,181,253,0.92); text-transform:uppercase; letter-spacing:0.05em; margin-top:0.8rem; }
.audit-reasoning p { margin:0.35rem 0 0; color:rgba(226,232,240,0.88); }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:0.72rem; color:#dbeafe; }
"""


def build_g3_html(stimulus_id: str, md_path: Path, bundle: dict) -> str:
    facts_html = build_facts_panel_html(bundle.get("facts") or [])
    guard_html = build_guard_panel_html(bundle)
    citation_html = build_citation_audit_html(bundle)
    report_html = markdown_report_html(md_path)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AAPL G3 — {stimulus_id}</title>
  <style>{G3_CSS}</style>
</head>
<body>
  <div class="shell">
    {facts_html}
    {guard_html}
    {citation_html}
    <section class="card report-card">{report_html}</section>
  </div>
</body>
</html>
"""


def export_screenshot(chrome_bin: str, html_path: Path, png_path: Path) -> None:
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={WINDOW_SIZE}",
        f"--screenshot={png_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    chrome_bin = resolve_chrome_binary()
    STIMULI_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using Chrome binary: {chrome_bin}")
    for stimulus_id, md_name, html_name, png_name, run_key in STIMULI:
        md_path = STIMULI_DIR / md_name
        html_path = STIMULI_DIR / html_name
        png_path = ASSETS_DIR / png_name
        bundle = load_run_bundle(run_key)
        html_path.write_text(build_g3_html(stimulus_id, md_path, bundle), encoding="utf-8")
        export_screenshot(chrome_bin, html_path, png_path)
        print(f"Exported {png_name} ({len(bundle.get('citation_rows') or [])} citations)")


if __name__ == "__main__":
    main()
