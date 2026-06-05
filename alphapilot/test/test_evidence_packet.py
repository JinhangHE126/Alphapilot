from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.evidence_packet import (  # noqa: E402
    Coverage,
    EvidencePacket,
    Fact,
    MissingField,
    OutputLevel,
    compute_evidence_score,
    determine_output_level,
)


def _base_packet() -> EvidencePacket:
    return EvidencePacket(
        symbol="TSLA",
        request_type="comprehensive_analysis",
        is_cold_start=False,
        coverage=Coverage(
            rag_context="available",
            market_data="available",
            fundamental_data="available",
            news_data="available",
            filings="missing",
        ),
    )


def test_determine_output_level_no_facts():
    packet = _base_packet()
    packet = compute_evidence_score(packet)
    result = determine_output_level(packet)
    assert result.allowed_output_level == OutputLevel.INSUFFICIENT_EVIDENCE


def test_determine_output_level_full_analysis_when_fields_complete():
    packet = _base_packet()
    packet.facts = [
        Fact(field="current_price", value=200.0, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.95, confidence_tier="machine"),
        Fact(field="revenue_growth_yoy", value=20.1, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="eps_growth_yoy", value=18.2, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="pe_ratio", value=30.0, unit="ratio", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="market_cap", value=1000000000, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="news_headline", value="Positive delivery update", unit="text", period="latest", source="newsapi", as_of_date="2026-06-05", confidence=0.70, confidence_tier="llm_extracted"),
    ]
    packet = compute_evidence_score(packet)
    result = determine_output_level(packet)
    assert result.allowed_output_level == OutputLevel.FULL_ANALYSIS


def test_determine_output_level_limited_when_critical_missing():
    packet = _base_packet()
    packet.facts = [
        Fact(field="current_price", value=200.0, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.95, confidence_tier="machine"),
        Fact(field="revenue_growth_yoy", value=20.1, unit="percent", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="pe_ratio", value=30.0, unit="ratio", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
        Fact(field="market_cap", value=1000000000, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.90, confidence_tier="machine"),
    ]
    packet.missing_fields = [
        MissingField(field="eps_growth_yoy", reason="missing from data source")
    ]
    packet = compute_evidence_score(packet)
    result = determine_output_level(packet)
    assert result.allowed_output_level == OutputLevel.LIMITED_ANALYSIS
