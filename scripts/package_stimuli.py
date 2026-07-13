#!/usr/bin/env python3
"""Package Week 2 human-trust stimuli (S1–S4) from demo JSON outputs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets/stimuli"

SOURCES = {
    "S1": {
        "source_json": REPO_ROOT / "Docs/demo/AAPL_analysis_20260711_172255.json",
        "run_id": "CLEAN_001",
        "stimulus_id": "S1",
        "source_type": "news",
        "attack": "clean",
        "source_badge": "证据通道 · 市场新闻与标题",
        "source_badge_en": "Evidence channel: market news & headlines",
    },
    "S2": {
        "source_json": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S2_002_20260713_160524.json",
        "run_id": "ATT_S2_002",
        "stimulus_id": "S2",
        "source_type": "news",
        "attack": "attacked",
        "source_badge": "证据通道 · 市场新闻与标题",
        "source_badge_en": "Evidence channel: market news & headlines",
        "backup_run_id": "ATT_S2_001",
    },
    "S3": {
        "source_json": REPO_ROOT / "Docs/demo/AAPL_analysis_20260711_172255.json",
        "run_id": "CLEAN_001",
        "stimulus_id": "S3",
        "source_type": "filing",
        "attack": "clean",
        "source_badge": "证据通道 · SEC 10-K 年报摘录",
        "source_badge_en": "Evidence channel: SEC 10-K annual report excerpts",
    },
    "S4": {
        "source_json": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S4_002_20260713_161637.json",
        "run_id": "ATT_S4_002",
        "stimulus_id": "S4",
        "source_type": "filing",
        "attack": "attacked",
        "source_badge": "证据通道 · SEC 10-K 年报摘录",
        "source_badge_en": "Evidence channel: SEC 10-K annual report excerpts",
        "backup_run_id": "ATT_S4_001",
    },
}

WATERMARK = "SYNTHETIC — RESEARCH ONLY · 非投资建议"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def strip_evidence_appendix(report: str) -> str:
    """Remove trailing evidence tables if accidentally included."""
    report = report.strip()
    for marker in ("## 证据溯源", "## Evidence Provenance"):
        idx = report.find(marker)
        if idx != -1:
            report = report[:idx].rstrip()
    return report


def extract_recommendation(data: dict) -> str:
    for key in ("recommendation_attacked", "recommendation", "recommendation_clean"):
        val = data.get(key)
        if val and val != "Unknown":
            return str(val)
    return "Hold"


def build_header(meta: dict, data: dict) -> str:
    rec = extract_recommendation(data)
    guard = data.get("guard") or data.get("guard_full") or {}
    guard_valid = guard.get("is_valid")
    guard_conf = guard.get("confidence") or guard.get("confidence_score")
    guard_line = ""
    if guard_valid is not None:
        guard_line = f"**Guard**: {'Valid' if guard_valid else 'Invalid'}"
        if guard_conf is not None:
            guard_line += f" (confidence={guard_conf})"

    lines = [
        f"# AAPL AlphaPilot Equity Research Brief",
        "",
        f"> {WATERMARK}",
        "",
        f"**Stimulus**: {meta['stimulus_id']} · **Source**: {meta['source_type']} · **Condition**: {meta['attack']}",
        f"**Run ID**: {meta['run_id']} · **Symbol**: AAPL (Apple Inc.)",
        f"**{meta['source_badge']}** · *{meta['source_badge_en']}*",
        f"**Recommendation**: {rec}",
    ]
    if guard_line:
        lines.append(guard_line)
    lines.extend(["", "---", "", ""])
    return "\n".join(lines)


def report_to_html(markdown_body: str, title: str) -> str:
    """Minimal HTML wrapper for Google Form / screenshot embedding."""
    # Very light conversion: preserve [doc:N], headings, bold, lists.
    html = markdown_body
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.M)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.M)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"^> (.+)$", r"<p class=\"watermark\">\1</p>", html, flags=re.M)
    html = re.sub(r"^---$", "<hr>", html, flags=re.M)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.M)
    html = re.sub(r"(\[doc:\d+\])", r"<sup>\1</sup>", html)
    html = html.replace("\n\n", "</p><p>")
    html = f"<p>{html}</p>"
    html = re.sub(r"<p>(<h[12]>)", r"\1", html)
    html = re.sub(r"(</h[12]>)</p>", r"\1", html)
    html = re.sub(r"<p><li>", "<ul><li>", html)
    html = re.sub(r"</li></p>", "</li></ul>", html)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
    .watermark {{ color: #b45309; font-size: 0.85rem; border-left: 3px solid #f59e0b; padding-left: 0.75rem; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
    h2 {{ font-size: 1.15rem; margin-top: 1.5rem; color: #374151; }}
    hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }}
    sup {{ color: #2563eb; font-size: 0.75rem; }}
  </style>
</head>
<body>
{html}
</body>
</html>
"""


def package_one(key: str, meta: dict) -> dict:
    data = load_json(meta["source_json"])
    report = strip_evidence_appendix(data["report"])
    header = build_header(meta, data)
    markdown = header + report + "\n"

    stem = f"{meta['stimulus_id']}_{meta['source_type']}_{meta['attack']}"
    md_path = STIMULI_DIR / f"{stem}.md"
    html_path = STIMULI_DIR / f"{stem}.html"

    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(report_to_html(markdown, f"AAPL — {meta['stimulus_id']}"), encoding="utf-8")

    return {
        "stimulus_id": meta["stimulus_id"],
        "source_type": meta["source_type"],
        "attack": meta["attack"],
        "run_id": meta["run_id"],
        "backup_run_id": meta.get("backup_run_id"),
        "source_json": str(meta["source_json"].relative_to(REPO_ROOT)),
        "markdown": str(md_path.relative_to(REPO_ROOT)),
        "html": str(html_path.relative_to(REPO_ROOT)),
        "recommendation": extract_recommendation(data),
        "MER": data.get("MER", 0.0),
        "RDR": data.get("RDR", 0),
        "guard_valid": (data.get("guard") or {}).get("is_valid"),
        "guard_confidence": (data.get("guard") or {}).get("confidence"),
        "report_length": len(report),
        "language": "zh-CN",
        "watermark": WATERMARK,
    }


def main() -> None:
    STIMULI_DIR.mkdir(parents=True, exist_ok=True)
    entries = [package_one(key, meta) for key, meta in SOURCES.items()]

    manifest = {
        "study": "When Agents Are Steered, Do Humans Over-Trust?",
        "symbol": "AAPL",
        "packaged_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week": 2,
        "task": "Day 1–2 stimuli packaging",
        "note": "S1/S3 share CLEAN_001 body; differ by source_type label only. Body language zh-CN; questionnaire metadata English.",
        "stimuli": entries,
    }

    manifest_path = STIMULI_DIR / "stimuli_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Packaged {len(entries)} stimuli → {STIMULI_DIR.relative_to(REPO_ROOT)}/")
    for e in entries:
        print(f"  {e['stimulus_id']}: {e['markdown']} ({e['recommendation']}, MER={e['MER']})")


if __name__ == "__main__":
    main()
