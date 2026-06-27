from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConfidenceTier(str, Enum):
    """
    置信度等级枚举。
    1. MACHINE：机器级置信度
    2. LLM_EXTRACTED：LLM 提取的置信度
    3. LLM_INFERRED：LLM 推理的置信度
    4. USER_SUBMITTED：用户上传文档
    """
    MACHINE = "machine"
    LLM_EXTRACTED = "llm_extracted"
    LLM_INFERRED = "llm_inferred"
    USER_SUBMITTED = "user_submitted"


class OutputLevel(str, Enum):
    """
    输出等级枚举。
    1. FULL_ANALYSIS：完整分析
    2. LIMITED_ANALYSIS_PARTIAL：部分分析（包含缺失字段）
    3. LIMITED_ANALYSIS：部分分析（不包含缺失字段）
    4. DATA_SUMMARY_ONLY：仅返回数据摘要
    5. INSUFFICIENT_EVIDENCE：证据不足
    """
    FULL_ANALYSIS = "full_analysis"
    LIMITED_ANALYSIS_PARTIAL = "limited_analysis_partial"
    LIMITED_ANALYSIS = "limited_analysis"
    DATA_SUMMARY_ONLY = "data_summary_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Fact(BaseModel):
    """
    事实数据模型。
    1. field：标准化字段名，枚举约束
    2. value：原始值，不应让 LLM 自行补全
    3. unit：单位，如 USD、HKD、percent、shares、ratio 等
    4. period：时间周期，如 latest、FY2025、Q1_2026、TTM 等
    5. source：来源，枚举值，不允许空来源
    """
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
    """
    缺失字段模型。
    1. field：缺失字段名，枚举约束
    2. reason：缺失原因，如 "数据缺失"、"字段未采集"
    3. substitute：替代字段名，如 "current_price"、"revenue"
    """
    field: str
    reason: str
    substitute: Optional[str] = None


class Conflict(BaseModel):
    """
    冲突模型。
    1. field：冲突字段名，枚举约束
    2. values：冲突值列表
    3. sources：冲突来源列表
    4. resolution：冲突解决状态，如 "unresolved"、"resolved"
    """
    field: str
    values: list = Field(default_factory=list)
    sources: list = Field(default_factory=list)
    resolution: str = "unresolved"


class DocumentChunk(BaseModel):
    """
    文档证据块模型。
    与 Fact（结构化字段级事实）并行，承载非结构化长文档内容。
    1. chunk_id：唯一标识，如 "0700.HK_annual_2024_RiskFactors_p45"
    2. content：chunk 文本
    3. source：来源，如 "HKEX"、"user_uploaded"
    4. doc_id：所属文档唯一 ID
    5. doc_type：文档类型（annual_report / earnings_call / research_report / news）
    6. section：章节路径，如 "Risk Factors > Regulatory Risk"
    7. page：页码范围，如 "45-47"
    8. publish_date：发布日期
    9. report_period：报告期
    10. symbol：股票代码
    11. contains_table：是否包含表格
    12. language：语言
    """
    chunk_id: str = Field(description="唯一标识")
    content: str = Field(description="chunk 文本")
    source: str = Field(description="HKEX / user_uploaded 等")
    doc_id: str = Field(description="所属文档唯一 ID")
    doc_type: str = Field(description="annual_report / earnings_call / research_report / news")
    section: str = Field(default="", description="章节路径")
    page: str = Field(default="", description="页码范围")
    publish_date: str = Field(default="", description="发布日期")
    report_period: str = Field(default="", description="报告期")
    symbol: str = Field(default="", description="股票代码")
    contains_table: bool = Field(default=False, description="是否包含表格")
    language: str = Field(default="", description="语言")
    confidence_tier: str = Field(default="", description="user_submitted / machine 等")


