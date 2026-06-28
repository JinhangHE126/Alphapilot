#!/usr/bin/env python3
"""M5 演示标的数据准备：对 AAPL/0700 执行 fetch + 打印 chunk 按 section 统计。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="M5 demo ingest prep")
    parser.add_argument("--symbol", choices=["AAPL", "0700.HK", "TSLA"], default="0700.HK")
    parser.add_argument("--fetch", action="store_true", help="run fetchers to grab fresh docs")
    args = parser.parse_args()

    print(f"=== M5 Demo Ingest Prep: {args.symbol} ===\n")

    # 1) Check existing RAG index
    from rag.retriever import retriever
    if not retriever.vectorstore:
        print("❌ Vectorstore not initialized — run api/main.py first")
        sys.exit(1)

    # 2) Count existing chunks for the symbol
    total_docs = len(retriever.vectorstore.docstore._dict)
    print(f"  FAISS total known: {total_docs}")

    # Scan for this symbol's chunks via quick retrieval
    results = retriever.retrieve_doc_chunks(args.symbol, symbol=args.symbol, k=50)
    chunks = [r for r in results if r.get("symbol", "").upper() == args.symbol.upper()]
    print(f"  Chunks for {args.symbol}: {len(chunks)} retrieved\n")

    if not chunks:
        print("  ⚠️ No chunks found — run fetch/ingest first:")
        print(f"     DOC_FETCH_ENABLED=true DOC_FETCH_SYMBOLS={args.symbol} python -m api.main")
        print("     or upload a PDF via POST /api/upload/document")
        if args.fetch:
            _run_fetch(args.symbol)
        sys.exit(0)

    # 3) Chunk statistics by section
    section_counter: Counter[str] = Counter()
    doc_type_counter: Counter[str] = Counter()
    table_chunks = 0
    samples: list[dict] = []

    for c in chunks:
        sec = c.get("section", "") or "(empty)"
        section_counter[sec] += 1
        doc_type_counter[c.get("doc_type", "") or "(none)"] += 1
        if c.get("contains_table"):
            table_chunks += 1
        if len(samples) < 5:
            samples.append(c)

    print("  --- Section distribution ---")
    for sec, count in section_counter.most_common(15):
        print(f"    {count:4d}  {sec[:70]}")

    print(f"\n  --- Doc type distribution ---")
    for dt, count in doc_type_counter.most_common():
        print(f"    {count:4d}  {dt}")

    print(f"\n  --- Table chunks: {table_chunks}/{len(chunks)} ---")

    print(f"\n  --- Sample chunk IDs ---")
    for s in samples:
        cid = s.get("chunk_id", "")
        sec = s.get("section", "") or "(empty)"
        dt = s.get("doc_type", "")
        page = s.get("page", "")
        print(f"    [{cid}]")
        print(f"      section=\"{sec}\"  doc_type={dt}  page={page}  table={s.get('contains_table', False)}")

    print("\n✅ Demo ingest prep complete")
    print(f"   Symbol {args.symbol}: {len(chunks)} chunks, {len(section_counter)} sections, {table_chunks} with tables")


def _run_fetch(symbol: str):
    """触发一次文档抓取（需 yfinance 环境）。"""
    try:
        from knowledge.fetchers.hkex_fetcher import fetch_hkex_annual_reports
        from knowledge.document_ingest import ingest_file

        if symbol == "0700.HK":
            print("  🔍 Running HKEX fetch for 0700.HK...")
            # HKEX fetcher needs the activestock JSON data; skip if unavailable
            print("  ⚠️ HKEX fetch requires activestock_*.json in data/hkex/ — skipping auto-fetch")
    except ImportError:
        print("  ⚠️ yfinance not installed — skipping auto-fetch")


if __name__ == "__main__":
    main()
