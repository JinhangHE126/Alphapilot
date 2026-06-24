# =============================================================================
# INTERNAL USE ONLY — do not import from agents/
# All data access from agents MUST go through tools/data_collector.py
# or tools/providers/ (via ProviderRegistry). Direct imports of this module
# from alphapilot/agents/ will be caught by CI.
# =============================================================================

import yfinance as yf
import pandas as pd
import time
import random
import os
from contextlib import contextmanager
from yfinance.exceptions import YFRateLimitError
from config.proxy import get_proxy_for_agent



_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@contextmanager
def _temporary_proxy_env(proxy: str | None):
    snapshot = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
    try:
        if proxy:
            for key in _PROXY_ENV_KEYS:
                os.environ[key] = str(proxy)
        yield
    finally:
        for key, value in snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _without_proxy_env():
    snapshot = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
    try:
        for key in _PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _safe_yf_download(symbol: str, **kwargs):
    """Compat wrapper for yfinance versions without `proxy` kwarg support."""
    proxy = kwargs.get("proxy")
    kwargs_no_proxy = {k: v for k, v in kwargs.items() if k != "proxy"}

    def _is_empty_frame(df) -> bool:
        return df is None or getattr(df, "empty", False)

    def _direct_fallback():
        print("   ⚠️ yfinance 代理请求无结果，尝试直连兜底")
        with _without_proxy_env():
            return yf.download(symbol, **kwargs_no_proxy)

    try:
        result = yf.download(symbol, **kwargs)
        if proxy and _is_empty_frame(result):
            return _direct_fallback()
        return result
    except TypeError as exc:
        msg = str(exc)
        if "unexpected keyword argument" in msg and "proxy" in msg and "proxy" in kwargs:
            print("   ⚠️ yfinance 当前版本不支持 proxy 参数，改用环境变量代理重试")
            try:
                with _temporary_proxy_env(str(proxy) if proxy else None):
                    result = yf.download(symbol, **kwargs_no_proxy)
                if proxy and _is_empty_frame(result):
                    return _direct_fallback()
                return result
            except Exception as retry_exc:
                if proxy:
                    print("   ⚠️ 代理重试失败，尝试直连兜底")
                    with _without_proxy_env():
                        return yf.download(symbol, **kwargs_no_proxy)
                raise retry_exc
        raise
    except Exception:
        if proxy:
            print("   ⚠️ yfinance 代理请求失败，尝试直连兜底")
            with _without_proxy_env():
                return yf.download(symbol, **kwargs_no_proxy)
        raise


def _download_price_frame(symbol: str):
    """下载价格数据：港股尝试多种 symbol 格式，较少重试，快速失败。"""
    proxy = get_proxy_for_agent("market")
    max_retries = 2
    base_backoff = 5

    is_hk = symbol.endswith('.HK')
    candidates = [symbol]
    if is_hk:
        core = symbol.split('.')[0].lstrip('0') or '0'
        stripped = f"{core}.HK"
        if stripped != symbol:
            candidates.append(stripped)

    def _try_download(sym: str, use_proxy: str | None) -> tuple:
        for attempt in range(max_retries):
            try:
                print(f"📥 [Attempt {attempt+1}/{max_retries}] Downloading {sym} "
                      f"(proxy: {'启用' if use_proxy else '直连'})...")

                kwargs = {"period": "60d", "progress": False, "timeout": 30}
                if use_proxy:
                    kwargs["proxy"] = use_proxy
                df = _safe_yf_download(sym, **kwargs)

                if df is not None and not df.empty:
                    print(f"✅ 下载成功！共 {len(df)} 条记录")
                    return df, ""

            except YFRateLimitError:
                backoff = base_backoff * (2 ** attempt) + random.uniform(0, 2)
                print(f"⚠️ [Attempt {attempt+1}] Rate Limit，等待 {backoff:.1f}s...")
                time.sleep(backoff)
            except Exception as exc:
                print(f"❌ [Attempt {attempt+1}] 错误: {exc}")
                time.sleep(2)
        return None, ""

    for sym in candidates:
        if sym != candidates[0]:
            print(f"   🔄 尝试替代格式: {sym}")

        df, err = _try_download(sym, proxy)
        if df is not None and not df.empty:
            return df, ""

        if proxy:
            df, err = _try_download(sym, None)
            if df is not None and not df.empty:
                return df, ""

        if is_hk:
            try:
                print(f"   🔄 港股 {sym} 尝试 1y 周期...")
                kwargs = {"period": "1y", "progress": False, "timeout": 30}
                df = _safe_yf_download(sym, **kwargs)
                if df is not None and not df.empty:
                    print(f"✅ 1y 周期下载成功！共 {len(df)} 条记录")
                    return df, ""
            except Exception:
                pass

    print(f"🔄 最终直连兜底重试...")
    for attempt in range(1):
        for sym in candidates[:1]:
            try:
                print(f"   → 最终尝试 (直连) {sym}")
                df = _safe_yf_download(sym, period="60d", progress=False, timeout=30)
                if df is not None and not df.empty:
                    print(f"✅ 直连下载成功！共 {len(df)} 条记录")
                    return df, ""
            except Exception as exc:
                print(f"   ❌ 失败: {exc}")
                time.sleep(3)

    return None, "all_attempts_failed"


