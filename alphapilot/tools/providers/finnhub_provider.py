from __future__ import annotations

import os
import json
from datetime import date, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError
import time as _time

import pandas as pd

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

_FINNHUB_BASE = "https://finnhub.io/api/v1"


class FinnhubProvider(DataProvider):
    name = "finnhub"
    priority = 70

    def __init__(self) -> None:
        self._api_key = os.getenv("FINNHUB_API_KEY", "")
        if not self._api_key:
            self.enabled = False

    def _get(self, path: str) -> dict | None:
        url = f"{_FINNHUB_BASE}{path}&token={self._api_key}" if "?" in path else f"{_FINNHUB_BASE}{path}?token={self._api_key}"
        req = Request(url)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, Exception):
            return None

    def collect_market(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        today = date.today().isoformat()

        quote = self._get(f"/quote?symbol={clean}")

        facts: list[Fact] = []
        if quote and isinstance(quote, dict):
            price = quote.get("c")
            if price and isinstance(price, (int, float)) and price > 0:
                facts.append(Fact(
                    field="current_price", value=round(float(price), 2),
                    unit="USD", period="latest", source="finnhub",
                    source_url=None, as_of_date=today,
                    confidence=0.90, confidence_tier="machine",
                ))
            change_pct = quote.get("dp")
            if change_pct is not None:
                try:
                    facts.append(Fact(
                        field="price_change_pct", value=round(float(change_pct), 2),
                        unit="percent", period="latest", source="finnhub",
                        source_url=None, as_of_date=today,
                        confidence=0.90, confidence_tier="machine",
                    ))
                except (ValueError, TypeError):
                    pass

        to_ts = int(_time.time())
        from_ts = to_ts - 60 * 86400
        candle = self._get(f"/stock/candle?symbol={clean}&resolution=D&from={from_ts}&to={to_ts}")
        if candle and isinstance(candle, dict) and candle.get("s") == "ok":
            closes = candle.get("c", [])
            highs = candle.get("h", [])
            lows = candle.get("l", [])
            volumes = candle.get("v", [])
            if isinstance(closes, list) and len(closes) >= 5:
                try:
                    df = pd.DataFrame({"Close": closes, "High": highs, "Low": lows, "Volume": volumes})
                    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
                    df = df.dropna(subset=["Close"])
                    if len(df) >= 14:
                        close = df["Close"]
                        delta = close.diff()
                        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi_series = 100.0 - (100.0 / (1.0 + rs))
                        rsi = round(float(rsi_series.iloc[-1]), 1)
                        facts.append(Fact(
                            field="rsi_14", value=rsi, unit="index",
                            period="latest", source="finnhub",
                            source_url=None, as_of_date=today,
                            confidence=0.80, confidence_tier="machine",
                        ))

                        ema12 = close.ewm(span=12, adjust=False).mean()
                        ema26 = close.ewm(span=26, adjust=False).mean()
                        macd_line = ema12 - ema26
                        signal_line = macd_line.ewm(span=9, adjust=False).mean()
                        macd_val = round(float(macd_line.iloc[-1]), 4)
                        macd_signal = round(float(signal_line.iloc[-1]), 4)
                        facts.append(Fact(
                            field="macd", value=macd_val, unit="index",
                            period="latest", source="finnhub",
                            source_url=None, as_of_date=today,
                            confidence=0.80, confidence_tier="machine",
                        ))
                        facts.append(Fact(
                            field="macd_signal", value=macd_signal, unit="index",
                            period="latest", source="finnhub",
                            source_url=None, as_of_date=today,
                            confidence=0.80, confidence_tier="machine",
                        ))

                        returns = close.pct_change().dropna()
                        if len(returns) >= 5:
                            vol = round(float(returns.std() * (252 ** 0.5) * 100), 2)
                            facts.append(Fact(
                                field="volatility_20d_annualized", value=vol,
                                unit="percent", period="latest", source="finnhub",
                                source_url=None, as_of_date=today,
                                confidence=0.80, confidence_tier="machine",
                            ))

                        avg_vol = int(volumes.dropna().tail(20).mean()) if len(volumes.dropna()) >= 5 else 0
                        if avg_vol > 0:
                            facts.append(Fact(
                                field="avg_volume_20d", value=avg_vol,
                                unit="shares", period="latest", source="finnhub",
                                source_url=None, as_of_date=today,
                                confidence=0.80, confidence_tier="machine",
                            ))
                except Exception:
                    pass

        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        today = date.today().isoformat()
        facts = []

        profile = self._get(f"/stock/profile2?symbol={clean}")
        if profile and profile.get("marketCapitalization"):
            try:
                mcap_m = float(profile["marketCapitalization"])
                facts.append(Fact(
                    field="market_cap", value=mcap_m * 1_000_000,
                    unit="USD", period="latest", source="finnhub",
                    source_url=None, as_of_date=today,
                    confidence=0.90, confidence_tier="machine",
                ))
            except (ValueError, TypeError):
                pass

        metrics = self._get(f"/stock/metric?symbol={clean}")
        if metrics and metrics.get("metric"):
            m = metrics["metric"]
            pe = m.get("peBasicExclExtraTTM") or m.get("peTTM")
            if pe:
                try:
                    facts.append(Fact(
                        field="pe_ratio", value=round(float(pe), 2),
                        unit="ratio", period="latest", source="finnhub",
                        source_url=None, as_of_date=today,
                        confidence=0.85, confidence_tier="machine",
                    ))
                except (ValueError, TypeError):
                    pass

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        clean = symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")
        today = date.today()
        today_str = today.isoformat()
        is_us = not symbol.endswith(('.HK', '.SZ', '.SS', '.L', '.T'))

        facts: list[Fact] = []

        if is_us:
            week_ago = (today - timedelta(days=7)).isoformat()
            data = self._get(f"/company-news?symbol={clean}&from={week_ago}&to={today_str}")
            if data and isinstance(data, list):
                for item in data[:5]:
                    headline = item.get("headline", "")
                    if not headline:
                        continue
                    published = date.fromtimestamp(item.get("datetime", 0)).isoformat() if item.get("datetime") else today_str
                    facts.append(Fact(
                        field="news_headline", value=headline,
                        unit="text", period="latest",
                        source=item.get("source", "finnhub_news"),
                        source_url=item.get("url"),
                        as_of_date=published,
                        confidence=0.70, confidence_tier="llm_extracted",
                    ))

        if not facts:
            gen_news = self._get(f"/news?category=general")
            if gen_news and isinstance(gen_news, list):
                for item in gen_news[:3]:
                    headline = item.get("headline", "")
                    if not headline:
                        continue
                    published = date.fromtimestamp(item.get("datetime", 0)).isoformat() if item.get("datetime") else today_str
                    facts.append(Fact(
                        field="news_headline", value=f"[Market] {headline}",
                        unit="text", period="latest",
                        source=item.get("source", "finnhub_market"),
                        source_url=item.get("url"),
                        as_of_date=published,
                        confidence=0.55, confidence_tier="llm_extracted",
                    ))

        return facts