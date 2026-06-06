from __future__ import annotations

import os
import json
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import URLError

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

_POLYGON_BASE = "https://api.polygon.io"


class PolygonProvider(DataProvider):
    name = "polygon"
    priority = 80

    def __init__(self) -> None:
        self._api_key = os.getenv("POLYGON_API_KEY", "")
        if not self._api_key:
            self.enabled = False

    def _get(self, path: str) -> dict | None:
        url = f"{_POLYGON_BASE}{path}&apiKey={self._api_key}" if "?" in path else f"{_POLYGON_BASE}{path}?apiKey={self._api_key}"
        req = Request(url)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, Exception):
            return None

    def collect_market(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/v2/aggs/ticker/{clean}/prev")
        if not data or data.get("status") != "OK":
            return []
        today = date.today().isoformat()
        results = data.get("results", [])
        if not results:
            return []
        r = results[0]
        facts = []
        c = r.get("c")
        if c:
            facts.append(Fact(field="current_price", value=round(float(c), 2),
                              unit="USD", period="latest", source="polygon",
                              source_url=None, as_of_date=today,
                              confidence=0.95, confidence_tier="machine"))
        v = r.get("v")
        if v:
            facts.append(Fact(field="avg_volume_20d", value=int(v),
                              unit="shares", period="latest", source="polygon",
                              source_url=None, as_of_date=today,
                              confidence=0.90, confidence_tier="machine"))
        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/v3/reference/tickers/{clean}")
        if not data or data.get("status") != "OK":
            return []
        today = date.today().isoformat()
        r = data.get("results", {})
        facts = []
        market_cap = r.get("market_cap")
        if market_cap:
            facts.append(Fact(field="market_cap", value=float(market_cap),
                              unit="USD", period="latest", source="polygon",
                              source_url=None, as_of_date=today,
                              confidence=0.90, confidence_tier="machine"))
        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        data = self._get(f"/v2/reference/news?ticker={clean}&limit=5")
        if not data or data.get("status") != "OK":
            return []
        today = date.today().isoformat()
        facts = []
        for item in data.get("results", [])[:5]:
            title = item.get("title", "")
            if not title:
                continue
            facts.append(Fact(
                field="news_headline", value=title,
                unit="text", period="latest",
                source=item.get("publisher", {}).get("name", "polygon_news"),
                source_url=item.get("article_url"),
                as_of_date=item.get("published_utc", today)[:10],
                confidence=0.70, confidence_tier="llm_extracted",
            ))
        return facts