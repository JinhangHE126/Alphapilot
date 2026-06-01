from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    symbol: str
    question: str
    hallucination_count: int = 0
    facts_traceable: int = 0
    total_conclusions: int = 0
    should_reject: bool = False
    did_reject: bool = False
    notes: str = ""

    @property
    def hallucination_rate(self) -> float:
        return 1.0 if self.total_conclusions == 0 else (
            1.0 - self.facts_traceable / self.total_conclusions
        )

    @property
    def reject_accuracy(self) -> float:
        if not self.should_reject:
            return 1.0
        return 1.0 if self.did_reject else 0.0


@dataclass
class EvalSuite:
    results: list[EvalResult] = field(default_factory=list)

    def add(self, r: EvalResult) -> None:
        self.results.append(r)

    @property
    def avg_hallucination_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.hallucination_rate for r in self.results) / len(self.results)

    @property
    def reject_accuracy(self) -> float:
        relevant = [r for r in self.results if r.should_reject]
        if not relevant:
            return 1.0
        return sum(r.reject_accuracy for r in relevant) / len(relevant)

    @property
    def source_traceability(self) -> float:
        if not self.results:
            return 0.0
        total = sum(r.total_conclusions for r in self.results)
        traced = sum(r.facts_traceable for r in self.results)
        return traced / total if total > 0 else 0.0

    def summary(self) -> str:
        return (
            f"EvalSuite Summary:\n"
            f"  Results: {len(self.results)}\n"
            f"  Avg Hallucination Rate: {self.avg_hallucination_rate:.1%}\n"
            f"  Reject Accuracy: {self.reject_accuracy:.1%}\n"
            f"  Source Traceability: {self.source_traceability:.1%}"
        )


COLD_START_SYMBOLS: list[str] = [
    "0005.HK", "0700.HK", "9988.HK", "BABA", "JPM",
    "BAC", "WMT", "JNJ", "PG", "KO",
    "XOM", "CVX", "PFE", "MRK", "DIS",
    "NFLX", "ADBE", "CRM", "INTC", "AMD",
]

COLD_START_QUESTIONS: list[str] = [
    "请全面分析该股票并给出中线投资建议",
    "这家公司的基本面如何？营收和利润增长趋势是什么？",
    "当前估值水平合理吗？P/E、P/B 与同业对比如何？",
    "最近的新闻和市场情绪如何？有什么重大事件？",
    "这只股票的主要风险因素有哪些？",
]


__all__ = [
    "EvalResult",
    "EvalSuite",
    "COLD_START_SYMBOLS",
    "COLD_START_QUESTIONS",
]