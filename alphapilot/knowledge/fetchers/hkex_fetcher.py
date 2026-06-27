"""HKEX 披露易 — 年报/公告 PDF 自动抓取与入库。"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime
from html import unescape
from typing import Any
from urllib.request import Request, urlopen

import aiohttp

from config.proxy import get_requests_proxies
from knowledge.document_ingest import ingest_file, save_raw_bytes

_HKEX_UA = "Mozilla/5.0 (compatible; AlphaPilot/1.0)"
_ACTIVE_STOCK_URLS = (
    "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_e.json",
    "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json",
    "https://www1.hkexnews.hk/ncms/script/eds/inactivestock_sehk_e.json",
    "https://www1.hkexnews.hk/ncms/script/eds/inactivestock_sehk_c.json",
)
_ANNUAL_KEYWORDS = re.compile(
    r"annual\s*report|年报|年報|annual\s*results",
    re.IGNORECASE,
)
_PDF_URL_DATE = re.compile(r"/sehk/(\d{4})/(\d{2})(\d{2})/")


def _hkex_display_code(symbol: str) -> str:
    """0700.HK → 00700（披露易 5 位代码）。"""
    raw = symbol.upper().replace(".HK", "").strip()
    if not raw.isdigit():
        return raw
    return raw.zfill(5)


def _clean_html_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _publish_date_from_url(url: str) -> str:
    m = _PDF_URL_DATE.search(url)
    if not m:
        return ""
    y, mo, d = m.group(1), m.group(2), m.group(3)
    return f"{y}-{mo}-{d}"


def _load_stock_id_map() -> dict[str, int]:
    mapping: dict[str, int] = {}
    headers = {"User-Agent": _HKEX_UA}
    active_urls = _ACTIVE_STOCK_URLS[:2]
    inactive_urls = _ACTIVE_STOCK_URLS[2:]

    def _ingest(url: str) -> None:
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode())
        except Exception:
            return
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            code = str(item.get("c", "")).strip()
            stock_id = item.get("i")
            if code and stock_id is not None:
                mapping[code] = int(stock_id)

    for url in active_urls:
        _ingest(url)
    for url in inactive_urls:
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode())
        except Exception:
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            code = str(item.get("c", "")).strip()
            stock_id = item.get("i")
            if code and stock_id is not None and code not in mapping:
                mapping[code] = int(stock_id)
    return mapping


def resolve_hkex_stock_id(symbol: str) -> int | None:
    code = _hkex_display_code(symbol)
    stock_map = _load_stock_id_map()
    return stock_map.get(code)


def _build_search_url(
    stock_id: int,
    *,
    row_range: int = 20,
    annual_only: bool = True,
) -> str:
    today = date.today().isoformat()
    params = (
        f"lang=EN&category=0&market=SEHK&stockId={stock_id}"
        f"&documentType=-1&from=2018-01-01&to={today}"
        f"&titleOverride=&rowRange={row_range}&sortDir=0&sortByOptions=DateTime"
    )
    if annual_only:
        params += "&title=annual&t1code=40000&t2Gcode=-2&t2code=40100"
    else:
        params += "&title=&t1code=-2&t2Gcode=-2&t2code=-2"
    return f"https://www1.hkexnews.hk/search/titlesearch.xhtml?{params}"


def _parse_html_listings(html: str) -> list[dict[str, str]]:
    """从 titlesearch HTML 解析公告标题与 PDF 链接。"""
    rows = re.split(r"(?=Release Time:)", html)
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for row in rows[1:]:
        pdf_match = re.search(
            r'href="(/listedco/listconews/[^"]+\.pdf)"',
            row,
            re.IGNORECASE,
        )
        if not pdf_match:
            continue
        rel = pdf_match.group(1)
        file_url = f"https://www1.hkexnews.hk{rel}"
        if file_url in seen_urls:
            continue
        seen_urls.add(file_url)

        time_match = re.search(r"Release Time:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", row)
        doc_match = re.search(
            r"Document:\s*(.*?)(?:</td>|<a\s+href=|Release Time:|$)",
            row,
            re.IGNORECASE | re.DOTALL,
        )
        title = _clean_html_text(doc_match.group(1)) if doc_match else ""
        publish_date = ""
        if time_match:
            try:
                publish_date = datetime.strptime(time_match.group(1), "%d/%m/%Y").date().isoformat()
            except ValueError:
                publish_date = ""
        if not publish_date:
            publish_date = _publish_date_from_url(file_url)

        if title and file_url:
            results.append(
                {
                    "title": title,
                    "url": file_url,
                    "publish_date": publish_date,
                }
            )
    return results


async def _fetch_search_html(
    session: aiohttp.ClientSession,
    url: str,
    proxy: str | None,
) -> str:
    headers = {
        "User-Agent": _HKEX_UA,
        "Referer": "https://www1.hkexnews.hk/",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with session.get(url, headers=headers, proxy=proxy, timeout=60) as resp:
        resp.raise_for_status()
        return await resp.text(errors="ignore")


async def fetch_hkex_documents(
    symbol: str,
    *,
    max_docs: int = 3,
    annual_only: bool = True,
) -> dict[str, Any]:
    """
    抓取 HKEX 披露文件并入库。
    使用披露易股票列表解析 stockId，再从 titlesearch HTML 提取 PDF。
    """
    if not symbol.upper().endswith(".HK"):
        return {"symbol": symbol, "ingested": 0, "skipped": 0, "reason": "not_hk_symbol"}

    stock_id = resolve_hkex_stock_id(symbol)
    if stock_id is None:
        return {
            "symbol": symbol,
            "ingested": 0,
            "skipped": 0,
            "errors": [f"stockId not found for {_hkex_display_code(symbol)}"],
        }

    search_url = _build_search_url(
        stock_id,
        row_range=max(max_docs * 4, 20),
        annual_only=annual_only,
    )
    proxies = get_requests_proxies("fundamental")
    proxy = proxies.get("https") if proxies else None
    headers = {"User-Agent": _HKEX_UA, "Referer": "https://www1.hkexnews.hk/"}

    ingested = 0
    skipped = 0
    errors: list[str] = []

    async with aiohttp.ClientSession(trust_env=True) as session:
        try:
            html = await _fetch_search_html(session, search_url, proxy)
        except Exception as exc:
            return {"symbol": symbol, "ingested": 0, "errors": [str(exc)], "stock_id": stock_id}

        candidates = _parse_html_listings(html)
        if annual_only:
            filtered = [c for c in candidates if _ANNUAL_KEYWORDS.search(c["title"])]
            if filtered:
                candidates = filtered

        if not candidates:
            return {
                "symbol": symbol,
                "ingested": 0,
                "skipped": 0,
                "errors": ["no listings parsed from HKEX HTML"],
                "stock_id": stock_id,
            }

        for item in candidates[:max_docs]:
            file_id = uuid.uuid4().hex[:10]
            doc_id = f"{symbol.upper()}_annual_report_{file_id}"
            metadata = {
                "doc_id": doc_id,
                "symbol": symbol.upper(),
                "source": "HKEX",
                "doc_type": "annual_report",
                "publish_date": item.get("publish_date") or datetime.utcnow().date().isoformat(),
                "report_period": "",
                "language": "zh",
            }
            try:
                async with session.get(
                    item["url"],
                    headers=headers,
                    proxy=proxy,
                    timeout=120,
                ) as file_resp:
                    if file_resp.status != 200:
                        skipped += 1
                        errors.append(f"{item['title'][:40]}: HTTP {file_resp.status}")
                        continue
                    content = await file_resp.read()
                if not content.startswith(b"%PDF"):
                    skipped += 1
                    errors.append(f"{item['title'][:40]}: not a PDF")
                    continue
                path = save_raw_bytes(symbol, "hkex", ".pdf", content)
                written = ingest_file(path, metadata, doc_type="annual_report")
                if written:
                    ingested += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"{item.get('title', '')[:40]}: {exc}")

    return {
        "symbol": symbol,
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
        "stock_id": stock_id,
    }
