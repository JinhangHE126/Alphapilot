"""SEC EDGAR — 10-K / 10-Q 申报文件自动抓取与入库。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import aiohttp

from knowledge.document_ingest import ingest_file, save_raw_bytes
from tools.sec_edgar_tools import resolve_cik

_SEC_UA = "AlphaPilot/1.0 (contact@alphapilot.dev)"
_FILING_FORMS = {"10-K", "10-Q"}


async def _sec_get_json(session: aiohttp.ClientSession, url: str) -> dict | None:
    headers = {"User-Agent": _SEC_UA, "Accept": "application/json"}
    try:
        async with session.get(url, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None


def _recent_filings(submissions: dict, limit: int) -> list[dict[str, str]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary = recent.get("primaryDocument", [])
    out: list[dict[str, str]] = []
    for i, form in enumerate(forms):
        if form not in _FILING_FORMS:
            continue
        if i >= len(accessions) or i >= len(primary):
            continue
        out.append(
            {
                "form": form,
                "accession": accessions[i].replace("-", ""),
                "filing_date": dates[i] if i < len(dates) else "",
                "primary_document": primary[i],
            }
        )
        if len(out) >= limit:
            break
    return out


async def fetch_sec_filings(
    symbol: str,
    *,
    max_docs: int = 3,
) -> dict[str, Any]:
    """下载 SEC 申报主文档（HTML/HTM）并入库。"""
    clean = (
        symbol.replace(".HK", "")
        .replace(".L", "")
        .replace(".SZ", "")
        .replace(".SS", "")
        .upper()
    )
    cik = resolve_cik(clean)
    if not cik:
        return {"symbol": symbol, "ingested": 0, "reason": "cik_not_found"}

    cik_num = str(int(cik))
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    ingested = 0
    skipped = 0
    errors: list[str] = []

    async with aiohttp.ClientSession(trust_env=True) as session:
        submissions = await _sec_get_json(session, submissions_url)
        if not submissions:
            return {"symbol": symbol, "ingested": 0, "errors": ["submissions_unavailable"]}

        filings = _recent_filings(submissions, max_docs * 2)
        for filing in filings[:max_docs]:
            accession = filing["accession"]
            primary = filing["primary_document"]
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_num}/"
                f"{accession}/{primary}"
            )
            file_id = uuid.uuid4().hex[:10]
            doc_type = "annual_report" if filing["form"] == "10-K" else "earnings_call"
            doc_id = f"{clean}_{filing['form']}_{file_id}"
            metadata = {
                "doc_id": doc_id,
                "symbol": clean,
                "source": "SEC",
                "doc_type": doc_type,
                "publish_date": filing.get("filing_date") or datetime.utcnow().date().isoformat(),
                "report_period": filing.get("form", ""),
                "language": "en",
            }
            ext = ".htm" if primary.lower().endswith((".htm", ".html")) else ".txt"
            try:
                headers = {"User-Agent": _SEC_UA}
                async with session.get(doc_url, headers=headers, timeout=60) as resp:
                    if resp.status != 200:
                        skipped += 1
                        continue
                    content = await resp.read()
                path = save_raw_bytes(clean, "sec", ext, content)
                written = ingest_file(path, metadata, doc_type=doc_type)
                if written:
                    ingested += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"{filing['form']} {filing.get('filing_date')}: {exc}")

    return {"symbol": symbol, "ingested": ingested, "skipped": skipped, "errors": errors}
