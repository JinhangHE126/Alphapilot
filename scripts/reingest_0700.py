#!/usr/bin/env python3
"""Re-ingest 0700.HK (Tencent Q1 2026) PDF into FAISS doc chunks."""
from __future__ import annotations

import re
import sys
import uuid
from datetime import date
from pathlib import Path
from collections import Counter
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

TENCENT_PDF_URL = (
    "https://static.www.tencent.com/uploads/2026/05/13/"
    "47382ae415a209fd161bc19a1f9b3704.pdf"
)

def main():
    print("=" * 60)
    print("0700.HK — Re-ingest Tencent Q1 2026 PDF")
    print("=" * 60)

    # 1. Download PDF
    print("\n[1/3] Downloading Tencent Q1 2026 PDF...")
    try:
        req = Request(
            TENCENT_PDF_URL,
            headers={"User-Agent": "AlphaPilot/1.0 (contact@alphapilot.dev)"},
        )
        with urlopen(req, timeout=120) as resp:
            content = resp.read()
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        sys.exit(1)
    print(f"  ✅ Downloaded {len(content):,} bytes")

    # 2. Save raw
    from knowledge.document_ingest import RAW_DIR
    file_id = uuid.uuid4().hex[:10]
    pdf_path = RAW_DIR / f"0700.HK_Q1_2026_{file_id}.pdf"
    pdf_path.write_bytes(content)
    print(f"  Saved to {pdf_path}")

    # 3. Parse and chunk
    print("\n[2/3] Parsing PDF and chunking...")
    from knowledge.pdf_parser import parse_and_chunk
    from knowledge.document_ingest import ingest_chunks

    metadata = {
        "doc_id": f"0700.HK_Q1_2026_{file_id}",
        "symbol": "0700.HK",
        "source": "HKEX",
        "doc_type": "earnings_call",
        "publish_date": "2026-05-13",
        "report_period": "Q1 2026",
        "language": "zh",
    }

    chunks = parse_and_chunk(str(pdf_path), metadata, doc_type="earnings_call")
    print(f"  Produced {len(chunks)} chunks")

    sec_ctr = Counter(c.get("section", "?") for c in chunks)
    print("  Sections:")
    for s, n in sec_ctr.most_common(15):
        print(f"    {n:3d}  {s}")

    # 4. Ingest (add directly to FAISS)
    print("\n[3/3] Adding to FAISS...")
    from rag.retriever import retriever
    from langchain_core.documents import Document

    vs = retriever.vectorstore
    docs_added = 0
    for c in chunks:
        doc = Document(
            page_content=c.get("content", ""),
            metadata={
                "_type": "document_chunk",
                "chunk_id": c.get("chunk_id", ""),
                "doc_id": metadata["doc_id"],
                "symbol": metadata["symbol"],
                "section": c.get("section", ""),
                "doc_type": metadata["doc_type"],
                "page": c.get("page", ""),
                "source": metadata["source"],
                "publish_date": metadata["publish_date"],
                "language": metadata["language"],
                "contains_table": c.get("contains_table", False),
            },
        )
        vs.add_documents([doc])
        retriever._known_doc_ids.add(c.get("chunk_id", ""))
        docs_added += 1

    print(f"  ✅ Added {docs_added} chunks to FAISS (in-memory)")

    # Save
    vs.save_local(str(Path("rag_data/faiss_index")))
    print(f"  ✅ FAISS saved")

    # Verify
    results = retriever.retrieve_doc_chunks("0700.HK", symbol="0700.HK", k=50)
    chunks_7 = [r for r in results if r.get("symbol", "").upper() == "0700.HK"]
    sec_ctr2 = Counter(c.get("section", "") or "(empty)" for c in chunks_7)

    print(f"\n{'='*60}")
    print(f"✅ 0700.HK re-ingest complete: {len(chunks_7)} chunks")
    if chunks_7:
        print("Sections:")
        for s, n in sec_ctr2.most_common(15):
            print(f"  {n:3d}  {s[:75]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
