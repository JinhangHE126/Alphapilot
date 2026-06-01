from __future__ import annotations

import json
from datetime import date
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

_SEC_USER_AGENT = "AlphaPilot/1.0 (contact@alphapilot.dev)"


def _sec_request(url: str) -> Optional[dict]:
    req = Request(url, headers={"User-Agent": _SEC_USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, Exception):
        return None


def fetch_sec_company_facts(cik: str) -> dict:
    data = _sec_request(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )
    if not data:
        return {"status": "error", "message": "SEC EDGAR API unavailable"}

    facts = data.get("facts", {}).get("us-gaap", {})
    today = date.today().isoformat()

    extracted = []
    mappings = {
        "Revenues": "revenue",
        "EarningsPerShareBasic": "eps",
        "EarningsPerShareDiluted": "eps_diluted",
        "GrossProfit": "gross_profit",
        "NetIncomeLoss": "net_income",
        "OperatingIncomeLoss": "operating_income",
        "Assets": "total_assets",
        "Liabilities": "total_liabilities",
        "StockholdersEquity": "stockholders_equity",
    }

    for sec_field, internal_field in mappings.items():
        if sec_field not in facts:
            continue
        units = facts[sec_field].get("units", {})
        usd_entries = units.get("USD", [])
        if not usd_entries:
            usd_entries = units.get("shares", [])
        if not usd_entries:
            continue

        latest = max(
            (e for e in usd_entries if e.get("form") in ("10-K", "10-Q", "8-K")),
            key=lambda e: e.get("end", ""),
            default=usd_entries[-1],
        )
        val = latest.get("val")
        if val is None:
            continue

        extracted.append({
            "field": internal_field,
            "value": val,
            "unit": "USD",
            "period": latest.get("fy", ""),
            "source": "SEC_EDGAR",
            "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "as_of_date": str(latest.get("filed", today)),
            "confidence": 0.95,
            "confidence_tier": "machine",
        })

    return {
        "status": "ok",
        "entity_name": data.get("entityName", ""),
        "cik": str(data.get("cik", cik)),
        "facts": extracted,
    }


def resolve_cik(ticker: str) -> Optional[str]:
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        req = Request(url, headers={"User-Agent": _SEC_USER_AGENT})
        with urlopen(req, timeout=10) as resp:
            mapping = json.loads(resp.read().decode())
        ticker_upper = ticker.upper().replace(".", "")
        for entry in mapping.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


def collect_sec_facts(symbol: str) -> list[dict]:
    clean = symbol.replace(".HK", "").replace(".L", "").replace(".SZ", "").replace(".SS", "")
    cik = resolve_cik(clean)
    if not cik:
        return []
    result = fetch_sec_company_facts(cik)
    return result.get("facts", [])


__all__ = [
    "fetch_sec_company_facts",
    "resolve_cik",
    "collect_sec_facts",
]