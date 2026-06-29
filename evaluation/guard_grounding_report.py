#!/usr/bin/env python3
"""Guard doc grounding 通过率统计（M6 §4.2）

离线分析 Demo JSON 报告中的 Guard 校验结果：
- [doc:N] 引用是否存在（grounding audit）
- citation chunk_ids 是否与 evidence_packet 对齐
- Guard Valid 占比
- 各项检查的 passing rate

用法:
    cd alphapilot && PYTHONPATH=. python ../evaluation/guard_grounding_report.py
    # 指定分析目录:
    PYTHONPATH=. python ../evaluation/guard_grounding_report.py --input-dir ../Docs/demo

数据来源: Docs/demo/*_analysis_*.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[1] / "Docs" / "demo"


def load_reports(input_dir: Path) -> List[Dict[str, Any]]:
    """Load all analysis JSON files from the demo directory."""
    reports: List[Dict[str, Any]] = []
    for jf in sorted(input_dir.glob("*_analysis_*.json")):
        try:
            with open(jf) as f:
                reports.append(json.load(f))
        except Exception as exc:
            print(f"⚠️ Skipped {jf.name}: {exc}")
    return reports


def extract_doc_markers(text: str) -> List[int]:
    """Extract unique [doc:N] numbers from text."""
    found = re.findall(r"\[doc:\s*(\d+)\]", text, re.IGNORECASE)
    return sorted(set(int(m) for m in found))


def grounding_check(report: Dict[str, Any]) -> Dict[str, Any]:
    """Run grounding audit on a single report."""
    symbol = report.get("symbol", "?")
    guard = report.get("guard", {}) or {}
    citations = report.get("citations", {}) or {}
    report_text = report.get("report", "") or ""

    is_valid = guard.get("is_valid", False)
    confidence = guard.get("confidence_score") or guard.get("confidence", 0)
    issues = guard.get("issues", [])
    warnings = list(guard.get("warnings", []) or []) + list(guard.get("grounding_warnings", []) or [])
    evidence_chunks = report.get("document_evidence_chunks", 0)
    evidence_sections = report.get("evidence_sections", [])

    # Extract [doc:N] markers from report text
    doc_markers = extract_doc_markers(report_text)

    # Citation chunk_ids
    citation_ids = citations.get("chunk_ids", []) or []
    citation_markers = citations.get("doc_markers", []) or []

    # Grounding checks
    has_doc_evidence = evidence_chunks > 0
    has_markers = len(doc_markers) > 0
    citation_count_ok = len(citation_ids) > 0
    multi_marker_ok = len(set(doc_markers)) >= 2  # ≥2 distinct [doc:N]
    marker_chunk_align = True
    if doc_markers and evidence_chunks > 0:
        # [doc:N] must be within 1..len(document_evidence), not <= len(citation_ids)
        for m in doc_markers:
            if m < 1 or m > evidence_chunks:
                marker_chunk_align = False
                break
        # Each in-range marker should map to a persisted citation
        if marker_chunk_align and citation_markers:
            cited_nums = set()
            for cm in citation_markers:
                if isinstance(cm, str) and ":" in cm:
                    try:
                        cited_nums.add(int(cm.split(":", 1)[1]))
                    except ValueError:
                        pass
            for m in doc_markers:
                if 1 <= m <= evidence_chunks and m not in cited_nums:
                    marker_chunk_align = False
                    break

    # Level 3 warning: evidence but no markers
    level3_warning = any("missing citations" in w.lower() for w in warnings)

    checks = {
        "guard_valid": is_valid,
        "evidence_chunks_present": has_doc_evidence,
        "doc_markers_in_report": has_markers,
        "citations_written": citation_count_ok,
        "multi_doc_references": multi_marker_ok,
        "marker_chunk_alignment": marker_chunk_align,
        "no_level3_warning": not level3_warning,
    }

    all_pass = all(checks.values())

    return {
        "symbol": symbol,
        "guard_valid": is_valid,
        "confidence": confidence,
        "evidence_chunks": evidence_chunks,
        "evidence_sections": evidence_sections,
        "doc_marker_count": len(doc_markers),
        "doc_markers": doc_markers,
        "citation_count": len(citation_ids),
        "checks": checks,
        "all_checks_pass": all_pass,
        "issues": issues,
        "warnings": warnings,
    }


def print_grounding_result(result: Dict[str, Any], index: int):
    """Pretty-print a single grounding result."""
    symbol = result["symbol"]
    status = "✅" if result["all_checks_pass"] else "⚠️"
    checks = result["checks"]

    print(f"\n[{index}] {status} {symbol}")
    print(f"    Guard Valid={result['guard_valid']}  confidence={result['confidence']}")
    print(f"    Evidence chunks={result['evidence_chunks']}  "
          f"sections={result['evidence_sections']}")
    print(f"    [doc:N] markers in report: {result['doc_marker_count']} "
          f"→ {result['doc_markers']}")
    print(f"    Citations written: {result['citation_count']}")

    # Detail checks
    for name, passed in checks.items():
        if name in ("guard_valid",):
            continue
        icon = "✅" if passed else "❌"
        print(f"      {icon} {name}")

    if result["issues"]:
        print(f"    Guard Issues:")
        for issue in result["issues"]:
            print(f"      - {issue}")
    if result.get("warnings"):
        warn_str = ", ".join(result["warnings"][:2])
        print(f"    Guard Warnings: {warn_str}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="包含 *_analysis_*.json 的目录",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"❌ Directory not found: {input_dir}")
        sys.exit(1)

    reports = load_reports(input_dir)
    if not reports:
        print(f"❌ No *_analysis_*.json files found in {input_dir}")
        print("   Run scripts/run_analysis_direct.py first to generate reports.")
        sys.exit(1)

    print(f"{'='*70}")
    print(f"🛡️  Guard Doc Grounding Report")
    print(f"{'='*70}")
    print(f"  Input: {input_dir}")
    print(f"  Reports analyzed: {len(reports)}")
    print()

    results: List[Dict[str, Any]] = []
    for i, r in enumerate(reports, 1):
        result = grounding_check(r)
        results.append(result)
        print_grounding_result(result, i)

    # ── Aggregate stats ──
    n = len(results)
    valid_count = sum(1 for r in results if r["guard_valid"])
    all_pass_count = sum(1 for r in results if r["all_checks_pass"])
    evidence_count = sum(1 for r in results if r["checks"]["evidence_chunks_present"])
    markers_count = sum(1 for r in results if r["checks"]["doc_markers_in_report"])
    citations_count = sum(1 for r in results if r["checks"]["citations_written"])
    multi_doc_count = sum(1 for r in results if r["checks"]["multi_doc_references"])

    print(f"\n{'='*70}")
    print(f"📊 AGGREGATE STATS")
    print(f"{'='*70}")
    print(f"  Reports evaluated:           {n}")
    print(f"  Guard Valid:                 {valid_count}/{n} = {valid_count/n:.1%}")
    print(f"  All grounding checks pass:   {all_pass_count}/{n} = {all_pass_count/n:.1%}")
    print()
    print(f"  ── Individual checks ──")
    print(f"  Evidence chunks present:     {evidence_count}/{n} = {evidence_count/n:.1%}")
    print(f"  [doc:N] markers in report:   {markers_count}/{n} = {markers_count/n:.1%}")
    print(f"  Citations written:           {citations_count}/{n} = {citations_count/n:.1%}")
    print(f"  Multi-doc references (≥2):   {multi_doc_count}/{n} = {multi_doc_count/n:.1%}")

    # Section distribution across all reports
    all_sections: Counter = Counter()
    for r in results:
        for s in r.get("evidence_sections", []) or []:
            all_sections[s] += 1
    if all_sections:
        print(f"\n  Evidence section distribution:")
        for sec, cnt in all_sections.most_common(10):
            print(f"    {cnt:3d}  {sec}")

    # Marker count distribution
    marker_dist: Counter = Counter()
    for r in results:
        marker_dist[r["doc_marker_count"]] += 1
    print(f"\n  [doc:N] marker count distribution:")
    for cnt, freq in sorted(marker_dist.items()):
        bar = "█" * freq
        print(f"    {cnt:2d} markers: {freq} reports {bar}")

    # ── Total aggregation ──
    total_evidence = sum(r["evidence_chunks"] for r in results)
    total_markers = sum(r["doc_marker_count"] for r in results)
    total_citations = sum(r["citation_count"] for r in results)

    print(f"\n  ── Totals across {n} reports ──")
    print(f"  Evidence chunks:             {total_evidence}")
    print(f"  [doc:N] markers:             {total_markers}")
    print(f"  Citations written:           {total_citations}")

    avg_markers = total_markers / n if n else 0
    avg_evidence = total_evidence / n if n else 0
    print(f"  Avg markers/report:          {avg_markers:.1f}")
    print(f"  Avg evidence chunks/report:  {avg_evidence:.1f}")

    # Pass/fail
    threshold = 0.85  # 85% of reports should pass all grounding checks
    pct = all_pass_count / n if n else 0
    print(f"\n  {'✅' if pct >= threshold else '❌'} Overall: {all_pass_count}/{n} "
          f"all-checks-pass = {pct:.1%} "
          f"({'PASS' if pct >= threshold else 'FAIL'} >= {threshold:.0%})")

    print(f"{'='*70}")

    return 0 if pct >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
