from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass, field

from schemas.evidence_packet import EvidencePacket, ConfidenceTier


TTL_MAP: dict[str, timedelta] = {
    "market_data": timedelta(minutes=5),
    "market_data_daily": timedelta(hours=24),
    "fundamental_data": timedelta(days=180),
    "fundamental_estimate": timedelta(days=30),
    "news_data": timedelta(days=30),
    "filings": timedelta.max,
}


@dataclass
class IngestionRecord:
    symbol: str
    data_type: str
    field: str
    value: str | float
    source: str
    as_of_date: str
    confidence: float
    confidence_tier: str
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""

    def __post_init__(self) -> None:
        ttl = TTL_MAP.get(self.data_type, timedelta(days=7))
        if not self.expires_at:
            self.expires_at = (
                datetime.now() + ttl
            ).isoformat()


def should_ingest(packet: EvidencePacket) -> bool:
    if packet.evidence_score < 50:
        return False
    return True


def extract_records(packet: EvidencePacket) -> list[IngestionRecord]:
    records = []
    for fact in packet.facts:
        if fact.confidence_tier == ConfidenceTier.LLM_INFERRED:
            continue
        if fact.confidence_tier == ConfidenceTier.LLM_EXTRACTED and fact.confidence < 0.7:
            continue

        data_type = _classify_data_type(fact.field)
        records.append(IngestionRecord(
            symbol=packet.symbol,
            data_type=data_type,
            field=fact.field,
            value=fact.value,
            source=fact.source,
            as_of_date=fact.as_of_date,
            confidence=fact.confidence,
            confidence_tier=fact.confidence_tier.value,
        ))
    return records


def _classify_data_type(field: str) -> str:
    market_fields = {"current_price", "price_change_pct", "rsi_14", "macd",
                     "macd_signal", "volatility_20d_annualized", "avg_volume_20d"}
    fundamental_fields = {"revenue_growth_yoy", "eps_growth_yoy", "pe_ratio",
                          "forward_pe", "pb_ratio", "market_cap", "dividend_yield",
                          "beta", "return_on_equity", "debt_to_equity",
                          "sector", "industry", "company_name", "revenue", "net_profit", "eps",
                          "gross_margin", "operating_margin", "net_margin", "debt_to_assets",
                          "net_profit_growth_yoy", "operating_cash_flow", "free_cash_flow",
                          "cash_position", "total_debt", "net_debt"}
    news_fields = {"news_headline"}

    if field in market_fields:
        return "market_data"
    if field in fundamental_fields:
        return "fundamental_data"
    if field in news_fields:
        return "news_data"
    return "misc"


__all__ = [
    "IngestionRecord",
    "TTL_MAP",
    "should_ingest",
    "extract_records",
]