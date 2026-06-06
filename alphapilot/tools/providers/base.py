from __future__ import annotations

from abc import ABC, abstractmethod

from schemas.evidence_packet import Fact


class DataProvider(ABC):
    name: str = ""
    priority: int = 0
    enabled: bool = True

    @abstractmethod
    def collect_market(self, symbol: str) -> list[Fact]:
        ...

    @abstractmethod
    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        ...

    @abstractmethod
    def collect_news(self, symbol: str) -> list[Fact]:
        ...

    def collect_filings(self, symbol: str) -> list[Fact]:
        return []

    @property
    def failure_count(self) -> int:
        return getattr(self, "_failure_count", 0)

    def record_failure(self) -> None:
        self._failure_count = getattr(self, "_failure_count", 0) + 1

    def record_success(self) -> None:
        self._failure_count = 0