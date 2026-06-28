#!/usr/bin/env python3
"""Run full AlphaPilot analysis pipeline directly (no HTTP API), save report.

Usage: python scripts/run_analysis_direct.py AAPL [--no-stream]
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))


async def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    no_stream = "--no-stream" in sys.argv

    print(f"=== AlphaPilot Direct Analysis: {symbol} ===")

    # Create analysis session
    session_id = str(uuid.uuid4())
    analysis_id = str(uuid.uuid4())
    user_id = "demo_user"

    print(f"Session: {session_id}")
    print(f"Analysis: {analysis_id}")

    # ── Run the workflow ──
    print(f"\nRunning analysis pipeline for {symbol}...")
    from services.analysis_service import _run_workflow_sync

    result = _run_workflow_sync(
        user_message=f"对{symbol}进行全面分析，包括市场表现、基本面、新闻事件、多空观点、风险评估和投资组合建议。",
        stock_symbol=symbol,
        user_id=user_id,
        thread_id=session_id,
    )

    # ── Extract results ──
    guard_check = result.get("guard_check", {}) or {}
    final_report = result.get("final_report", "") or ""
    citations = result.get("citations", {}) or {}
    recommendation = result.get("recommendation", "") or ""

    # Evidence packet lives inside guard_check
    ep = guard_check.get("evidence_packet", {}) or {}
    de = ep.get("document_evidence", []) or []

    markers = re.findall(r"\[doc:\s*\d+\]", final_report, re.IGNORECASE)

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Guard Valid: {guard_check.get('is_valid')}")
    print(f"Confidence: {guard_check.get('confidence_score')}")
    print(f"Issues: {guard_check.get('issues', [])}")
    print(f"Warnings: {guard_check.get('warnings', [])}")
    print(f"Document evidence chunks: {len(de)}")
    print(f"Report length: {len(final_report)} chars")
    print(f"[doc:N] markers: {markers}")
    print(f"Citations chunk_ids: {citations.get('chunk_ids', [])}")

    # Section checklist
    for s in ["核心发现", "交叉验证", "整体评估", "投资建议", "风险警告"]:
        marker = "✓" if s in final_report else "✗"
        print(f"  {marker} {s}")

    if de:
        print(f"\nEvidence samples (first 3):")
        for i, ev in enumerate(de[:3]):
            print(f"  [{i}] section={ev.get('section','?')}  chunk_id={ev.get('chunk_id','?')[:60]}")

    # ── Save report ──
    demo_dir = Path("../Docs/demo")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_data = {
        "symbol": symbol,
        "session_id": session_id,
        "analysis_id": analysis_id,
        "timestamp": timestamp,
        "guard": {
            "is_valid": guard_check.get("is_valid"),
            "confidence": guard_check.get("confidence_score"),
            "output_level": guard_check.get("output_level"),
            "issues": guard_check.get("issues", []),
            "warnings": guard_check.get("warnings", []),
        },
        "document_evidence_chunks": len(de),
        "evidence_sections": list(set(ev.get("section", "") for ev in de if ev.get("section"))),
        "report_length": len(final_report),
        "doc_markers": markers,
        "citations": {
            "chunk_ids": citations.get("chunk_ids", []),
            "doc_markers": citations.get("doc_markers", []),
        },
        "report": final_report,
    }

    json_path = demo_dir / f"{symbol}_analysis_{timestamp}.json"
    json_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2))
    print(f"\nSaved: {json_path}")

    # Also save markdown
    md_path = demo_dir / f"{symbol}_analysis_sample.md"
    md_content = f"""# {symbol} AlphaPilot Executive Synthesis

**分析时间**: {timestamp}  
**Guard**: {'Valid' if guard_check.get('is_valid') else 'Invalid'} (confidence={guard_check.get('confidence_score')})  
**文档证据**: {len(de)} chunks  
**[doc:N] 引用**: {', '.join(markers) if markers else '无'}

---

{final_report}

---

## 证据溯源

| # | Section | Chunk |
|---|---------|-------|
"""
    for i, ev in enumerate(de[:10]):
        chunk_id = (ev.get("chunk_id", "") or "")[:40]
        section = ev.get("section", "") or "General"
        md_content += f"| {i+1} | {section} | {chunk_id} |\n"

    if guard_check.get("issues"):
        md_content += "\n---\n## Guard 校验问题\n\n"
        for issue in guard_check["issues"]:
            md_content += f"- {issue}\n"

    md_path.write_text(md_content)
    print(f"Saved: {md_path}")
    print(f"\n{'='*60}")
    print("✅ Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
