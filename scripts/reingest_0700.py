#!/usr/bin/env python3
"""Re-ingest 0700.HK (Tencent Q1 2026) PDF — rebuild FAISS without old 0700 chunks."""
from __future__ import annotations

import shutil
import sys
import uuid
from datetime import date
from pathlib import Path
from collections import Counter
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

RAG_INDEX_PATH = Path("rag_data/faiss_index")

TENCENT_PDF_URL = (
    "https://static.www.tencent.com/uploads/2026/05/13/"
    "47382ae415a209fd161bc19a1f9b3704.pdf"
)


def _is_0700_symbol(symbol: str) -> bool:
    s = (symbol or "").upper().replace(".HK", "")
    return s in {"0700", "700"}


def main():
    print("=" * 60)
    print("0700.HK — Re-ingest Tencent Q1 2026 PDF (clean rebuild)")
    print("=" * 60)

    # 1. Download PDF
    print("\n[1/4] Downloading Tencent Q1 2026 PDF...")
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

    # 2. Save raw + parse
    from knowledge.document_ingest import RAW_DIR
    from knowledge.pdf_parser import parse_and_chunk
    from langchain_core.documents import Document
    from langchain_community.vectorstores.faiss import FAISS
    from rag.retriever import retriever

    file_id = uuid.uuid4().hex[:10]
    pdf_path = RAW_DIR / f"0700.HK_Q1_2026_{file_id}.pdf"
    pdf_path.write_bytes(content)
    print(f"  Saved to {pdf_path}")

    print("\n[2/4] Parsing PDF and chunking...")
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

    # 3. Rebuild FAISS: drop old 0700.HK, keep everything else
    print("\n[3/4] Rebuilding FAISS (remove old 0700.HK chunks)...")
    vs = retriever.vectorstore
    kept_docs: list[Document] = []
    removed = 0
    for doc in vs.docstore._dict.values():
        meta = doc.metadata or {}
        if _is_0700_symbol(meta.get("symbol", "")):
            removed += 1
        else:
            kept_docs.append(doc)
    print(f"  Non-0700 docs kept: {len(kept_docs)}  |  0700.HK removed: {removed}")

    all_docs = list(kept_docs)
    for c in chunks:
        all_docs.append(
            Document(
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
        )

    texts = [d.page_content for d in all_docs]
    metadatas = [d.metadata for d in all_docs]
    new_vs = FAISS.from_texts(texts, retriever.embedding_model, metadatas=metadatas)
    print(f"  New index: {new_vs.index.ntotal} vectors")

    print("\n[4/4] Saving FAISS index...")
    if RAG_INDEX_PATH.exists():
        shutil.rmtree(str(RAG_INDEX_PATH), ignore_errors=True)
    new_vs.save_local(str(RAG_INDEX_PATH))
    retriever.vectorstore = new_vs
    retriever._known_doc_ids = set()
    retriever._scan_existing_doc_ids()
    print(f"  ✅ Saved to {RAG_INDEX_PATH}")

    # Verify
    results = retriever.retrieve_doc_chunks("0700.HK", symbol="0700.HK", k=50)
    chunks_7 = [r for r in results if _is_0700_symbol(r.get("symbol", ""))]
    sec_ctr2 = Counter(c.get("section", "") or "(empty)" for c in chunks_7)

    print(f"\n{'='*60}")
    print(f"✅ 0700.HK re-ingest complete: {len(chunks_7)} chunks in index")
    if chunks_7:
        print("Sections:")
        for s, n in sec_ctr2.most_common(15):
            print(f"  {n:3d}  {s[:75]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
