from __future__ import annotations

import time
from datetime import date
from typing import Optional

from tools.market_tools import _download_price_frame
from tools.news_tools import _fetch_news_list, _extract_news_item

COLLECTOR_TIMEOUT = 15


def _currency_for(symbol: str) -> str:
    upper = symbol.upper()
    if upper.endswith(".HK"):
        return "HKD"
    if upper.endswith(".SZ") or upper.endswith(".SS"):
        return "CNY"
    if upper.endswith(".T"):
        return "JPY"
    if upper.endswith(".L"):
        return "GBP"
    return "USD"


def collect_market_facts(symbol: str) -> list[dict]:
    today = date.today().isoformat()

    try:
        df, fetch_error = _download_price_frame(symbol)
    except Exception:
        return [
            {
                "field": "market_data_error",
                "value": True,
                "unit": "flag",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.0,
                "confidence_tier": "machine",
            }
        ]

    if df is None or df.empty:
        return []

    import pandas as pd
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()

    if len(close) < 2:
        return []

    latest = round(float(close.iloc[-1]), 2)
    prev_close = float(close.iloc[-2])
    change_pct = round((latest - prev_close) / prev_close * 100, 2)

    volume_col = df.get("Volume")
    if volume_col is not None:
        if isinstance(volume_col, pd.DataFrame):
            volume_col = volume_col.iloc[:, 0]
        avg_volume = int(volume_col.dropna().tail(20).mean()) if len(volume_col.dropna()) >= 5 else 0
    else:
        avg_volume = 0

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    rsi = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty else 0

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_val = round(float(macd_line.iloc[-1]), 4)
    macd_signal = round(float(signal_line.iloc[-1]), 4)

    returns = close.pct_change().dropna()
    volatility = round(float(returns.std() * (252 ** 0.5) * 100), 2) if len(returns) >= 5 else 0

    return [
        {
            "field": "current_price",
            "value": latest,
            "unit": _currency_for(symbol),
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.95,
            "confidence_tier": "machine",
        },
        {
            "field": "price_change_pct",
            "value": change_pct,
            "unit": "percent",
            "period": "1d",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.95,
            "confidence_tier": "machine",
        },
        {
            "field": "rsi_14",
            "value": rsi,
            "unit": "index",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.90,
            "confidence_tier": "machine",
        },
        {
            "field": "macd",
            "value": macd_val,
            "unit": "ratio",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.85,
            "confidence_tier": "machine",
        },
        {
            "field": "macd_signal",
            "value": macd_signal,
            "unit": "ratio",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.85,
            "confidence_tier": "machine",
        },
        {
            "field": "volatility_20d_annualized",
            "value": volatility,
            "unit": "percent",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.85,
            "confidence_tier": "machine",
        },
        {
            "field": "avg_volume_20d",
            "value": avg_volume,
            "unit": "shares",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.90,
            "confidence_tier": "machine",
        },
    ]


def collect_fundamental_facts(symbol: str) -> list[dict]:
    today = date.today().isoformat()
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception:
        return []

    facts = []

    def _add(field: str, value, unit: str, period: str = "latest"):
        if value is not None:
            facts.append({
                "field": field,
                "value": value,
                "unit": unit,
                "period": period,
                "source": "yfinance",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.85,
                "confidence_tier": "machine",
            })

    def _add_pct(field: str, value):
        if value is not None:
            facts.append({
                "field": field,
                "value": round(float(value) * 100, 2),
                "unit": "percent",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.85,
                "confidence_tier": "machine",
            })

    def _add_ratio(field: str, value):
        if value is not None:
            v = float(value)
            facts.append({
                "field": field,
                "value": round(v, 2) if abs(v) < 10000 else round(v, 0),
                "unit": "ratio",
                "period": "latest",
                "source": "yfinance",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.85,
                "confidence_tier": "machine",
            })

    _add("market_cap", info.get("marketCap"), _currency_for(symbol))
    _add_ratio("pe_ratio", info.get("trailingPE"))
    _add_ratio("forward_pe", info.get("forwardPE"))
    _add_ratio("pb_ratio", info.get("priceToBook"))
    _add("dividend_yield", info.get("dividendYield"), "percent")
    _add_ratio("beta", info.get("beta"))
    _add("sector", info.get("sector"), "text")
    _add("industry", info.get("industry"), "text")
    _add_pct("revenue_growth_yoy", info.get("revenueGrowth"))
    _add_pct("eps_growth_yoy", info.get("earningsGrowth"))
    _add_pct("return_on_equity", info.get("returnOnEquity"))
    _add_ratio("debt_to_equity", info.get("debtToEquity"))

    if info.get("longName"):
        facts.append({
            "field": "company_name",
            "value": info["longName"],
            "unit": "text",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 1.0,
            "confidence_tier": "machine",
        })

    return facts


