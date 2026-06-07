from __future__ import annotations

import os
from datetime import date

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider


class TushareProvider(DataProvider):
    name = "tushare"
    priority = 85

    def __init__(self) -> None:
        self._api_key = os.getenv("TUSHARE_API_KEY", "")
        if not self._api_key:
            self.enabled = False

    def _get_pro(self):
        try:
            import tushare as ts
            pro = ts.pro_api(self._api_key)
            return pro
        except Exception:
            return None

    def _resolve_ts_code(self, symbol: str) -> str | None:
        if symbol.endswith(".SZ"):
            return f"{symbol.replace('.SZ', '')}.SZ"
        if symbol.endswith(".SS"):
            return f"{symbol.replace('.SS', '')}.SH"
        return None

    def collect_market(self, symbol: str) -> list[Fact]:
        ts_code = self._resolve_ts_code(symbol)
        if ts_code is None:
            return []

        pro = self._get_pro()
        if pro is None:
            return []

        today = date.today().isoformat()
        facts = []

        try:
            df = pro.daily(ts_code=ts_code, limit=2)
            if df is not None and not df.empty:
                df = df.sort_values("trade_date")
                row = df.iloc[-1]
                close = float(row["close"])
                facts.append(Fact(
                    field="current_price", value=close, unit="CNY",
                    period="latest", source="tushare", source_url=None,
                    as_of_date=today, confidence=0.90, confidence_tier="machine",
                ))
                if len(df) >= 2:
                    prev_close = float(df.iloc[-2]["close"])
                    change = round((close - prev_close) / prev_close * 100, 2)
                    facts.append(Fact(
                        field="price_change_pct", value=change, unit="percent",
                        period="1d", source="tushare", source_url=None,
                        as_of_date=today, confidence=0.90, confidence_tier="machine",
                    ))
        except Exception:
            pass

        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        ts_code = self._resolve_ts_code(symbol)
        if ts_code is None:
            return []

        pro = self._get_pro()
        if pro is None:
            return []

        today = date.today().isoformat()
        facts = []

        try:
            df = pro.daily_basic(ts_code=ts_code, limit=1)
            if df is not None and not df.empty:
                row = df.iloc[0]
                pe = row.get("pe")
                if pe is not None:
                    facts.append(Fact(
                        field="pe_ratio", value=round(float(pe), 2),
                        unit="ratio", period="latest", source="tushare",
                        source_url=None, as_of_date=today,
                        confidence=0.85, confidence_tier="machine",
                    ))
                mcap = row.get("total_mv")
                if mcap is not None:
                    facts.append(Fact(
                        field="market_cap", value=float(mcap) * 10000,
                        unit="CNY", period="latest", source="tushare",
                        source_url=None, as_of_date=today,
                        confidence=0.90, confidence_tier="machine",
                    ))
        except Exception:
            pass

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        return []