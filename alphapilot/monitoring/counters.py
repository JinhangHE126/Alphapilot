from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class AnalysisMetrics:
    total_requests: int = 0
    cold_start_count: int = 0
    insufficient_evidence_count: int = 0
    data_summary_only_count: int = 0
    limited_analysis_count: int = 0
    full_analysis_count: int = 0
    guard_pass_count: int = 0
    guard_fail_count: int = 0
    symbol_mismatch_count: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    field_missing_counts: dict[str, int] = field(default_factory=dict)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, evidence_packet: dict | None, guard_valid: bool,
               symbol_mismatch: bool, token_count: int = 0, duration_ms: int = 0) -> None:
        with self._lock:
            self.total_requests += 1
            self.total_tokens += token_count
            self.total_duration_ms += duration_ms

            if symbol_mismatch:
                self.symbol_mismatch_count += 1

            if guard_valid:
                self.guard_pass_count += 1
            else:
                self.guard_fail_count += 1

            if not evidence_packet:
                return

            is_cold = evidence_packet.get("is_cold_start", False)
            if is_cold:
                self.cold_start_count += 1

            level = evidence_packet.get("allowed_output_level", "")
            if level == "insufficient_evidence":
                self.insufficient_evidence_count += 1
            elif level == "data_summary_only":
                self.data_summary_only_count += 1
            elif level == "limited_analysis":
                self.limited_analysis_count += 1
            elif level == "full_analysis":
                self.full_analysis_count += 1

            for m in evidence_packet.get("missing_fields", []):
                field_name = m.get("field", "") if isinstance(m, dict) else ""
                if field_name:
                    self.field_missing_counts[field_name] = (
                        self.field_missing_counts.get(field_name, 0) + 1
                    )

    def snapshot(self) -> dict:
        with self._lock:
            total = max(self.total_requests, 1)
            return {
                "total_requests": self.total_requests,
                "cold_start_pct": round(self.cold_start_count / total * 100, 1),
                "insufficient_evidence_pct": round(self.insufficient_evidence_count / total * 100, 1),
                "limited_analysis_pct": round(self.limited_analysis_count / total * 100, 1),
                "full_analysis_pct": round(self.full_analysis_count / total * 100, 1),
                "guard_pass_pct": round(self.guard_pass_count / total * 100, 1),
                "symbol_mismatch_count": self.symbol_mismatch_count,
                "avg_tokens_per_request": self.total_tokens // total,
                "avg_duration_ms": self.total_duration_ms // total,
                "top_missing_fields": sorted(
                    self.field_missing_counts.items(),
                    key=lambda x: x[1], reverse=True,
                )[:5],
            }


_global_metrics = AnalysisMetrics()


def get_metrics() -> AnalysisMetrics:
    return _global_metrics


__all__ = ["AnalysisMetrics", "get_metrics"]