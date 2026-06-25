from __future__ import annotations

import re
import time
import os
from datetime import date
from typing import Optional
from contextlib import contextmanager

from tools.news_tools import _fetch_news_list, _extract_news_item
from tools.technical_indicators import compute_kdj, compute_bollinger
from config.proxy import get_proxy_for_agent

COLLECTOR_TIMEOUT = 15

_SUPPLEMENT_FIELDS = frozenset({
    "pe_ratio",
    "market_cap",
    "revenue_growth_yoy",
    "eps_growth_yoy",
    "news_headline",
})

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def _collect_fields(results: dict, *categories: str) -> set[str]:
    fields: set[str] = set()
    for cat in categories:
        for fact in results.get(cat, []):
            if isinstance(fact, dict) and fact.get("field"):
                fields.add(fact["field"])
    return fields


def _tencent_hk_fallback_pe_mcap(symbol: str) -> list[dict]:
    """Tertiary fallback for HK stocks: fetch pe_ratio / market_cap from Tencent quote API."""
    if not symbol.endswith(".HK"):
        return []

    import requests as _requests
    code = symbol.replace(".HK", "").zfill(5)
    url = f"https://qt.gtimg.cn/q=r_hk{code}"
    try:
        resp = _requests.get(url, timeout=10)
        resp.encoding = "gbk"
        m = re.search(r'"(.+)"', resp.text)
        if not m:
            return []
        parts = m.group(1).split("~")
        if len(parts) < 50:
            return []

        today = date.today().isoformat()
        facts: list[dict] = []

        pe = float(parts[39]) if parts[39] else 0
        mcap_raw = float(parts[44]) if parts[44] else 0

        if pe > 0:
            facts.append({
                "field": "pe_ratio",
                "value": pe,
                "unit": "ratio",
                "period": "latest",
                "source": "tencent_hk",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.80,
                "confidence_tier": "machine",
            })
        if mcap_raw > 0:
            facts.append({
                "field": "market_cap",
                "value": mcap_raw * 1e8,
                "unit": "HKD",
                "period": "latest",
                "source": "tencent_hk",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.80,
                "confidence_tier": "machine",
            })

        if facts:
            print(f"   🔄 Tencent HK fallback for {symbol}: pe={pe}, market_cap={mcap_raw}亿 HKD")
        return facts
    except Exception:
        return []


def _supplement_missing_facts(symbol: str, results: dict, registry, market: str) -> None:
    """Backfill critical fields from yfinance (and Tencent HK for HK stocks) when providers omit them."""
    present = _collect_fields(results, "market", "fundamental", "news")
    missing = _SUPPLEMENT_FIELDS - present
    if not missing:
        return

    added = False
    fund_missing = missing & {"pe_ratio", "market_cap", "revenue_growth_yoy", "eps_growth_yoy"}
    if fund_missing:
        for fact in collect_fundamental_facts(symbol):
            if fact.get("field") in fund_missing:
                results["fundamental"].append(fact)
                added = True

    # Tertiary fallback for HK stocks: Tencent quote API for pe_ratio / market_cap
    # Recompute still-missing fields after yfinance attempt
    still_missing = (
        _SUPPLEMENT_FIELDS
        - _collect_fields(results, "market", "fundamental", "news")
    ) & {"pe_ratio", "market_cap"}
    if still_missing and symbol.endswith(".HK"):
        for fact in _tencent_hk_fallback_pe_mcap(symbol):
            if fact.get("field") in still_missing:
                results["fundamental"].append(fact)
                added = True

    if "news_headline" in missing:
        news = collect_news_facts(symbol)
        if news:
            results["news"].extend(news)
            added = True

    if not added:
        return

    print(f"   🔄 Supplemental fetch for {symbol}: {sorted(missing)}")
    for category in ("market", "fundamental", "news"):
        if results.get(category):
            results[category] = registry.apply_field_priority(results[category], market)


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


@contextmanager
def _temporary_proxy_env(proxy: str | None):
    snapshot = {k: os.environ.get(k) for k in _PROXY_ENV_KEYS}
    try:
        if proxy:
            for k in _PROXY_ENV_KEYS:
                os.environ[k] = proxy
        yield
    finally:
        for k, v in snapshot.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _to_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_ticker_payload(symbol: str) -> tuple[dict, dict]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    try:
        fast_info = dict(ticker.fast_info or {})
    except Exception:
        fast_info = {}

    # Retry with configured fundamental proxy when key fields are missing.
    if info.get("marketCap") is None and info.get("trailingPE") is None:
        proxy = get_proxy_for_agent("fundamental")
        if proxy:
            with _temporary_proxy_env(proxy):
                ticker2 = yf.Ticker(symbol)
                info2 = ticker2.info or {}
                if info2:
                    info = info2
                try:
                    fast2 = dict(ticker2.fast_info or {})
                    if fast2:
                        fast_info = fast2
                except Exception:
                    pass
    return info, fast_info


