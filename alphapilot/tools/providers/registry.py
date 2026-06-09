from __future__ import annotations

import os
from typing import Optional

from tools.providers.base import DataProvider

_DEFAULT_ENABLED = "yfinance,sec_edgar,akshare,eastmoney,sina_tencent"
_DEFAULT_PRIORITY = "sec_edgar:100,yfinance:40"
_COLLECTOR_TIMEOUT = 15


class ProviderRegistry:
    FIELD_PRIORITY: dict[str, dict[str, list[str]]] = {
        "HK": {
            "current_price":        ["akshare_hk", "akshare_hk_hist", "tencent_hk", "eastmoney_push2", "yfinance"],
            "price_change_pct":     ["akshare_hk", "akshare_hk_hist", "tencent_hk", "eastmoney_push2", "yfinance"],
            "rsi_14":               ["akshare_hk_hist", "yfinance"],
            "volatility_20d_annualized": ["akshare_hk_hist", "yfinance"],
            "avg_volume_20d":       ["akshare_hk_hist", "akshare_hk", "yfinance"],
            "market_cap":           ["tencent_hk", "akshare", "eastmoney_push2", "yfinance"],
            "pe_ratio":             ["tencent_hk", "yfinance", "akshare_derived", "akshare", "eastmoney_push2"],
            "revenue_growth_yoy":   ["eastmoney_gmaindicator", "akshare_hk", "akshare", "yfinance"],
            "eps_growth_yoy":       ["eastmoney_gmaindicator", "akshare_hk", "akshare", "yfinance"],
            "news_headline":        ["akshare_hk", "yfinance"],
            "return_on_equity":     ["eastmoney_gmaindicator", "akshare", "yfinance"],
            "gross_margin":         ["eastmoney_gmaindicator"],
            "net_margin":           ["eastmoney_gmaindicator"],
            "debt_to_assets":       ["eastmoney_gmaindicator"],
        },
        "US": {
            "revenue":              ["SEC_EDGAR", "yfinance"],
            "eps":                  ["SEC_EDGAR", "yfinance"],
            "revenue_growth_yoy":   ["yfinance", "sec_edgar", "alpha_vantage", "eastmoney_gmaindicator"],
            "eps_growth_yoy":       ["yfinance", "sec_edgar", "alpha_vantage", "eastmoney_gmaindicator"],
            "market_cap":           ["yfinance", "finnhub", "alpha_vantage", "polygon", "tiingo", "sina_us", "tencent_us", "eastmoney_push2"],
            "pe_ratio":             ["yfinance", "finnhub", "alpha_vantage", "tiingo", "sina_us", "tencent_us", "eastmoney_push2"],
            "current_price":        ["polygon", "tiingo", "yfinance", "finnhub", "sina_us", "tencent_us", "eastmoney_push2"],
            "price_change_pct":     ["polygon", "tiingo", "yfinance", "finnhub", "sina_us", "tencent_us", "eastmoney_push2"],
            "avg_volume_20d":       ["polygon", "yfinance", "finnhub"],
            "rsi_14":               ["yfinance", "finnhub"],
            "macd":                 ["yfinance", "finnhub"],
            "macd_signal":          ["yfinance", "finnhub"],
            "volatility_20d_annualized": ["yfinance", "finnhub"],
            "news_headline":        ["finnhub_news", "finnhub_market", "yfinance"],
            "return_on_equity":     ["eastmoney_gmaindicator", "yfinance"],
            "gross_margin":         ["eastmoney_gmaindicator"],
            "net_margin":           ["eastmoney_gmaindicator"],
            "debt_to_assets":       ["eastmoney_gmaindicator"],
        },
        "CN": {
            "current_price":        ["yfinance"],
            "market_cap":           ["yfinance"],
            "pe_ratio":             ["yfinance"],
        },
    }

    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}
        self._cooldown: dict[str, float] = {}
        self._failure_threshold: int = 3
        self._cooldown_seconds: float = 300.0

    def register(self, provider: DataProvider) -> None:
        enabled_str = os.getenv("ENABLED_DATA_PROVIDERS", _DEFAULT_ENABLED)
        enabled_names = {n.strip() for n in enabled_str.split(",") if n.strip()}

        if enabled_names and provider.name not in enabled_names:
            provider.enabled = False

        priority_str = os.getenv("PROVIDER_PRIORITY", _DEFAULT_PRIORITY)
        for entry in priority_str.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, prio = entry.split(":", 1)
                if name.strip() == provider.name:
                    try:
                        provider.priority = int(prio.strip())
                    except ValueError:
                        pass

        self._providers[provider.name] = provider

    def get_enabled(self) -> list[DataProvider]:
        import time

        now = time.time()
        enabled = []
        for p in self._providers.values():
            if not p.enabled:
                continue
            if p.name in self._cooldown:
                if now - self._cooldown[p.name] < self._cooldown_seconds:
                    continue
                del self._cooldown[p.name]
            if p.failure_count >= self._failure_threshold:
                self._cooldown[p.name] = now
                print(f"   ⚠️ Provider {p.name} entered cooldown ({self._cooldown_seconds}s)")
                continue
            enabled.append(p)
        enabled.sort(key=lambda p: p.priority, reverse=True)
        return enabled

    def record_result(self, provider_name: str, success: bool) -> None:
        p = self._providers.get(provider_name)
        if p is None:
            return
        if success:
            p.record_success()
        else:
            p.record_failure()
    def apply_field_priority(self, facts: list[dict], market: str) -> list[dict]:
        """Dedup facts by field-level source priority after parallel collection.

        For each field, keep only the fact from the highest-priority source
        defined in FIELD_PRIORITY[market]. Fields not in the priority map
        are passed through unchanged (all sources retained).
        """
        priority_map = self.FIELD_PRIORITY.get(market, {})
        if not priority_map:
            return facts

        best: dict[str, dict] = {}
        kept_all: list[dict] = []

        for f in facts:
            field = f.get("field", "")
            source = f.get("source", "")
            ordered = priority_map.get(field)

            if ordered is None:
                kept_all.append(f)
                continue

            try:
                rank = ordered.index(source)
            except ValueError:
                if field not in best:
                    best[field] = f
                continue

            if field not in best:
                best[field] = f
            else:
                prev_source = best[field].get("source", "")
                try:
                    prev_rank = ordered.index(prev_source)
                except ValueError:
                    best[field] = f
                    continue
                if rank < prev_rank:
                    if prev_rank != rank:
                        pass
                    best[field] = f

        result = list(best.values()) + kept_all
        return result


