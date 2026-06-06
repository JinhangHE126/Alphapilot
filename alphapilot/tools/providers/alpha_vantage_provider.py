from __future__ import annotations

import os
import json
import time
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import URLError

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider


class AlphaVantageProvider(DataProvider):
    name = "alpha_vantage"
    priority = 60

    def __init__(self) -> None:
        self._api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
        self._base = "https://www.alphavantage.co/query"
        self._last_call: float = 0
        self._min_interval: float = 12.0
        self._call_count: int = 0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()
        self._call_count += 1

    def _get(self, params: dict) -> dict | None:
        self._throttle()
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self._base}?{qs}"
        req = Request(url)
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if "Note" in data or "Information" in data:
                msg = data.get("Note", data.get("Information", ""))
                print(f"   ⚠️ Alpha Vantage rate limit: {msg[:100]}")
                return None
            return data
        except (URLError, json.JSONDecodeError, Exception) as e:
            print(f"   ⚠️ Alpha Vantage failed: {e}")
            return None

    def collect_market(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get({
            "function": "GLOBAL_QUOTE",
            "symbol": clean,
            "apikey": self._api_key,
        })
        if not data:
            return []
        quote = data.get("Global Quote", {})
        if not quote:
            return []
        today = date.today().isoformat()
        facts = []
        price = quote.get("05. price")
        if price:
            try:
                facts.append(Fact(
                    field="current_price",
                    value=round(float(price), 2),
                    unit="USD",
                    period="latest",
                    source="alpha_vantage",
                    source_url=None,
                    as_of_date=today,
                    confidence=0.90,
                    confidence_tier="machine",
                ))
            except (ValueError, TypeError):
                pass
        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get({
            "function": "OVERVIEW",
            "symbol": clean,
            "apikey": self._api_key,
        })
        if not data or "Symbol" not in data:
            return []
        today = date.today().isoformat()
        facts = []

        field_map = {
            "MarketCapitalization": ("market_cap", "USD"),
            "PERatio": ("pe_ratio", "ratio"),
            "EPS": ("eps", "USD"),
            "RevenueTTM": ("revenue_ttm", "USD"),
            "ProfitMargin": ("profit_margin", "percent"),
            "Sector": ("sector", "text"),
            "Industry": ("industry", "text"),
            "Name": ("company_name", "text"),
        }

        for av_field, (internal_field, unit) in field_map.items():
            val = data.get(av_field)
            if val is None or val == "None" or val == "":
                continue
            try:
                if unit in ("USD", "percent", "ratio"):
                    parsed = float(val)
                else:
                    parsed = str(val)
            except (ValueError, TypeError):
                continue

            facts.append(Fact(
                field=internal_field,
                value=parsed,
                unit=unit,
                period="latest",
                source="alpha_vantage",
                source_url=None,
                as_of_date=today,
                confidence=0.85,
                confidence_tier="machine",
            ))

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        return []