def collect_market_facts(symbol: str) -> list[dict]:
    today = date.today().isoformat()

    try:
        df, fetch_error = fetch_price_history(symbol)
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

    try:
        high = df["High"]
        if isinstance(high, pd.DataFrame):
            high = high.iloc[:, 0]
        low = df["Low"]
        if isinstance(low, pd.DataFrame):
            low = low.iloc[:, 0]
        kdj_k, kdj_d, kdj_j = compute_kdj(high.dropna(), low.dropna(), close.dropna())
    except Exception:
        kdj_k, kdj_d, kdj_j = 0, 0, 0

    try:
        bb_upper, bb_mid, bb_lower = compute_bollinger(close.dropna())
    except Exception:
        bb_upper, bb_mid, bb_lower = 0, 0, 0

    returns = close.pct_change().dropna()
    volatility = round(float(returns.std() * (252 ** 0.5) * 100), 2) if len(returns) >= 5 else 0

    # 最大回撤 (从区间最高点到最低点的最大跌幅)
    max_drawdown = 0.0
    if len(close) >= 5:
        cummax = close.cummax()
        drawdown = (close - cummax) / cummax
        max_drawdown = round(float(drawdown.min() * 100), 2)  # 负值, 如 -18.5 表示跌了 18.5%

    market_facts = [
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
            "field": "max_drawdown",
            "value": abs(max_drawdown),  # 存绝对值, 前端展示为 -X% 或 X%
            "unit": "percent",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.85,
            "confidence_tier": "machine",
        },
    ]
    if avg_volume > 0:
        market_facts.append({
            "field": "avg_volume_20d",
            "value": avg_volume,
            "unit": "shares",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.90,
            "confidence_tier": "machine",
        })
    if kdj_k > 0:
        market_facts.append({
            "field": "kdj_k",
            "value": kdj_k,
            "unit": "index",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
        market_facts.append({
            "field": "kdj_d",
            "value": kdj_d,
            "unit": "index",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
        market_facts.append({
            "field": "kdj_j",
            "value": kdj_j,
            "unit": "index",
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
    if bb_mid > 0:
        market_facts.append({
            "field": "bollinger_upper",
            "value": bb_upper,
            "unit": _currency_for(symbol),
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
        market_facts.append({
            "field": "bollinger_mid",
            "value": bb_mid,
            "unit": _currency_for(symbol),
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
        market_facts.append({
            "field": "bollinger_lower",
            "value": bb_lower,
            "unit": _currency_for(symbol),
            "period": "latest",
            "source": "yfinance",
            "source_url": None,
            "as_of_date": today,
            "confidence": 0.80,
            "confidence_tier": "machine",
        })
    return market_facts


def collect_fundamental_facts(symbol: str) -> list[dict]:
    today = date.today().isoformat()
    try:
        info, fast_info = _safe_ticker_payload(symbol)
    except Exception:
        return []

    facts = []

    def _add(field: str, value, unit: str, period: str = "latest", allow_zero: bool = True):
        if value is not None:
            if not allow_zero:
                numeric = _to_float(value)
                if numeric is None or numeric == 0:
                    return
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

    def _add_pct(field: str, value, allow_zero: bool = True):
        if value is not None:
            numeric = _to_float(value)
            if numeric is None or (not allow_zero and numeric == 0):
                return
            facts.append({
                "field": field,
                "value": round(numeric * 100, 2),
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

    market_cap = _to_float(info.get("marketCap"))
    if market_cap is None:
        market_cap = _to_float(fast_info.get("market_cap"))
    if market_cap is None:
        shares = _to_float(info.get("sharesOutstanding")) or _to_float(fast_info.get("shares"))
        px = (
            _to_float(info.get("currentPrice"))
            or _to_float(info.get("regularMarketPrice"))
            or _to_float(fast_info.get("last_price"))
        )
        if shares and px:
            market_cap = shares * px
    _add("market_cap", market_cap, _currency_for(symbol))

    pe_ratio = _to_float(info.get("trailingPE"))
    if pe_ratio is None:
        pe_ratio = _to_float(fast_info.get("trailing_pe"))
    if pe_ratio is None:
        trailing_eps = _to_float(info.get("trailingEps"))
        px = (
            _to_float(info.get("currentPrice"))
            or _to_float(info.get("regularMarketPrice"))
            or _to_float(fast_info.get("last_price"))
        )
        if trailing_eps and px and trailing_eps != 0:
            pe_ratio = px / trailing_eps
    _add_ratio("pe_ratio", pe_ratio)
    _add_ratio("forward_pe", info.get("forwardPE"))
    _add_ratio("pb_ratio", info.get("priceToBook"))
    _add("dividend_yield", info.get("dividendYield"), "percent")
    _add_ratio("beta", info.get("beta"))
    _add("sector", info.get("sector"), "text")
    _add("industry", info.get("industry"), "text")
    _add("revenue", _to_float(info.get("totalRevenue")), _currency_for(symbol), allow_zero=False)
    _add(
        "net_profit",
        _to_float(info.get("netIncomeToCommon")) or _to_float(info.get("netIncome")),
        _currency_for(symbol),
        allow_zero=False,
    )
    _add("eps", _to_float(info.get("trailingEps")), _currency_for(symbol), allow_zero=False)
    _add("operating_cash_flow", _to_float(info.get("operatingCashflow")), _currency_for(symbol), allow_zero=False)
    _add("free_cash_flow", _to_float(info.get("freeCashflow")), _currency_for(symbol), allow_zero=False)
    _add("cash_position", _to_float(info.get("totalCash")), _currency_for(symbol), allow_zero=False)
    _add("total_debt", _to_float(info.get("totalDebt")), _currency_for(symbol), allow_zero=False)
    total_cash = _to_float(info.get("totalCash"))
    total_debt = _to_float(info.get("totalDebt"))
    if total_cash is not None and total_debt is not None:
        _add("net_debt", total_debt - total_cash, _currency_for(symbol))
    _add_pct("revenue_growth_yoy", info.get("revenueGrowth"), allow_zero=False)
    _add_pct("eps_growth_yoy", info.get("earningsGrowth"), allow_zero=False)
    _add_pct("net_profit_growth_yoy", info.get("earningsQuarterlyGrowth"), allow_zero=False)
    _add_pct("return_on_equity", info.get("returnOnEquity"))
    _add_pct("gross_margin", info.get("grossMargins"))
    _add_pct("operating_margin", info.get("operatingMargins"))
    _add_pct("net_margin", info.get("profitMargins"))
    _add_ratio("debt_to_equity", info.get("debtToEquity"))

    if not any(f["field"] == "pe_ratio" for f in facts):
        mcap = info.get("marketCap")
        net_income = info.get("netIncomeToCommon") or info.get("netIncome")
        try:
            if mcap and net_income and float(net_income) > 0:
                _add_ratio("pe_ratio", float(mcap) / float(net_income))
        except (TypeError, ValueError):
            pass

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
    from tools.providers.registry import get_registry

    registry = get_registry()
    enabled_providers = registry.get_enabled()

    is_hk = symbol.endswith('.HK')
    is_us = not is_hk and not symbol.endswith('.SZ') and not symbol.endswith('.SS')

    results = {"market": [], "fundamental": [], "news": [], "filings": [], "hkex": [], "errors": []}

    if enabled_providers:
        n = len(enabled_providers)
        names = ",".join(p.name for p in enabled_providers)
        print(f"   🔌 Multi-provider mode: {n} enabled ({names})")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures_map: dict = {}

            for provider in enabled_providers:
                for category in ["market", "fundamentals", "news"]:
                    method = getattr(provider, f"collect_{category}", None)
                    if method is None:
                        continue
                    key = "fundamental" if category == "fundamentals" else category
                    futures_map[pool.submit(method, symbol)] = (provider.name, key)

                if is_us and hasattr(provider, "collect_filings"):
                    futures_map[pool.submit(provider.collect_filings, symbol)] = (provider.name, "filings")

            if is_hk:
                futures_map[pool.submit(_collect_hkex, symbol)] = ("direct", "hkex")

            for fut in concurrent.futures.as_completed(futures_map):
                provider_name, category = futures_map[fut]
                try:
                    provider_results = fut.result(timeout=COLLECTOR_TIMEOUT)
                    if provider_name != "direct":
                        registry.record_result(provider_name, True)
                except Exception as e:
                    if provider_name != "direct":
                        registry.record_result(provider_name, False)
                    results["errors"].append(f"{provider_name} {category} failed: {e}")
                    continue

                if not isinstance(provider_results, list):
                    continue
                for item in provider_results:
                    try:
                        results[category].append(item.model_dump(mode="json"))
                    except AttributeError:
                        results[category].append(item)

        market = "HK" if is_hk else ("CN" if not is_us else "US")
        for category in ["market", "fundamental", "news", "filings", "hkex"]:
            if results.get(category):
                before = len(results[category])
                results[category] = registry.apply_field_priority(results[category], market)
                after = len(results[category])
                if before != after:
                    print(f"   🔍 Field-priority dedup ({category}): {before} → {after} facts")
        _supplement_missing_facts(symbol, results, registry, market)
    else:
        print(f"   ⚠️ No enabled providers, falling back to direct calls")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            future_market = pool.submit(collect_market_facts, symbol)
            future_fundamental = pool.submit(collect_fundamental_facts, symbol)
            future_news = pool.submit(collect_news_facts, symbol)

            future_sec = pool.submit(_collect_sec, symbol) if is_us else None
            future_hkex = pool.submit(_collect_hkex, symbol) if is_hk else None

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

            if future_hkex:
                try:
                    results["hkex"] = future_hkex.result(timeout=COLLECTOR_TIMEOUT)
                except Exception:
                    pass

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


def fetch_price_history(symbol: str):
    """Download raw OHLCV DataFrame for a symbol.

    Uses cache + multi-provider fallback (tiingo/polygon/eastmoney → yfinance).
    Agents that need full price series (e.g. backtesting) should call this
    instead of importing market_tools directly.
    """
    from tools.price_history import fetch_price_history as _fetch
    return _fetch(symbol)


__all__ = [
    "collect_market_facts",
    "collect_fundamental_facts",
    "collect_news_facts",
    "collect_all",
    "fetch_price_history",
]