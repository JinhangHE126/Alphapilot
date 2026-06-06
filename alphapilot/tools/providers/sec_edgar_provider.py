from __future__ import annotations

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider
from tools.sec_edgar_tools import collect_sec_facts as _collect_sec_raw


class SecEdgarProvider(DataProvider):
    name = "sec_edgar"
    priority = 100

    def collect_market(self, symbol: str) -> list[Fact]:
        return []

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        raw = _collect_sec_raw(symbol)
        results = []
        for f in raw:
            try:
                results.append(Fact(**f))
            except Exception:
                pass
        return results

    def collect_news(self, symbol: str) -> list[Fact]:
        return []

    def collect_filings(self, symbol: str) -> list[Fact]:
        return []