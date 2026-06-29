#!/usr/bin/env python3
"""文档检索召回率评估（M6 §4.2）

人工标注 query → 预期命中 section / doc_type → hybrid_retrieve → Recall@5 / @15

用法:
    cd alphapilot && PYTHONPATH=. python ../scripts/eval_doc_recall.py
    # 指定 symbol 范围:
    PYTHONPATH=. python ../scripts/eval_doc_recall.py --symbol AAPL

依赖: FAISS 已加载（rag_data/faiss_index 存在）
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# 人工标注评测集
# 每条: query, expected_sections (至少命中 1 个), symbol, doc_type (optional)
# ═══════════════════════════════════════════════════════════════
ANNOTATED_QUERIES: List[Dict[str, Any]] = [
    # ── AAPL §3.5.1 预期命中 Risk Factors + MD&A + Business ──
    {
        "query": "What are the primary risk factors for Apple's business?",
        "expected_sections": ["risk factors"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    {
        "query": "Apple management discussion of financial condition and results",
        "expected_sections": ["md&a"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    {
        "query": "Apple business overview and operating segments",
        "expected_sections": ["business", "business overview"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    {
        "query": "供应链集中风险和贸易限制对苹果的影响",
        "expected_sections": ["risk factors"],
        "symbol": "AAPL",
    },
    {
        "query": "苹果现金流状况和自由现金流",
        "expected_sections": ["cash flows", "md&a"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    {
        "query": "Apple revenue growth and profit margins",
        "expected_sections": ["md&a"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    {
        "query": "苹果负债权益比和债务结构",
        "expected_sections": ["financial statements", "md&a"],
        "symbol": "AAPL",
    },
    {
        "query": "Apple legal proceedings and regulatory risks",
        "expected_sections": ["risk factors"],
        "symbol": "AAPL",
        "doc_type": "annual_report",
    },
    # ── 0700.HK 季报内容（re-ingest 后 section 为 Financial Statements / 季报标题等）──
    {
        "query": "腾讯2026年第一季度收入构成",
        "expected_sections": [
            "general",
            "financial statements",
            "tencent announces",
            "income",
            "revenue",
        ],
        "symbol": "0700.HK",
        "doc_type": "earnings_call",
    },
    {
        "query": "Tencent Q1 2026 revenue breakdown by segment",
        "expected_sections": [
            "general",
            "financial statements",
            "tencent announces",
            "quarter results",
            "revenue",
        ],
        "symbol": "0700.HK",
    },
    # ── 跨标的检索 ──
    {
        "query": "technology company supply chain concentration risks",
        "expected_sections": ["risk factors"],
        "symbol": "",
        "eval_symbol": "AAPL",
    },
    {
        "query": "company share repurchase program and buyback authorization",
        "expected_sections": ["md&a", "financial statements"],
        "symbol": "",
        "eval_symbol": "AAPL",
    },
    # ── 中文关键词 section boost 验证 (§3.2) ──
    {
        "query": "监管合规风险",
        "expected_sections": ["risk factors"],
        "symbol": "AAPL",
    },
    {
        "query": "管理层经营讨论与分析",
        "expected_sections": ["md&a"],
        "symbol": "AAPL",
    },
    {
        "query": "财务报表附注和会计政策",
        "expected_sections": ["financial statements"],
        "symbol": "AAPL",
    },
]


def _section_match(
    retrieved_sections: List[str],
    expected_sections: List[str],
) -> bool:
    """Check if any retrieved section partially matches an expected section."""
    if not retrieved_sections or not expected_sections:
        return False
    normalized_ret = []
    for ret in retrieved_sections:
        rl = (ret or "").strip().lower()
        if rl in ("", "#", "# #"):
            rl = "general"
        normalized_ret.append(rl)
    for ret in normalized_ret:
        for exp in expected_sections:
            el = exp.lower()
            if el in ret or ret in el:
                return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="", help="只评测指定 symbol")
    parser.add_argument("--k5", action="store_true", default=True, help="计算 Recall@5")
    parser.add_argument("--k15", action="store_true", default=True, help="计算 Recall@15")
    args = parser.parse_args()

    from rag.retriever import retriever

    queries = ANNOTATED_QUERIES
    if args.symbol:
        queries = [q for q in queries if q["symbol"].upper() == args.symbol.upper()]
        if not queries:
            print(f"No annotated queries for symbol={args.symbol}")
            return

    print(f"{'='*70}")
    print(f"📊 Document Recall Evaluation ({len(queries)} annotated queries)")
    print(f"{'='*70}\n")

    results_at5: List[bool] = []
    results_at15: List[bool] = []
    failures: List[Dict[str, Any]] = []

    for i, q in enumerate(queries, 1):
        query_text = q["query"].replace("\n", " ").strip()
        symbol = q.get("symbol", "")
        eval_symbol = q.get("eval_symbol", symbol)
        doc_type = q.get("doc_type", "")
        expected = q.get("expected_sections", [])

        # Retrieve
        hits = retriever.hybrid_retrieve(
            query_text,
            symbol=symbol,
            k=15,
            doc_type=doc_type,
        )
        if eval_symbol:
            hits = [
                h for h in hits
                if (h.get("symbol") or "").upper() == eval_symbol.upper()
            ]

        # Extract sections
        sections_at5 = [h.get("section", "") or "" for h in hits[:5]]
        sections_at15 = [h.get("section", "") or "" for h in hits[:15]]

        hit5 = _section_match(sections_at5, expected)
        hit15 = _section_match(sections_at15, expected)
        results_at5.append(hit5)
        results_at15.append(hit15)

        status5 = "✅" if hit5 else "❌"
        status15 = "✅" if hit15 else "❌"

        top3_sections = ", ".join(
            f"{h.get('section','?')}" for h in hits[:3]
        )

        print(
            f"[{i:2d}] {status5}@5  {status15}@15  | "
            f"`{query_text[:60]}...`"
        )
        print(
            f"     expected={expected}  top3=({top3_sections})"
        )

        if not hit5:
            failures.append({
                "index": i,
                "query": query_text,
                "expected": expected,
                "symbol": symbol,
                "retrieved_sections_at5": sections_at5,
            })

        if i % 5 == 0 and i < len(queries):
            print()

    # ── Summary ──
    recall5 = sum(results_at5) / len(results_at5) if results_at5 else 0
    recall15 = sum(results_at15) / len(results_at15) if results_at15 else 0

    print(f"\n{'='*70}")
    print(f"📈 RESULTS")
    print(f"{'='*70}")
    print(f"  Total queries:     {len(queries)}")
    print(f"  Recall@5:           {sum(results_at5)}/{len(queries)} = {recall5:.1%}")
    print(f"  Recall@15:          {sum(results_at15)}/{len(queries)} = {recall15:.1%}")

    # Breakdown by symbol
    by_symbol = Counter(q.get("symbol", "(all)") for q in queries)
    print(f"\n  Breakdown by symbol:")
    for sym, count in sorted(by_symbol.items()):
        sym_indices = [
            i for i, q in enumerate(queries) if q.get("symbol", "") == sym
        ]
        r5 = sum(results_at5[i] for i in sym_indices)
        r15 = sum(results_at15[i] for i in sym_indices)
        print(f"    {sym:12s}  queries={count:2d}  R@5={r5}/{count}={r5/count:.1%}  R@15={r15}/{count}={r15/count:.1%}")

    if failures:
        print(f"\n  ❌ R@5 misses ({len(failures)}):")
        for f in failures:
            print(
                f"    [{f['index']}] {f['symbol']} | "
                f"\"{f['query'][:70]}\""
            )
            print(
                f"         expected={f['expected']}  "
                f"got={f['retrieved_sections_at5']}"
            )

    # Pass/fail threshold
    threshold = 0.70
    overall_pass = recall5 >= threshold
    print(f"\n  {'✅' if overall_pass else '❌'} Overall: Recall@5={recall5:.1%} "
          f"({'PASS' if overall_pass else 'FAIL'} >= {threshold:.0%})")
    print(f"{'='*70}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
