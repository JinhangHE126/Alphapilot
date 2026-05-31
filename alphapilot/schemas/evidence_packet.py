from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConfidenceTier(str, Enum):
    MACHINE = "machine"
    LLM_EXTRACTED = "llm_extracted"
    LLM_INFERRED = "llm_inferred"


class OutputLevel(str, Enum):
    FULL_ANALYSIS = "full_analysis"
    LIMITED_ANALYSIS = "limited_analysis"
    DATA_SUMMARY_ONLY = "data_summary_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Fact(BaseModel):
    field: str = Field(description="标准化字段名，枚举约束")
    value: float | str = Field(description="原始值，不应让 LLM 自行补全")
    unit: str = Field(description="USD、HKD、percent、shares、ratio 等")
    period: str = Field(description="latest、FY2025、Q1_2026、TTM 等")
    source: str = Field(description="枚举值，不允许空来源")
    source_url: Optional[str] = Field(default=None, description="官方文件、新闻或网页链接")
    as_of_date: str = Field(description="数据对应日期，非采集日期")
    confidence: float = Field(ge=0.0, le=1.0, description="字段级置信度")
    confidence_tier: ConfidenceTier = Field(description="下游信任权重")


class MissingField(BaseModel):
    field: str
    reason: str


class Conflict(BaseModel):
    field: str
    values: list = Field(default_factory=list)
    sources: list = Field(default_factory=list)
    resolution: str = "unresolved"


class Coverage(BaseModel):
    rag_context: str = "missing"
    market_data: str = "missing"
    fundamental_data: str = "missing"
    news_data: str = "missing"
    filings: str = "missing"


class EvidencePacket(BaseModel):
    symbol: str
    company_name: str = ""
    generated_at: str = ""
    as_of_date: str = ""
    request_type: str = "comprehensive_analysis"
    is_cold_start: bool = False
    coverage: Coverage = Field(default_factory=Coverage)
    facts: list[Fact] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    evidence_score: int = Field(default=0, ge=0, le=100)
    evidence_score_breakdown: dict = Field(default_factory=dict)
    allowed_output_level: OutputLevel = OutputLevel.INSUFFICIENT_EVIDENCE


@dataclass
class GuardResult:
    allowed_output_level: OutputLevel
    reason: str
    evidence_score: int
    evidence_score_breakdown: dict = field(default_factory=dict)


_REQUEST_FIELD_EXPECTATIONS: dict[str, int] = {
    "comprehensive_analysis": 8,
    "fundamental_analysis": 6,
    "technical_analysis": 4,
    "news_sentiment": 3,
    "risk_assessment": 5,
}


_REQUEST_SOURCE_EXPECTATIONS: dict[str, int] = {
    "comprehensive_analysis": 3,
    "fundamental_analysis": 2,
    "technical_analysis": 1,
    "news_sentiment": 2,
    "risk_assessment": 2,
}


CRITICAL_FIELDS = {"revenue", "eps", "current_price", "revenue_growth_yoy", "eps_growth"}

_TIER_WEIGHT = {
    "machine": 1.0,
    "llm_extracted": 0.5,
    "llm_inferred": 0.2,
}


def compute_evidence_score(packet: EvidencePacket) -> EvidencePacket:
    facts = packet.facts
    request_type = packet.request_type
    expected_sources = _REQUEST_SOURCE_EXPECTATIONS.get(request_type, 2)
    expected_fields = _REQUEST_FIELD_EXPECTATIONS.get(request_type, 6)

    sources = {f.source for f in facts}
    machine_sources = {
        f.source for f in facts
        if f.confidence_tier == ConfidenceTier.MACHINE
    }
    weighted_source_count = len(machine_sources) + (
        len(sources - machine_sources) * 0.5
    )
    source_diversity = min(100, int(weighted_source_count / max(expected_sources, 1) * 100))

    from datetime import datetime, timedelta
    now = datetime.now().date()
    recency = 100
    for f in facts:
        try:
            d = datetime.strptime(f.as_of_date, "%Y-%m-%d").date()
            age = (now - d).days
        except (ValueError, TypeError):
            age = 365
        if age <= 1:
            continue
        elif age <= 7:
            recency = min(recency, 80)
        elif age <= 30:
            recency = min(recency, 60)
        elif age <= 90:
            recency = min(recency, 30)
        else:
            recency = min(recency, 10)

    weighted_fact_count = sum(
        _TIER_WEIGHT.get(f.confidence_tier.value if hasattr(f.confidence_tier, 'value') else f.confidence_tier, 0.5)
        for f in facts
    )
    completeness = min(100, int(weighted_fact_count / max(expected_fields, 1) * 100))

    field_confidence_avg = 0
    if facts:
        field_confidence_avg = int(sum(
            f.confidence * _TIER_WEIGHT.get(
                f.confidence_tier.value if hasattr(f.confidence_tier, 'value') else f.confidence_tier, 0.5
            )
            for f in facts
        ) / len(facts) * 100)

    evidence_score = int(
        source_diversity * 0.25
        + recency * 0.25
        + completeness * 0.30
        + field_confidence_avg * 0.20
    )

    packet.evidence_score = evidence_score
    packet.evidence_score_breakdown = {
        "source_diversity": source_diversity,
        "recency": recency,
        "completeness": completeness,
        "field_confidence_avg": field_confidence_avg,
    }
    return packet


