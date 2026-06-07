from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from typing import Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

OHLCV_CACHE_TTL = 600.0
_YF_COOLDOWN_SECONDS = 120.0

_ohlcv_cache: dict[str, tuple[pd.DataFrame, float]] = {}
_yf_cooldown_until: float = 0.0


def _clean_symbol(symbol: str) -> str:
    return symbol.replace(".HK", "").replace(".SZ", "").replace(".SS", "").replace(".L", "")


def _to_ohlcv_frame(rows: list[dict], close_key: str = "close") -> Optional[pd.DataFrame]:
    if not rows:
        return None
    closes = []
    for row in rows:
        val = row.get(close_key) or row.get("Close") or row.get("adjClose")
        if val is None:
            continue
        try:
            closes.append(float(val))
        except (TypeError, ValueError):
            continue
    if len(closes) < 20:
        return None
    return pd.DataFrame({"Close": closes})


def _fetch_tiingo(symbol: str) -> Optional[pd.DataFrame]:
    api_key = os.getenv("TIINGO_API_KEY", "")
    if not api_key:
        return None
    clean = _clean_symbol(symbol)
    url = f"https://api.tiingo.com/tiingo/daily/{clean}?token={api_key}"
    req = Request(url)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, Exception):
        return None
    if not isinstance(data, list) or len(data) < 20:
        return None
    tail = data[-60:]
    return _to_ohlcv_frame(tail, close_key="adjClose")


def _fetch_polygon(symbol: str) -> Optional[pd.DataFrame]:
    api_key = os.getenv("POLYGON_API_KEY", "")
    if not api_key:
        return None
    clean = _clean_symbol(symbol)
    end = date.today()
    start = end - timedelta(days=90)
    path = (
        f"https://api.polygon.io/v2/aggs/ticker/{clean}/range/1/day/"
        f"{start.isoformat()}/{end.isoformat()}?adjusted=true&sort=asc&limit=60&apiKey={api_key}"
    )
    req = Request(path)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, json.JSONDecodeError, Exception):
        return None
    if data.get("status") != "OK":
        return None
    results = data.get("results", [])
    if len(results) < 20:
        return None
    closes = [float(r["c"]) for r in results if r.get("c") is not None]
    if len(closes) < 20:
        return None
    return pd.DataFrame({"Close": closes})


def _fetch_eastmoney_hk(symbol: str) -> Optional[pd.DataFrame]:
    if not symbol.endswith(".HK"):
        return None
    code = symbol.replace(".HK", "")
    secid = f"116.{code}"
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}"
        "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        "&klt=101&fqt=1&end=20500101&lmt=60"
    )
    try:
        from tools.providers.akshare_provider import _curl_get_json
        data = _curl_get_json(url)
    except Exception:
        return None
    if not data or not data.get("data") or not data["data"].get("klines"):
        return None
    klines = data["data"]["klines"]
    if len(klines) < 20:
        return None
    closes = []
    for k in klines:
        parts = k.split(",")
        if len(parts) > 2:
            try:
                closes.append(float(parts[2]))
            except ValueError:
                continue
    if len(closes) < 20:
        return None
    return pd.DataFrame({"Close": closes})


def _fetch_yfinance(symbol: str) -> tuple[Optional[pd.DataFrame], str]:
    global _yf_cooldown_until
    if time.time() < _yf_cooldown_until:
        remaining = int(_yf_cooldown_until - time.time())
        print(f"   ⏸️ yfinance cooldown active ({remaining}s), skipping download")
        return None, "yfinance_cooldown"

    from tools.market_tools import _download_price_frame_fast

    df, err = _download_price_frame_fast(symbol)
    if err == "rate_limited":
        _yf_cooldown_until = time.time() + _YF_COOLDOWN_SECONDS
        print(f"   ⏸️ yfinance rate-limited, cooldown {_YF_COOLDOWN_SECONDS}s for all symbols")
    if df is not None and not df.empty:
        return df, ""
    return None, err or "yfinance_failed"


def fetch_price_history(symbol: str) -> tuple[Optional[pd.DataFrame], str]:
    """Fetch OHLCV history with cache + multi-provider fallback.

    Order:
      HK  → eastmoney → yfinance
      US  → tiingo → polygon → yfinance
      CN  → yfinance (tushare daily series TBD)
    """
    now = time.time()
    cached = _ohlcv_cache.get(symbol)
    if cached is not None:
        df, cached_at = cached
        if now - cached_at < OHLCV_CACHE_TTL:
            print(f"   💾 OHLCV cache hit for {symbol} (age={int(now - cached_at)}s)")
            return df.copy(), ""

    is_hk = symbol.endswith(".HK")
    providers: list[tuple[str, Callable]] = []
    if is_hk:
        providers.append(("eastmoney", lambda: _fetch_eastmoney_hk(symbol)))
    else:
        providers.append(("tiingo", lambda: _fetch_tiingo(symbol)))
        providers.append(("polygon", lambda: _fetch_polygon(symbol)))
    providers.append(("yfinance", lambda: _fetch_yfinance(symbol)))

    last_err = "no_provider"
    for name, fetcher in providers:
        if name == "yfinance":
            df, err = fetcher()
        else:
            df = fetcher()
            err = "" if df is not None else f"{name}_empty"
        if df is not None and not df.empty and len(df) >= 20:
            print(f"   ✅ OHLCV from {name} for {symbol} ({len(df)} rows)")
            _ohlcv_cache[symbol] = (df.copy(), now)
            return df, ""
        if err:
            last_err = err
            if name != "yfinance":
                print(f"   ⚠️ OHLCV {name} miss for {symbol}")

    return None, last_err


__all__ = ["fetch_price_history"]
