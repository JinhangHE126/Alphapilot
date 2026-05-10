import yfinance as yf
import pandas as pd
import time
from yfinance.exceptions import YFRateLimitError   # 新增
from config.proxy import get_proxy_for_agent
# from tools.rag_tools import retrieve_knowledge
# import time

# import time
# from yfinance.exceptions import YFRateLimitError



def _download_price_frame(symbol: str):
    """增强版下载函数：更长的指数退避 + jitter + 最终兜底"""
    proxy = get_proxy_for_agent("market")
    max_retries = 6                    # 增加到 6 次
    base_backoff = 8                   # 从 8 秒开始（关键！）

    for attempt in range(max_retries):
        try:
            print(f"📥 [Attempt {attempt+1}/{max_retries}] Downloading {symbol} "
                  f"(proxy: {'启用' if proxy else '直连'})...")

            if proxy:
                df = yf.download(
                    symbol,
                    period="60d",
                    progress=False,
                    proxy=proxy,
                    timeout=45,           # 适当增加超时
                )
            else:
                df = yf.download(
                    symbol,
                    period="60d",
                    progress=False,
                    timeout=45,
                )

            if df is not None and not df.empty:
                print(f"✅ 下载成功！共 {len(df)} 条记录")
                return df, ""

        except YFRateLimitError:
            backoff = base_backoff * (2 ** attempt) + random.uniform(0, 3)  # 指数退避 + jitter
            print(f"⚠️ [Attempt {attempt+1}] Yahoo Finance Rate Limit 触发，等待 {backoff:.1f} 秒后重试...")
            time.sleep(backoff)

        except Exception as exc:
            print(f"❌ [Attempt {attempt+1}] 其他错误: {exc}")
            time.sleep(3)

    # ==================== 最终兜底直连重试（更保守） ====================
    print("🔄 所有代理尝试失败，执行最终直连兜底重试...")
    for attempt in range(3):
        try:
            print(f"   → 最终尝试 {attempt+1}/3（直连）")
            df = yf.download(symbol, period="60d", progress=False, timeout=60)
            if df is not None and not df.empty:
                print(f"✅ 最终直连下载成功！共 {len(df)} 条记录")
                return df, ""
        except Exception as exc:
            print(f"   ❌ 最终尝试 {attempt+1} 失败: {exc}")
            time.sleep(5)

    return None, "all_attempts_failed"

def fetch_market_data(symbol: str) -> str:
    """获取完整技术面数据：价格 + RSI + MACD + 波动率"""
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