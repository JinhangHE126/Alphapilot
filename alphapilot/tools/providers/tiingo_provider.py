from __future__ import annotations

import os
import json
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import URLError

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

_TIINGO_BASE = "https://api.tiingo.com"


class TiingoProvider(DataProvider):
    name = "tiingo"
    priority = 75

    def __init__(self) -> None:
        self._api_key = os.getenv("TIINGO_API_KEY", "")
        if not self._api_key:
            self.enabled = False

    def _get(self, path: str) -> dict | list | None:
        url = f"{_TIINGO_BASE}{path}&token={self._api_key}" if "?" in path else f"{_TIINGO_BASE}{path}?token={self._api_key}"
        req = Request(url)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, Exception):
            return None

    def collect_market(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/tiingo/daily/{clean}")
        if not data:
            return []
        today = date.today().isoformat()
        facts = []
        if isinstance(data, list) and data:
            latest = data[-1]
            adj_close = latest.get("adjClose")
            if adj_close:
                facts.append(Fact(field="current_price", value=round(float(adj_close), 2),
                                  unit="USD", period="latest", source="tiingo",
                                  source_url=None, as_of_date=today,
                                  confidence=0.95, confidence_tier="machine"))
            volume = latest.get("volume")
            if volume:
                facts.append(Fact(field="avg_volume_20d", value=int(volume),
                                  unit="shares", period="latest", source="tiingo",
                                  source_url=None, as_of_date=today,
                                  confidence=0.90, confidence_tier="machine"))
        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/tiingo/fundamentals/{clean}")
        if not data or not isinstance(data, list) or not data:
            return []
        today = date.today().isoformat()
        latest = data[0]
        facts = []
        market_cap = latest.get("marketCap")
        if market_cap:
            facts.append(Fact(field="market_cap", value=float(market_cap),
                              unit="USD", period="latest", source="tiingo",
                              source_url=None, as_of_date=today,
                              confidence=0.90, confidence_tier="machine"))
        pe = latest.get("peRatio")
        if pe:
            facts.append(Fact(field="pe_ratio", value=float(pe),
                              unit="ratio", period="latest", source="tiingo",
                              source_url=None, as_of_date=today,
                              confidence=0.85, confidence_tier="machine"))
        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/tiingo/news?tickers={clean}&limit=5")
        if not data or not isinstance(data, list):
            return []
        today = date.today().isoformat()
        facts = []
        for item in data[:5]:
            title = item.get("title", "")
            if not title:
                continue
            facts.append(Fact(
                field="news_headline", value=title,
                unit="text", period="latest",
                source=item.get("source", "tiingo_news"),
                source_url=item.get("url"),
                as_of_date=item.get("publishedDate", today)[:10],
                confidence=0.70, confidence_tier="llm_extracted",
            ))
        return facts