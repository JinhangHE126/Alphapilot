from __future__ import annotations

import json
from datetime import date
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

_HKEX_USER_AGENT = "AlphaPilot/1.0"


def _hkex_request(url: str) -> Optional[dict]:
    req = Request(url, headers={
        "User-Agent": _HKEX_USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, Exception):
        return None


def fetch_hkex_announcements(stock_code: str, count: int = 5) -> list[dict]:
    code = stock_code.replace(".HK", "").lstrip("0") or "0"
    today = date.today().isoformat()

    url = (
        f"https://www1.hkexnews.hk/search/titlesearch.xhtml"
        f"?lang=en&category=0&market=SEHK&stockId={code}"
        f"&documentType=-1&from=2025-01-01&to={today}"
        f"&title=&titleOverride=&t1code=-2&t2Gcode=-2&t2code=-2"
        f"&rowRange={count}&sortDir=0&sortByOptions=DateTime"
    )

    try:
        req = Request(url, headers={
            "User-Agent": _HKEX_USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://www1.hkexnews.hk/",
        })
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    results = []
    items = data if isinstance(data, list) else []
    for item in items[:count]:
        entry = item if isinstance(item, dict) else {}
        title = ""

        for key in ("TITLE", "title", "Title", "STOCK_NAME"):
            raw = entry.get(key, "")
            if isinstance(raw, str):
                title = raw
                break
            if isinstance(raw, dict):
                title = raw.get("zh-Hant", raw.get("en", ""))
                break

        file_link = entry.get("FILE_LINK", entry.get("FILELINK", ""))
        file_url = ""
        if isinstance(file_link, str) and file_link:
            file_url = "https://www1.hkexnews.hk" + file_link

        if title:
            results.append({
                "field": "hkex_announcement",
                "value": title,
                "unit": "text",
                "period": "latest",
                "source": "HKEX",
                "source_url": file_url or url,
                "as_of_date": today,
                "confidence": 0.90,
                "confidence_tier": "machine",
            })

    return results


def collect_hkex_facts(symbol: str) -> list[dict]:
    if not symbol.endswith(".HK"):
        return []
    return fetch_hkex_announcements(symbol)


__all__ = ["fetch_hkex_announcements", "collect_hkex_facts"]