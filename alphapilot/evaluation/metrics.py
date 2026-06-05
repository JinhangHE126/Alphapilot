from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class EvalCase:
    case_id: str
    symbol: str
    question: str
    expected_output_levels: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    require_traceability: bool = True
    should_reject: bool = False


@dataclass
class EvalResult:
    case_id: str
    symbol: str
    question: str
    hallucination_count: int = 0
    facts_traceable: int = 0
    total_conclusions: int = 0
    output_level: str = ""
    expected_output_levels: list[str] = field(default_factory=list)
    output_level_match: bool = False
    should_reject: bool = False
    did_reject: bool = False
    cold_start_detected: bool = False
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

    @property
    def output_level_accuracy(self) -> float:
        if not self.expected_output_levels:
            return 1.0
        return 1.0 if self.output_level_match else 0.0

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "symbol": self.symbol,
            "question": self.question,
            "output_level": self.output_level,
            "expected_output_levels": self.expected_output_levels,
            "output_level_match": self.output_level_match,
            "hallucination_count": self.hallucination_count,
            "hallucination_rate": self.hallucination_rate,
            "facts_traceable": self.facts_traceable,
            "total_conclusions": self.total_conclusions,
            "should_reject": self.should_reject,
            "did_reject": self.did_reject,
            "reject_accuracy": self.reject_accuracy,
            "cold_start_detected": self.cold_start_detected,
            "notes": self.notes,
        }


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

    @property
    def cold_start_coverage(self) -> float:
        if not self.results:
            return 0.0
        cold_start_cases = [r for r in self.results if r.should_reject]
        if not cold_start_cases:
            return 1.0
        detected = sum(1 for r in cold_start_cases if r.cold_start_detected)
        return detected / len(cold_start_cases)

    @property
    def output_level_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.output_level_accuracy for r in self.results) / len(self.results)

    def summary(self) -> str:
        return (
            f"EvalSuite Summary:\n"
            f"  Results: {len(self.results)}\n"
            f"  Avg Hallucination Rate: {self.avg_hallucination_rate:.1%}\n"
            f"  Reject Accuracy: {self.reject_accuracy:.1%}\n"
            f"  Source Traceability: {self.source_traceability:.1%}\n"
            f"  Cold Start Coverage: {self.cold_start_coverage:.1%}\n"
            f"  Output Level Accuracy: {self.output_level_accuracy:.1%}"
        )

    def to_dict(self) -> dict:
        return {
            "summary": {
                "results": len(self.results),
                "avg_hallucination_rate": self.avg_hallucination_rate,
                "reject_accuracy": self.reject_accuracy,
                "source_traceability": self.source_traceability,
                "cold_start_coverage": self.cold_start_coverage,
                "output_level_accuracy": self.output_level_accuracy,
            },
            "results": [r.to_dict() for r in self.results],
        }


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

DEFAULT_EVAL_SET_PATH = Path(__file__).with_name("cold_start_eval_set.jsonl")


def load_eval_cases(path: str | Path = DEFAULT_EVAL_SET_PATH) -> list[EvalCase]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path_obj}")

    cases: list[EvalCase] = []
    with path_obj.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            payload = json.loads(line)
            case_id = payload.get("case_id") or f"case_{idx:03d}"
            should_reject = payload.get("should_reject", False)
        if isinstance(should_reject, str):
            should_reject = should_reject.lower() in ("true", "1", "yes")
        cases.append(
            EvalCase(
                case_id=case_id,
                symbol=payload["symbol"],
                question=payload["question"],
                expected_output_levels=payload.get("expected_output_levels", []),
                must_not_contain=payload.get("must_not_contain", []),
                require_traceability=bool(payload.get("require_traceability", True)),
                should_reject=bool(should_reject),
            )
            )
    return cases


__all__ = [
    "EvalCase",
    "EvalResult",
    "EvalSuite",
    "COLD_START_SYMBOLS",
    "COLD_START_QUESTIONS",
    "DEFAULT_EVAL_SET_PATH",
    "load_eval_cases",
]