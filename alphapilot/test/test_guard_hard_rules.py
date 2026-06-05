from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.guard_agent import _hard_rule_guard  # noqa: E402


def _packet_full_level() -> dict:
    return {
        "symbol": "TSLA",
        "request_type": "comprehensive_analysis",
        "is_cold_start": False,
        "coverage": {
            "rag_context": "available",
            "market_data": "available",
            "fundamental_data": "available",
            "news_data": "available",
            "filings": "missing",
        },
        "facts": [
            {
                "field": "current_price",
                "value": 200.0,
                "unit": "USD",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": "2026-06-05",
                "confidence": 0.95,
                "confidence_tier": "machine",
            },
            {
                "field": "revenue_growth_yoy",
                "value": 20.1,
                "unit": "percent",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": "2026-06-05",
                "confidence": 0.9,
                "confidence_tier": "machine",
            },
            {
                "field": "eps_growth_yoy",
                "value": 18.2,
                "unit": "percent",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": "2026-06-05",
                "confidence": 0.9,
                "confidence_tier": "machine",
            },
            {
                "field": "pe_ratio",
                "value": 30.0,
                "unit": "ratio",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": "2026-06-05",
                "confidence": 0.9,
                "confidence_tier": "machine",
            },
            {
                "field": "market_cap",
                "value": 1000000000,
                "unit": "USD",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": "2026-06-05",
                "confidence": 0.9,
                "confidence_tier": "machine",
            },
        ],
        "missing_fields": [],
        "conflicts": [],
        "evidence_score": 85,
        "evidence_score_breakdown": {},
        "allowed_output_level": "full_analysis",
    }


def test_guard_rejects_symbol_mismatch():
    result = _hard_rule_guard(_packet_full_level(), "current price is 200", symbol="AAPL")
    assert result["is_valid"] is False
    assert any("Symbol mismatch" in issue for issue in result["issues"])


def test_guard_rejects_ungrounded_keyword_claim():
    packet = _packet_full_level()
    packet["facts"] = [f for f in packet["facts"] if f["field"] != "pb_ratio"]
    result = _hard_rule_guard(packet, "The P/B is 8.0 and valuation is expensive.", symbol="TSLA")
    assert result["is_valid"] is False
    assert any("Ungrounded claim" in issue for issue in result["issues"])
