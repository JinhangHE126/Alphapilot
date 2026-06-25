from __future__ import annotations

import os
import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from schemas.evidence_packet import Fact, ConfidenceTier

DB_PATH = os.getenv("FACT_STORE_PATH", str(Path(__file__).parent.parent / "data" / "fact_store.db"))

TTL_MAP: dict[str, timedelta] = {
    "market_data": timedelta(minutes=5),
    "market_data_daily": timedelta(hours=24),
    "fundamental_data": timedelta(days=180),
    "fundamental_estimate": timedelta(days=30),
    "news_data": timedelta(days=30),
    "filings": timedelta.max,
}
_DEFAULT_TTL = timedelta(days=7)


class FactStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._run_migrations()

    def _run_migrations(self) -> None:
        migration_dir = Path(__file__).parent / "migrations"
        if not migration_dir.is_dir():
            return
        for name in sorted(os.listdir(str(migration_dir))):
            if name.endswith(".sql"):
                path = migration_dir / name
                self._conn.executescript(path.read_text(encoding="utf-8"))
        self._conn.commit()

    def upsert_fact(self, symbol: str, fact: Fact) -> None:
        field = fact.field
        data_type = self._classify_data_type(field)
        ttl = TTL_MAP.get(data_type, _DEFAULT_TTL)
        now = datetime.now()
        expires_at = (now + ttl).isoformat() if ttl != timedelta.max else None
        payload = json.dumps({
            "field": field,
            "value": fact.value,
            "unit": fact.unit,
            "period": fact.period,
        }, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

        tier = fact.confidence_tier
        if isinstance(tier, ConfidenceTier):
            tier_str = tier.value
        else:
            tier_str = str(tier)

        existing = self._conn.execute(
            "SELECT id, raw_payload_hash, status FROM facts "
            "WHERE symbol=? AND field=? AND period=? AND source=? AND as_of_date=?",
            (symbol, field, fact.period, fact.source, fact.as_of_date),
        ).fetchone()

        if existing and existing["status"] == "active" and existing["raw_payload_hash"] == payload_hash:
            return

        if existing and existing["status"] == "active":
            self._conn.execute(
                "UPDATE facts SET status='superseded' WHERE id=?",
                (existing["id"],),
            )
            version = existing["id"] + 1 if existing["id"] else 1
        else:
            version = 1

        self._conn.execute(
            """INSERT OR REPLACE INTO facts
               (symbol, field, value, unit, period, source, source_url,
                as_of_date, retrieved_at, expires_at, confidence,
                confidence_tier, status, version, raw_payload_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (
                symbol, field, str(fact.value), fact.unit, fact.period,
                fact.source, fact.source_url, fact.as_of_date,
                now.isoformat(), expires_at,
                fact.confidence, tier_str,
                version, payload_hash,
            ),
        )
        self._conn.commit()

    def get_active_facts(self, symbol: str, fields: Optional[list[str]] = None) -> list[dict]:
        now = datetime.now().isoformat()
        if fields:
            placeholders = ",".join("?" for _ in fields)
            rows = self._conn.execute(
                f"SELECT * FROM facts WHERE symbol=? AND status='active' "
                f"AND field IN ({placeholders}) "
                f"AND (expires_at IS NULL OR expires_at > ?)",
                (symbol, *fields, now),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM facts WHERE symbol=? AND status='active' "
                "AND (expires_at IS NULL OR expires_at > ?)",
                (symbol, now),
            ).fetchall()
        return [dict(r) for r in rows]

    def has_coverage(self, symbol: str, required_fields: list[str]) -> bool:
        active = self.get_active_facts(symbol, fields=required_fields)
        covered = {r["field"] for r in active}
        return set(required_fields).issubset(covered)

    def _classify_data_type(self, field: str) -> str:
        market_fields = {"current_price", "price_change_pct", "rsi_14", "macd",
                         "macd_signal", "volatility_20d_annualized", "avg_volume_20d"}
        fundamental_fields = {"revenue_growth_yoy", "eps_growth_yoy", "pe_ratio",
                              "forward_pe", "pb_ratio", "market_cap", "dividend_yield",
                              "beta", "return_on_equity", "debt_to_equity",
                              "sector", "industry", "company_name", "revenue", "net_profit", "eps",
                              "revenue_ttm", "profit_margin", "gross_margin", "operating_margin",
                              "net_margin", "debt_to_assets", "net_profit_growth_yoy",
                              "operating_cash_flow", "free_cash_flow", "cash_position",
                              "total_debt", "net_debt"}
        news_fields = {"news_headline"}
        filing_fields = {"filing_url", "hkex_announcement"}

        if field in market_fields:
            return "market_data"
        if field in fundamental_fields:
            return "fundamental_data"
        if field in news_fields:
            return "news_data"
        if field in filing_fields:
            return "filings"
        return "misc"


_fact_store: Optional[FactStore] = None


def get_fact_store() -> FactStore:
    global _fact_store
    if _fact_store is None:
        _fact_store = FactStore()
    return _fact_store