class Coverage(BaseModel):
    """
    数据覆盖模型。
    1. rag_context：RAG 上下文，如 "公司介绍"、"行业分析"
    2. market_data：市场数据，如 "股票价格"、"股票成交量"
    3. fundamental_data：基本面数据，如 "EPS"、"ROE"
    4. news_data：新闻数据，如 "新闻标题"、"新闻内容"
    5. filings：文件数据，如 "公司报告"、"公司公告"
    6. document_evidence：文档证据覆盖，如 "available"、"missing"
    """
    rag_context: str = "missing"
    market_data: str = "missing"
    fundamental_data: str = "missing"
    news_data: str = "missing"
    filings: str = "missing"
    document_evidence: str = "missing"


class EvidencePacket(BaseModel):
    """
    证据包模型。
    1. symbol：股票代码，如 "AAPL"
    2. company_name：公司名称，如 "Apple Inc."
    3. generated_at：生成时间，如 "2025-01-01 12:00:00"
    4. as_of_date：数据对应日期，如 "2025-01-01"
    5. request_type：请求类型，如 "comprehensive_analysis"
    6. is_cold_start：是否冷冷启动，如 False
    7. coverage：数据覆盖模型
    8. facts：事实数据列表
    9. missing_fields：缺失字段列表
    10. conflicts：冲突列表
    """
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
    document_evidence: list[DocumentChunk] = Field(default_factory=list)
    evidence_score: int = Field(default=0, ge=0, le=100)
    evidence_score_breakdown: dict = Field(default_factory=dict)
    allowed_output_level: OutputLevel = OutputLevel.INSUFFICIENT_EVIDENCE


@dataclass
class GuardResult:
    """
    守卫结果模型。
    1. allowed_output_level：允许的输出等级
    2. reason：拒绝原因
    3. evidence_score：证据分数
    4. evidence_score_breakdown：证据分数分解
    """
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


_CRITICAL_FIELDS_BY_REQUEST_TYPE: dict[str, set[str]] = {
    "comprehensive_analysis": {
        "current_price",
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "pe_ratio",
        "market_cap",
    },
    "fundamental_analysis": {
        "revenue_growth_yoy",
        "eps_growth_yoy",
        "pe_ratio",
        "market_cap",
    },
    "technical_analysis": {
        "current_price",
        "rsi_14",
        "macd",
        "volatility_20d_annualized",
    },
    "news_sentiment": {"news_headline"},
    "risk_assessment": {"current_price", "volatility_20d_annualized"},
}

_TIER_WEIGHT = {
    "machine": 1.0,
    "llm_extracted": 0.5,
    "llm_inferred": 0.2,
}


def compute_evidence_score(packet: EvidencePacket) -> EvidencePacket:
    """
    计算证据分数。
    1. 从 Evidence Packet 中获取事实
    2. 计算证据分数
    3. 返回 Evidence Packet
    """
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

    # 9.8 输出等级联动：文档证据覆盖给予加分
    doc_bonus = 0
    if packet.coverage.document_evidence == "available":
        doc_bonus = 5
        evidence_score = min(100, evidence_score + doc_bonus)

    packet.evidence_score = evidence_score
    packet.evidence_score_breakdown = {
        "source_diversity": source_diversity,
        "recency": recency,
        "completeness": completeness,
        "field_confidence_avg": field_confidence_avg,
    }
    if doc_bonus:
        packet.evidence_score_breakdown["document_evidence_bonus"] = doc_bonus
    return packet