def determine_output_level(packet: EvidencePacket) -> GuardResult:

    if not packet.facts:
        return GuardResult(
            allowed_output_level=OutputLevel.INSUFFICIENT_EVIDENCE,
            reason="no reliable facts available",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    machine_facts = [f for f in packet.facts if f.confidence_tier == ConfidenceTier.MACHINE]
    if not machine_facts and packet.is_cold_start:
        return GuardResult(
            allowed_output_level=OutputLevel.INSUFFICIENT_EVIDENCE,
            reason="no machine-verified facts in cold start",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if packet.evidence_score < 30:
        return GuardResult(
            allowed_output_level=OutputLevel.INSUFFICIENT_EVIDENCE,
            reason=f"evidence_score={packet.evidence_score} < 30",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if packet.evidence_score < 50:
        return GuardResult(
            allowed_output_level=OutputLevel.DATA_SUMMARY_ONLY,
            reason=f"evidence_score={packet.evidence_score} < 50",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    critical_missing = CRITICAL_FIELDS & {m.field for m in packet.missing_fields}
    if critical_missing:
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
            reason=f"critical fields missing: {critical_missing}",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if packet.conflicts:
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
            reason=f"{len(packet.conflicts)} unresolved conflict(s)",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if packet.evidence_score >= 70:
        return GuardResult(
            allowed_output_level=OutputLevel.FULL_ANALYSIS,
            reason="all checks passed",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    return GuardResult(
        allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
        reason=f"evidence_score={packet.evidence_score} insufficient",
        evidence_score=packet.evidence_score,
        evidence_score_breakdown=packet.evidence_score_breakdown,
    )


TIER_MARKS: dict[ConfidenceTier, str] = {
    ConfidenceTier.MACHINE: "[✓]",
    ConfidenceTier.LLM_EXTRACTED: "[~]",
    ConfidenceTier.LLM_INFERRED: "[?]",
}


def render_packet_for_agent(packet: EvidencePacket) -> str:
    guard_result = determine_output_level(packet)

    lines = [
        f"## Evidence Packet: {packet.symbol}",
        f"- Evidence Score: {packet.evidence_score}/100",
        f"- Output Level: {guard_result.allowed_output_level.value}",
        f"- Is Cold Start: {packet.is_cold_start}",
        f"- Guard Reason: {guard_result.reason}",
        "",
        "### Verified Facts (use ONLY these data points)",
    ]

    for f in packet.facts:
        mark = TIER_MARKS.get(f.confidence_tier, "[?]")
        lines.append(
            f"- {mark} {f.field}: {f.value} {f.unit} "
            f"(period: {f.period}, source: {f.source}, "
            f"as_of: {f.as_of_date}, confidence: {f.confidence:.0%})"
        )

    lines.append("")
    lines.append("### Missing Data (DO NOT fabricate)")
    for m in packet.missing_fields:
        lines.append(f"- {m.field}: {m.reason}")

    if packet.conflicts:
        lines.append("")
        lines.append("### Conflicts (DO NOT use for strong conclusions)")
        for c in packet.conflicts:
            lines.append(f"- {c.field}: {c.resolution} (sources: {c.sources})")

    lines.append("")
    lines.append("### Strict Rules")
    lines.append("- Base ALL claims on the facts above. Do not introduce facts not listed.")
    lines.append("- [?] facts are speculative, not definitive.")
    lines.append("- If a data point is missing, explicitly state it is unavailable.")
    lines.append("- Do NOT generate investment recommendations when output level is data_summary_only or insufficient_evidence.")

    return "\n".join(lines)


__all__ = [
    "EvidencePacket",
    "Fact",
    "MissingField",
    "Conflict",
    "Coverage",
    "ConfidenceTier",
    "OutputLevel",
    "GuardResult",
    "compute_evidence_score",
    "determine_output_level",
    "render_packet_for_agent",
]