def collect_news_facts(symbol: str) -> list[dict]:
    today = date.today().isoformat()
    try:
        news_list = _fetch_news_list(symbol)
    except Exception:
        return []

    if not news_list:
        return []

    clean_symbol = symbol.replace('.HK', '').replace('.SZ', '').replace('.SS', '').replace('.L', '')
    facts = []
    for item in news_list[:5]:
        n = _extract_news_item(item) if callable(_extract_news_item) else item
        title = n.get("title", "") if isinstance(n, dict) else ""
        publisher = n.get("publisher", "") if isinstance(n, dict) else ""
        link = n.get("link", "") if isinstance(n, dict) else ""
        if not title:
            continue

        title_upper = title.upper()
        symbol_in_title = (
            clean_symbol.upper() in title_upper
            or symbol.upper() in title_upper
        )
        confidence = 0.65 if symbol_in_title else 0.40

        if not symbol_in_title:
            continue

        facts.append({
            "field": "news_headline",
            "value": title,
            "unit": "text",
            "period": "latest",
            "source": publisher or "yfinance_news",
            "source_url": link or None,
            "as_of_date": today,
            "confidence": confidence,
            "confidence_tier": "llm_extracted",
        })

    return facts


_collector_cache: dict[str, tuple[dict, float]] = {}

# Per-data-type TTL in seconds. Market data goes stale fastest; fundamentals
# and filings are valid for the duration of a single process (eval run).
_collector_cache_ttl: dict[str, float] = {
    "market": 300.0,      # 5 min
    "fundamental": 3600.0,  # 1 hour (fin statements don't change intra-day)
    "news": 600.0,         # 10 min
    "filings": 7200.0,      # 2 hours
    "hkex": 7200.0,
}
_default_cache_ttl = 600.0


def collect_all(symbol: str, force_refresh: bool = False) -> dict:
    """
    Collect all available data for a symbol.

    Caches results per-symbol with per-data-type TTL to avoid redundant
    yfinance downloads during short-lived eval runs. Set force_refresh=True
    to bypass the cache entirely.

    TODO: long-term replace this process-level cache with a real Fact Store
          that uses field-level TTL and coverage checks, not just a
          similarity-threshold cold-start gate.
    """
    import time

    now = time.time()
    entry = _collector_cache.get(symbol)
    if entry is not None and not force_refresh:
        cached_data, cached_at = entry
        age = now - cached_at

        # Use the shortest TTL among populated data keys.
        populated_keys = [k for k, v in cached_data.items() if v and not k.startswith("errors")]
        effective_ttl = min(
            (_collector_cache_ttl.get(k, _default_cache_ttl) for k in populated_keys),
            default=_default_cache_ttl,
        )

        if age < effective_ttl:
            print(f"   💾 Collector cache hit for {symbol} (age={age:.0f}s, ttl={effective_ttl}s)")
            return cached_data
        else:
            print(f"   ⏳ Collector cache expired for {symbol} (age={age:.0f}s > ttl={effective_ttl}s)")
    elif entry is not None and force_refresh:
        print(f"   🔄 Force refresh for {symbol}, bypassing collector cache")

    import concurrent.futures

    results = {"market": [], "fundamental": [], "news": [], "errors": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        future_market = pool.submit(collect_market_facts, symbol)
        future_fundamental = pool.submit(collect_fundamental_facts, symbol)
        future_news = pool.submit(collect_news_facts, symbol)

        is_hk = symbol.endswith('.HK')
        is_us = not is_hk and not symbol.endswith('.SZ') and not symbol.endswith('.SS')

        future_sec = None
        future_hkex = None
        if is_us:
            future_sec = pool.submit(_collect_sec, symbol)
        if is_hk:
            future_hkex = pool.submit(_collect_hkex, symbol)

        for name, fut in [
            ("market", future_market),
            ("fundamental", future_fundamental),
            ("news", future_news),
        ]:
            try:
                results[name] = fut.result(timeout=COLLECTOR_TIMEOUT)
            except Exception as e:
                results["errors"].append(f"{name} collector failed: {e}")

        if future_sec:
            try:
                results["filings"] = future_sec.result(timeout=COLLECTOR_TIMEOUT)
            except Exception:
                pass
        else:
            results["filings"] = []

        if future_hkex:
            try:
                results["hkex"] = future_hkex.result(timeout=COLLECTOR_TIMEOUT)
            except Exception:
                pass
        else:
            results["hkex"] = []

    has_data = any(results.get(k) for k in ("market", "fundamental", "news", "filings", "hkex"))
    if has_data:
        _collector_cache[symbol] = (results, time.time())
    return results


def _collect_sec(symbol: str) -> list[dict]:
    from tools.sec_edgar_tools import collect_sec_facts
    return collect_sec_facts(symbol)


def _collect_hkex(symbol: str) -> list[dict]:
    from tools.hkex_tools import collect_hkex_facts
    return collect_hkex_facts(symbol)


__all__ = [
    "collect_market_facts",
    "collect_fundamental_facts",
    "collect_news_facts",
    "collect_all",
]