def determine_output_level(packet: EvidencePacket) -> GuardResult:
    """
    确定输出等级。
    1. 从 Evidence Packet 中获取证据分数
    2. 根据证据分数确定输出等级
    3. 返回 GuardResult
    """

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

    critical_fields = _CRITICAL_FIELDS_BY_REQUEST_TYPE.get(
        packet.request_type,
        _CRITICAL_FIELDS_BY_REQUEST_TYPE["comprehensive_analysis"],
    )
    hard_missing = [m.field for m in packet.missing_fields if not m.substitute]
    critical_missing = critical_fields & set(hard_missing)
    hard_missing_count = len(critical_missing)

    if hard_missing_count >= 2:
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
            reason=f"critical fields missing: {critical_missing}",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    partial_missing = [m.field for m in packet.missing_fields if m.substitute]
    critical_partial = critical_fields & set(partial_missing)
    substitute_count = len(critical_partial)

    if hard_missing_count == 0 and substitute_count <= 1 and packet.evidence_score >= 85 and not packet.conflicts:
        return GuardResult(
            allowed_output_level=OutputLevel.FULL_ANALYSIS,
            reason="all checks passed — high evidence coverage",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if hard_missing_count == 0 and substitute_count <= 1 and packet.evidence_score >= 80:
        reason_parts = []
        if critical_partial:
            reason_parts.append(f"critical fields have substitute only: {critical_partial}")
        if packet.conflicts:
            reason_parts.append(f"{len(packet.conflicts)} unresolved conflict(s)")
        reason = "; ".join(reason_parts) if reason_parts else "partial — near full coverage"
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS_PARTIAL,
            reason=reason,
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if critical_missing:
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
            reason=f"critical fields missing: {critical_missing}",
            evidence_score=packet.evidence_score,
            evidence_score_breakdown=packet.evidence_score_breakdown,
        )

    if critical_partial:
        return GuardResult(
            allowed_output_level=OutputLevel.LIMITED_ANALYSIS,
            reason=f"critical fields have substitute only: {critical_partial}",
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
    ConfidenceTier.USER_SUBMITTED: "[U]",
}

_CONFLICT_THRESHOLDS: dict[str, float] = {
    "current_price": 0.02,
    "pe_ratio": 0.10,
    "pb_ratio": 0.10,
    "market_cap": 0.10,
    "revenue_growth_yoy": 0.05,
    "eps_growth_yoy": 0.05,
}


def detect_conflicts(packet: EvidencePacket) -> EvidencePacket:
    """
    字段级冲突检测。同一 field 有多个数值型 fact 且来源不同时，
    若偏差超过对应阈值，则标记为冲突。
    官方来源（SEC_EDGAR、HKEX）优先于第三方。
    """
    from collections import defaultdict
    field_groups = defaultdict(list)
    for f in packet.facts:
        if isinstance(f.value, (int, float)):
            field_groups[f.field].append(f)

    conflicts = []
    for field_name, group in field_groups.items():
        if len(group) < 2:
            continue
        sources = {f.source for f in group}
        if len(sources) < 2:
            continue

        official_sources = {"SEC_EDGAR", "HKEX", "SSE", "SZSE"}
        has_official = bool(sources & official_sources)

        values = [float(f.value) for f in group]
        v_min, v_max = min(values), max(values)
        if v_max == 0:
            continue
        deviation = (v_max - v_min) / abs(v_max)

        threshold = _CONFLICT_THRESHOLDS.get(field_name, 0.10)
        if deviation > threshold:
            resolution = "official_source_preferred" if has_official else "marked_unresolved"
            conflicts.append(Conflict(
                field=field_name,
                values=values,
                sources=list(sources),
                resolution=resolution,
            ))

    if conflicts:
        packet.conflicts = list(packet.conflicts) + conflicts
    return packet


LANGUAGE_LABELS: dict[str, str] = {
    "zh": "简体中文",
    "yue": "粤语 (Cantonese)",
    "en": "English",
}


def _language_instruction(language: str) -> str:
    if not language or language == "en":
        return ""
    label = LANGUAGE_LABELS.get(language, language)
    return f"\n\n### 【语言要求 - 最高优先级】\n请全程使用 {label} 回复。所有分析内容、指标解读、结论、建议都必须使用 {label} 输出。禁止使用其他语言。"