_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _init_defaults(_registry)
    return _registry


def _init_defaults(registry: ProviderRegistry) -> None:
    from tools.providers.yfinance_provider import YFinanceProvider
    from tools.providers.sec_edgar_provider import SecEdgarProvider

    registry.register(YFinanceProvider())
    registry.register(SecEdgarProvider())

    try:
        from tools.providers.alpha_vantage_provider import AlphaVantageProvider
        registry.register(AlphaVantageProvider())
    except Exception:
        pass

    try:
        from tools.providers.polygon_provider import PolygonProvider
        registry.register(PolygonProvider())
    except Exception:
        pass

    try:
        from tools.providers.akshare_provider import AKShareProvider
        registry.register(AKShareProvider())
    except Exception:
        pass

    try:
        from tools.providers.tiingo_provider import TiingoProvider
        registry.register(TiingoProvider())
    except Exception:
        pass

    try:
        from tools.providers.finnhub_provider import FinnhubProvider
        registry.register(FinnhubProvider())
    except Exception:
        pass

    try:
        from tools.providers.tushare_provider import TushareProvider
        registry.register(TushareProvider())
    except Exception:
        pass

    try:
        from tools.providers.eastmoney_provider import EastmoneyProvider
        registry.register(EastmoneyProvider())
    except Exception:
        pass

    try:
        from tools.providers.sina_tencent_provider import SinaTencentProvider
        registry.register(SinaTencentProvider())
    except Exception:
        pass


__all__ = ["ProviderRegistry", "get_registry"]