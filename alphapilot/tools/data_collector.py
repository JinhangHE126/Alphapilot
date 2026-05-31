from __future__ import annotations

from datetime import date
from typing import Optional

from tools.market_tools import _download_price_frame
from tools.news_tools import _fetch_news_list, _extract_news_item

COLLECTOR_TIMEOUT = 15


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

    latest = float(close.iloc[-1])
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
            "unit": "USD",
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

    _add("market_cap", info.get("marketCap"), "USD")
    _add("pe_ratio", info.get("trailingPE"), "ratio")
    _add("forward_pe", info.get("forwardPE"), "ratio")
    _add("pb_ratio", info.get("priceToBook"), "ratio")
    _add("dividend_yield", info.get("dividendYield"), "percent")
    _add("beta", info.get("beta"), "ratio")
    _add("sector", info.get("sector"), "text")
    _add("industry", info.get("industry"), "text")
    _add("revenue_growth_yoy", info.get("revenueGrowth"), "percent")
    _add("eps_growth_yoy", info.get("earningsGrowth"), "percent")
    _add("return_on_equity", info.get("returnOnEquity"), "percent")
    _add("debt_to_equity", info.get("debtToEquity"), "ratio")

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

    facts = []
    for item in news_list[:5]:
        n = _extract_news_item(item) if callable(_extract_news_item) else item
        title = n.get("title", "") if isinstance(n, dict) else ""
        publisher = n.get("publisher", "") if isinstance(n, dict) else ""
        link = n.get("link", "") if isinstance(n, dict) else ""
        if title:
            facts.append({
                "field": "news_headline",
                "value": title,
                "unit": "text",
                "period": "latest",
                "source": publisher or "yfinance_news",
                "source_url": link or None,
                "as_of_date": today,
                "confidence": 0.55,
                "confidence_tier": "llm_extracted",
            })

    return facts


def collect_all(symbol: str) -> dict:
    import concurrent.futures

    results = {"market": [], "fundamental": [], "news": [], "errors": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        future_market = pool.submit(collect_market_facts, symbol)
        future_fundamental = pool.submit(collect_fundamental_facts, symbol)
        future_news = pool.submit(collect_news_facts, symbol)

        try:
            results["market"] = future_market.result(timeout=COLLECTOR_TIMEOUT)
        except Exception as e:
            results["errors"].append(f"market collector failed: {e}")

        try:
            results["fundamental"] = future_fundamental.result(timeout=COLLECTOR_TIMEOUT)
        except Exception as e:
            results["errors"].append(f"fundamental collector failed: {e}")

        try:
            results["news"] = future_news.result(timeout=COLLECTOR_TIMEOUT)
        except Exception as e:
            results["errors"].append(f"news collector failed: {e}")

    return results


__all__ = [
    "collect_market_facts",
    "collect_fundamental_facts",
    "collect_news_facts",
    "collect_all",
]