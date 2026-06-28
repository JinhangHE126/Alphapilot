#!/usr/bin/env python3
"""Remove old AAPL bad chunks from FAISS and re-ingest with proper 10-K text.

Strategy: Extract all non-AAPL docs from existing FAISS, add new properly-chunked 
AAPL docs, rebuild FAISS index, save.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import date
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

RAG_INDEX_PATH = Path("rag_data/faiss_index")
_SEC_UA = "AlphaPilot/1.0 (contact@alphapilot.dev)"


# ── SEC 10-K download ──────────────────────────────────────────

def _sec_json(url: str) -> dict | None:
    from urllib.request import Request, urlopen
    try:
        req = Request(url, headers={"User-Agent": _SEC_UA})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_aapl_cik() -> str | None:
    data = _sec_json("https://www.sec.gov/files/company_tickers.json")
    if not data:
        return None
    for v in data.values():
        if v.get("ticker", "").upper() == "AAPL":
            return str(v["cik_str"]).zfill(10)
    return None


def get_latest_10k(cik: str) -> dict | None:
    submissions = _sec_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if not submissions:
        return None
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary = recent.get("primaryDocument", [])
    for i, form in enumerate(forms):
        if form == "10-K":
            return {
                "accession": accessions[i].replace("-", ""),
                "filing_date": dates[i] if i < len(dates) else "",
                "primary_document": primary[i] if i < len(primary) else "",
            }
    return None


def download_10k(cik: str, filing: dict) -> bytes | None:
    from urllib.request import Request, urlopen
    cik_num = str(int(cik))
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_num}/"
        f"{filing['accession']}/{filing['primary_document']}"
    )
    try:
        req = Request(url, headers={"User-Agent": _SEC_UA})
        with urlopen(req, timeout=120) as resp:
            return resp.read()
    except Exception as e:
        print(f"  ⚠️ download error: {e}")
        return None


def clean_10k_html(html: str) -> str:
    """Strip iXBRL/HTML → readable text with markdown headings."""
    # Strip XBRL/ix tags
    html = re.sub(r"<ix:[^>]+>", "", html)
    html = re.sub(r"</ix:[^>]+>", "", html)
    html = re.sub(r"<\?xml[^?]*\?>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(
        r"<(style|script)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "\n", html)
    for e, c in [
        ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&#8217;", "'"), ("&#8220;", '"'), ("&#8221;", '"'), ("&#160;", " "),
        ("&#8226;", "-"), ("&#8212;", "--"),
    ]:
        text = text.replace(e, c)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    # Trim XBRL metadata header
    lines = text.split("\n")
    first_real = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not re.match(r"^(false|true|\d{4}$|P\dY|http://|[A-Z]{2,}:\d|iso4217|xbrli:)", s):
            first_real = i
            break
    text = "\n".join(lines[first_real:]).strip()

    # Convert SEC headings → markdown
    text = re.sub(r"(?m)^(PART\s+[IVX]+.*)$", r"# \1", text)
    text = re.sub(r"(?m)^(Part\s+[IVX]+.*)$", r"# \1", text)
    text = re.sub(r"(?m)^(Item\s+(\d+[A-Z]?)\.?\s+.*)$", r"## \1", text)
    text = re.sub(
        r"(?m)^([A-Z][A-Z\s\-/,&]{25,80})$",
        lambda m: f"### {m.group(1)}" if not m.group(1).startswith("#") else m.group(1),
        text,
    )
    return text


def main():
    print("=" * 60)
    print("AAPL 10-K — rebuild FAISS with clean chunks")
    print("=" * 60)

    # ── 1. Download 10-K ──
    print("\n[1/5] Downloading AAPL 10-K...")
    cik = get_aapl_cik()
    filing = get_latest_10k(cik)
    content = download_10k(cik, filing)
    html = content.decode("utf-8", errors="ignore")
    text = clean_10k_html(html)
    print(f"  Filed: {filing['filing_date']}  |  Clean text: {len(text):,} chars")

    # ── 2. Chunk the cleaned text ──
    print("\n[2/5] Chunking 10-K text...")
    from knowledge.document_chunker import chunk_document

    file_id = uuid.uuid4().hex[:10]
    metadata = {
        "doc_id": f"AAPL_10-K_{file_id}",
        "symbol": "AAPL",
        "source": "SEC",
        "doc_type": "annual_report",
        "publish_date": filing.get("filing_date") or date.today().isoformat(),
        "report_period": "10-K",
        "language": "en",
    }
    new_chunks = chunk_document("annual_report", text, metadata)
    print(f"  Produced {len(new_chunks)} chunks")
    sec_ctr = Counter(c.get("section", "?") for c in new_chunks)
    print("  Sections:")
    for s, n in sec_ctr.most_common(20):
        print(f"    {n:3d}  {s}")

    # ── 3. Load existing FAISS, extract non-AAPL docs ──
    print("\n[3/5] Extracting non-AAPL docs from existing FAISS...")
    from rag.retriever import retriever
    from langchain_core.documents import Document

    vs = retriever.vectorstore
    old_docs: list[Document] = []
    aapl_count = 0
    for doc in vs.docstore._dict.values():
        meta = doc.metadata or {}
        if meta.get("symbol", "").upper() == "AAPL":
            aapl_count += 1
        else:
            old_docs.append(doc)
    print(f"  Non-AAPL docs kept: {len(old_docs)}  |  AAPL removed: {aapl_count}")

    # ── 4. Build new FAISS index ──
    print("\n[4/5] Building new FAISS index...")
    from langchain_community.vectorstores.faiss import FAISS

    # Build docs list: old non-AAPL + new AAPL chunks
    all_docs = list(old_docs)
    for c in new_chunks:
        all_docs.append(Document(
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
        ))

    # Build new FAISS from texts
    texts = [d.page_content for d in all_docs]
    metadatas = [d.metadata for d in all_docs]
    new_vs = FAISS.from_texts(texts, retriever.embedding_model, metadatas=metadatas)
    print(f"  New index: {new_vs.index.ntotal} vectors")

    # ── 5. Save ──
    print("\n[5/5] Saving new FAISS index...")
    import shutil
    bak = RAG_INDEX_PATH.with_suffix(".faiss_index.bak")
    if RAG_INDEX_PATH.exists():
        shutil.rmtree(str(RAG_INDEX_PATH), ignore_errors=True)
    new_vs.save_local(str(RAG_INDEX_PATH))
    print(f"  ✅ Saved to {RAG_INDEX_PATH}")

    # Clear old retriever state and reload
    retriever.vectorstore = new_vs
    retriever._known_doc_ids = set()
    retriever._scan_existing_doc_ids()

    # ── Verify ──
    print(f"\n{'='*60}")
    print("✅ AAPL 10-K rebuild complete!")
    
    results = retriever.retrieve_doc_chunks("AAPL", symbol="AAPL", k=50)
    aapl_chunks = [r for r in results if r.get("symbol", "").upper() == "AAPL"]
    sec_ctr2 = Counter(c.get("section", "") or "(empty)" for c in aapl_chunks)
    dt_ctr2 = Counter(c.get("doc_type", "") or "(none)" for c in aapl_chunks)
    
    print(f"\nAAPL chunks: {len(aapl_chunks)}")
    print("Sections:")
    for s, n in sec_ctr2.most_common(20):
        print(f"  {n:3d}  {s[:80]}")
    print("Doc types:")
    for d, n in dt_ctr2.most_common():
        print(f"  {n:3d}  {d}")
    
    # Also verify 0700.HK still intact
    results_7 = retriever.retrieve_doc_chunks("0700.HK", symbol="0700.HK", k=50)
    chunks_7 = [r for r in results_7 if r.get("symbol", "").upper() == "0700.HK"]
    print(f"\n0700.HK chunks still intact: {len(chunks_7)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