def render_packet_for_agent(packet: EvidencePacket, language: str = "") -> str:
    """
    渲染 Evidence Packet 为代理输入格式。
    1. 从 Evidence Packet 中获取数据
    2. 根据输出等级和语言要求渲染代理输入格式
    3. 返回渲染输入
    """
    """
    为 Agent 渲染 Evidence Packet。
    1. 从 Evidence Packet 中获取 GuardResult
    2. 构建渲染字符串
    3. 返回渲染字符串
    """
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
        if m.substitute:
            lines.append(f"- {m.field}: {m.reason} — use '{m.substitute}' as indirect evidence ONLY")
        else:
            lines.append(f"- {m.field}: {m.reason}")

    if packet.conflicts:
        lines.append("")
        lines.append("### Conflicts (DO NOT use for strong conclusions)")
        for c in packet.conflicts:
            lines.append(f"- {c.field}: {c.resolution} (sources: {c.sources})")

    if packet.document_evidence:
        lines.append("")
        lines.append("### Document Evidence (non-structured, from reports & filings)")
        lines.append("- These are excerpts from annual reports, earnings calls, research reports, etc.")
        lines.append("- Use them for qualitative context (risk, strategy, management outlook).")
        lines.append("- Cross-reference with structured facts above; structured facts take precedence for numeric claims.")
        lines.append("- When referencing a specific chunk, cite it with its [doc:N] marker for traceability.")
        lines.append("")
        for i, dc in enumerate(packet.document_evidence, start=1):
            tier_mark = ""
            if dc.confidence_tier == "user_submitted":
                tier_mark = TIER_MARKS.get(ConfidenceTier.USER_SUBMITTED, "[U]")
            elif dc.confidence_tier in {t.value for t in ConfidenceTier}:
                tier_mark = TIER_MARKS.get(ConfidenceTier(dc.confidence_tier), "")
            header = (
                f"[doc:{i}]{tier_mark} source: {dc.doc_id}, section: {dc.section}"
                + (f", page: {dc.page}" if dc.page else "")
                + f", date: {dc.publish_date}]"
            )
            if dc.contains_table:
                header += " (contains table)"
            lines.append(f"#### {header}")
            # limit individual chunk display to avoid blowing up context
            content = dc.content[:1800] + "..." if len(dc.content) > 1800 else dc.content
            lines.append(content)
            lines.append("")

    lines.append("")
    lines.append("### Strict Rules")
    lines.append("- Base ALL claims on the facts above. Do not introduce facts not listed.")
    lines.append("- [?] facts are speculative, not definitive.")
    lines.append("- If a data point is missing, explicitly state it is unavailable.")
    lines.append("- Do NOT generate investment recommendations when output level is data_summary_only or insufficient_evidence.")
    lines.append("- DO NOT output target price, price target, 目标价, 价位, or 介入点 in human-readable analysis text.")
    lines.append("- If a downstream UI needs a valuation scenario, emit it only as machine-readable metadata and mark values null when evidence is insufficient.")
    lines.append("- When mentioning a numeric fact (price, PE, etc.), quote the EXACT value from the facts list. Do NOT round, approximate, or use 约/大概/approximately/roughly.")
    lines.append("- SUBSTITUTE FIELDS: 'revenue' / 'eps' are absolute values, NOT year-over-year growth rates. When revenue_growth_yoy or eps_growth_yoy is missing with a substitute, explain that trend analysis is limited to absolute values, and do NOT fabricate growth percentages.")

    lang_instr = _language_instruction(language)
    if lang_instr:
        lines.append(lang_instr)

    return "\n".join(lines)


__all__ = [
    "EvidencePacket",
    "Fact",
    "MissingField",
    "Conflict",
    "DocumentChunk",
    "Coverage",
    "ConfidenceTier",
    "OutputLevel",
    "GuardResult",
    "compute_evidence_score",
    "determine_output_level",
    "detect_conflicts",
    "render_packet_for_agent",
]