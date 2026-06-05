from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from knowledge.ingestion import extract_records, should_ingest  # noqa: E402
from schemas.evidence_packet import Coverage, EvidencePacket, Fact  # noqa: E402


def _packet(evidence_score: int, facts: list[Fact]) -> EvidencePacket:
    return EvidencePacket(
        symbol="TSLA",
        request_type="comprehensive_analysis",
        is_cold_start=True,
        coverage=Coverage(),
        facts=facts,
        missing_fields=[],
        conflicts=[],
        evidence_score=evidence_score,
    )


def test_should_ingest_requires_minimum_evidence_score():
    low = _packet(49, [])
    high = _packet(50, [])
    assert should_ingest(low) is False
    assert should_ingest(high) is True


def test_extract_records_filters_low_quality_facts():
    facts = [
        Fact(field="current_price", value=100.0, unit="USD", period="latest", source="yfinance", as_of_date="2026-06-05", confidence=0.95, confidence_tier="machine"),
        Fact(field="news_headline", value="Headline", unit="text", period="latest", source="news", as_of_date="2026-06-05", confidence=0.69, confidence_tier="llm_extracted"),
        Fact(field="summary_hint", value="speculative", unit="text", period="latest", source="llm", as_of_date="2026-06-05", confidence=0.95, confidence_tier="llm_inferred"),
    ]
    packet = _packet(80, facts)
    records = extract_records(packet)
    assert len(records) == 1
    assert records[0].field == "current_price"
