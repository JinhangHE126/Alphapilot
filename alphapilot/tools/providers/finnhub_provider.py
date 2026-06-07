from __future__ import annotations

import os
import json
from datetime import date, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

_FINNHUB_BASE = "https://finnhub.io/api/v1"


class FinnhubProvider(DataProvider):
    name = "finnhub"
    priority = 70

    def __init__(self) -> None:
        self._api_key = os.getenv("FINNHUB_API_KEY", "")
        if not self._api_key:
            self.enabled = False

    def _get(self, path: str) -> dict | None:
        url = f"{_FINNHUB_BASE}{path}&token={self._api_key}" if "?" in path else f"{_FINNHUB_BASE}{path}?token={self._api_key}"
        req = Request(url)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, Exception):
            return None

    def collect_market(self, symbol: str) -> list[Fact]:
        return []

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        today = date.today().isoformat()
        facts = []

        profile = self._get(f"/stock/profile2?symbol={clean}")
        if profile and profile.get("marketCapitalization"):
            try:
                mcap_m = float(profile["marketCapitalization"])
                facts.append(Fact(
                    field="market_cap", value=mcap_m * 1_000_000,
                    unit="USD", period="latest", source="finnhub",
                    source_url=None, as_of_date=today,
                    confidence=0.90, confidence_tier="machine",
                ))
            except (ValueError, TypeError):
                pass

        metrics = self._get(f"/stock/metric?symbol={clean}")
        if metrics and metrics.get("metric"):
            m = metrics["metric"]
            pe = m.get("peBasicExclExtraTTM") or m.get("peTTM")
            if pe:
                try:
                    facts.append(Fact(
                        field="pe_ratio", value=round(float(pe), 2),
                        unit="ratio", period="latest", source="finnhub",
                        source_url=None, as_of_date=today,
                        confidence=0.85, confidence_tier="machine",
                    ))
                except (ValueError, TypeError):
                    pass

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()
        today_str = today.isoformat()

        data = self._get(f"/company-news?symbol={clean}&from={week_ago}&to={today_str}")
        if not data or not isinstance(data, list):
            return []

        facts = []
        for item in data[:5]:
            headline = item.get("headline", "")
            if not headline:
                continue
            published = date.fromtimestamp(item.get("datetime", 0)).isoformat() if item.get("datetime") else today_str
            facts.append(Fact(
                field="news_headline", value=headline,
                unit="text", period="latest",
                source=item.get("source", "finnhub_news"),
                source_url=item.get("url"),
                as_of_date=published,
                confidence=0.70, confidence_tier="llm_extracted",
            ))
        return facts