def _download_price_frame_fast(symbol: str):
    """Single-attempt yfinance download for OHLCV fallback. Fails fast on rate limit."""
    proxy = get_proxy_for_agent("market")
    candidates = [symbol]
    if symbol.endswith(".HK"):
        core = symbol.split(".")[0].lstrip("0") or "0"
        stripped = f"{core}.HK"
        if stripped != symbol:
            candidates.append(stripped)

    try:
        for sym in candidates:
            kwargs = {"period": "60d", "progress": False, "timeout": 30}
            if proxy:
                kwargs["proxy"] = proxy
            print(f"📥 [fast] Downloading {sym} (proxy: {'启用' if proxy else '直连'})...")
            df = _safe_yf_download(sym, **kwargs)
            if df is not None and not df.empty:
                print(f"✅ [fast] 下载成功！共 {len(df)} 条记录")
                return df, ""
    except YFRateLimitError:
        print(f"⚠️ [fast] Rate Limit for {symbol}, skipping retries")
        return None, "rate_limited"
    except Exception as exc:
        print(f"❌ [fast] 错误: {exc}")
        return None, str(exc)

    return None, "empty"


import warnings

def fetch_market_data(symbol: str) -> str:
    """[DEPRECATED] 获取完整技术面数据：价格 + RSI + MACD + 波动率

    所有 Agent 应通过 tools.data_collector.fetch_price_history() 获取 OHLCV，
    或消费 Evidence Packet 中的结构化 Fact。本函数将在后续版本移除。
    """
    warnings.warn(
        "fetch_market_data is deprecated. Use tools.data_collector.fetch_price_history() "
        "or consume Evidence Packet facts instead.",
        DeprecationWarning, stacklevel=2,
    )
    try:
        df, fetch_error = _download_price_frame(symbol)
        if df is None or df.empty:
            if fetch_error:
                return f"Failed to fetch data for {symbol}. Details: {fetch_error}"
            return f"Failed to fetch data for {symbol}"

        close = df["Close"]
        volume = df["Volume"] if "Volume" in df.columns else None

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if volume is not None and isinstance(volume, pd.DataFrame):
            volume = volume.iloc[:, 0]

        close = close.dropna()
        if volume is not None:
            volume = volume.dropna()

        if len(close) < 2:
            return f"Not enough price data for {symbol}"

        latest = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1])

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()

        macd_latest = float(macd_line.iloc[-1])
        signal_latest = float(signal_line.iloc[-1])
        macd_histogram = macd_latest - signal_latest

        returns = close.pct_change()
        volatility = float(returns.rolling(window=20).std().iloc[-1] * 100)

        five_day_change = (
            (latest / float(close.iloc[-6]) - 1) * 100
            if len(close) > 5
            else 0.0
        )

        latest_volume = float(volume.iloc[-1]) if volume is not None and len(volume) > 0 else 0.0

        result = f"""
        [{symbol} Technical Analysis Report]
        Current Price: {latest:.2f} (Change: {(latest - prev_close) / prev_close * 100:+.2f}%)
        Latest Volume: {latest_volume:,.0f}
        RSI(14): {rsi:.1f} {'(Overbought)' if rsi > 70 else '(Oversold)' if rsi < 30 else '(Neutral)'}
        MACD: {macd_latest:.4f} (Signal: {signal_latest:.4f}, Histogram: {macd_histogram:+.4f})
        20-Day Volatility: {volatility:.2f}%
        5-Day Change: {five_day_change:+.2f}%

        Summary: {get_technical_summary(rsi, macd_histogram, volatility)}
        """
        return result.strip()

    except Exception as e:
        return f"Data fetch failed: {str(e)}"

def get_technical_summary(rsi: float, macd_hist: float, vol: float) -> str:
    if rsi > 70 and macd_hist < 0:
        return "Overbought, short-term pullback risk"
    elif rsi < 30 and macd_hist > 0:
        return "Oversold, high rebound probability"
    elif macd_hist > 0:
        return "MACD bullish crossover, upward trend"
    else:
        return "Sideways movement, wait and see"