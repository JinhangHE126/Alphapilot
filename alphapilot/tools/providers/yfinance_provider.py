from __future__ import annotations

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider
from tools.data_collector import (
    collect_market_facts as _collect_market_raw,
    collect_fundamental_facts as _collect_fundamental_raw,
    collect_news_facts as _collect_news_raw,
)


class YFinanceProvider(DataProvider):
    name = "yfinance"
    priority = 40

    def collect_market(self, symbol: str) -> list[Fact]:
        raw = _collect_market_raw(symbol)
        results = []
        for f in raw:
            try:
                results.append(Fact(**f))
            except Exception:
                pass
        return results

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        raw = _collect_fundamental_raw(symbol)
        results = []
        for f in raw:
            try:
                results.append(Fact(**f))
            except Exception:
                pass
        return results

    def collect_news(self, symbol: str) -> list[Fact]:
        raw = _collect_news_raw(symbol)
        results = []
        for f in raw:
            try:
                results.append(Fact(**f))
            except Exception:
                pass
        return results