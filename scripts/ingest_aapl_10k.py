#!/usr/bin/env python3
"""AAPL 10-K 获取并直接入库 — 绕开 heavy import chain，直接调 SEC API。"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, date
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "alphapilot"
sys.path.insert(0, str(PROJECT_ROOT))

_SEC_UA = "AlphaPilot/1.0 (contact@alphapilot.dev)"


def get_aapl_cik() -> str | None:
    """Resolve AAPL CIK via SEC company tickers JSON."""
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        req = Request(url, headers={"User-Agent": _SEC_UA})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    for _, v in data.items():
        if v.get("ticker", "").upper() == "AAPL":
            cik = str(v["cik_str"])
            return cik.zfill(10)
    return None


def get_latest_10k(cik: str) -> dict | None:
    """Get latest 10-K filing info from SEC submissions."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        req = Request(url, headers={"User-Agent": _SEC_UA})
        with urlopen(req, timeout=30) as resp:
            submissions = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠️ submissions fetch error: {e}")
        return None

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary = recent.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        return {
            "form": form,
            "accession": accessions[i].replace("-", ""),
            "filing_date": dates[i] if i < len(dates) else "",
            "primary_document": primary[i] if i < len(primary) else "",
        }
    return None


def download_10k(cik: str, filing: dict) -> bytes | None:
    """Download primary 10-K document."""
    cik_num = str(int(cik))
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_num}/"
        f"{filing['accession']}/{filing['primary_document']}"
    )
    print(f"  Downloading: {url}")
    try:
        req = Request(url, headers={"User-Agent": _SEC_UA})
        with urlopen(req, timeout=120) as resp:
            return resp.read()
    except Exception as e:
        print(f"  ⚠️ download error: {e}")
        return None


def main():
    print("=" * 60)
    print("AAPL 10-K Ingest (lightweight SEC direct)")
    print("=" * 60)

    # Step 1 — resolve CIK
    print("\n[1/5] Resolving AAPL CIK...")
    cik = get_aapl_cik()
    if not cik:
        print("  ❌ Could not resolve CIK for AAPL")
        sys.exit(1)
    print(f"  ✅ CIK={cik}")

    # Step 2 — get latest 10-K
    print("\n[2/5] Fetching latest 10-K filing info...")
    filing = get_latest_10k(cik)
    if not filing:
        print("  ❌ No 10-K found")
        sys.exit(1)
    print(f"  ✅ {filing['form']} filed {filing['filing_date']}")

    # Step 3 — download 10-K HTML
    print("\n[3/5] Downloading 10-K document...")
    content = download_10k(cik, filing)
    if not content:
        print("  ❌ Download failed")
        sys.exit(1)
    print(f"  ✅ Downloaded {len(content):,} bytes")

    # Step 4 — convert to text via markitdown
    print("\n[4/5] Converting HTML to text via markitdown...")
    from knowledge.document_ingest import RAW_DIR
    file_id = uuid.uuid4().hex[:10]
    dest = RAW_DIR / f"AAPL_10K_{file_id}.htm"
    dest.write_bytes(content)
    print(f"  Saved to {dest}")

    # SEC 10-K uses iXBRL HTML — strip XBRL/XML/HTML tags, keep readable text
    import re as _re
    html = dest.read_text(encoding="utf-8", errors="ignore")

    # Strip XBRL/ix tags
    html = _re.sub(r"<ix:[^>]+>", "", html)
    html = _re.sub(r"</ix:[^>]+>", "", html)
    # Strip XML declaration and comments
    html = _re.sub(r"<\?xml[^?]*\?>", "", html, flags=_re.IGNORECASE)
    html = _re.sub(r"<!--.*?-->", "", html, flags=_re.DOTALL)
    # Strip style/script blocks
    html = _re.sub(
        r"<(style|script)[^>]*>.*?</\1>",
        "",
        html,
        flags=_re.DOTALL | _re.IGNORECASE,
    )
    # Strip remaining HTML tags
    text = _re.sub(r"<[^>]+>", "\n", html)
    # Decode entities and clean whitespace
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&#8217;", "'")
    text = text.replace("&#8220;", '"')
    text = text.replace("&#8221;", '"')
    text = text.replace("&#160;", " ")
    text = _re.sub(r"\n{3,}", "\n\n", text)
    text = _re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    # Trim leading XBRL metadata (first ~20KB is data islands)
    lines = text.split("\n")
    first_real = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not _re.match(
            r"^(false|true|\d{4}|P\dY|http://|[A-Z]{2,}:\d|iso4217|xbrli:)", stripped
        ):
            first_real = i
            break
    text = "\n".join(lines[first_real:]).strip()

    print(f"  Cleaned text: {len(text):,} chars")

    # Step 5 — chunk and ingest
    print("\n[5/5] Chunking and ingesting...")

    # Convert SEC 10-K headings to markdown format for section detection
    # e.g., "Item 1. Business" → "## Item 1. Business"
    # e.g., "Part I" → "# Part I"
    text = _re.sub(
        r"(?m)^(Part [IVX]+\b.*)$",
        r"# \1",
        text,
    )
    text = _re.sub(
        r"(?m)^(Item\s+\d+[A-Z]?\.\s+.*)$",
        r"## \1",
        text,
    )
    # Also mark ALL-CAPS sub-headings
    text = _re.sub(
        r"(?m)^([A-Z][A-Z\s\-/,]{20,70})$",
        r"### \1",
        text,
    )
    print(f"  After heading inference: {len(text):,} chars")
    metadata = {
        "doc_id": f"AAPL_10-K_{file_id}",
        "symbol": "AAPL",
        "source": "SEC",
        "doc_type": "annual_report",
        "publish_date": filing.get("filing_date") or date.today().isoformat(),
        "report_period": "10-K",
        "language": "en",
    }

    from knowledge.document_chunker import chunk_document
    from knowledge.document_ingest import ingest_chunks

    chunks = chunk_document("annual_report", text, metadata)
    if not chunks:
        print("  ❌ No chunks produced")
        sys.exit(1)
    print(f"  Produced {len(chunks)} chunks")

    written = ingest_chunks(chunks)
    print(f"  ✅ Ingested {written} chunks into FAISS")

    # Verify
    from rag.retriever import retriever
    from collections import Counter

    results = retriever.retrieve_doc_chunks("AAPL", symbol="AAPL", k=50)
    aapl_chunks = [r for r in results if r.get("symbol", "").upper() == "AAPL"]
    print(f"\n  ✅ AAPL chunks in FAISS: {len(aapl_chunks)}")

    if aapl_chunks:
        sec_ctr = Counter(c.get("section", "") or "(empty)" for c in aapl_chunks)
        dt_ctr = Counter(c.get("doc_type", "") or "(none)" for c in aapl_chunks)
        print("  Sections:")
        for s, n in sec_ctr.most_common(10):
            print(f"    {n:4d}  {s[:75]}")
        print("  Doc types:")
        for d, n in dt_ctr.most_common():
            print(f"    {n:4d}  {d}")

    print("\n" + "=" * 60)
    print("✅ AAPL 10-K ingest complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
