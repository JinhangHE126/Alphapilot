from __future__ import annotations

from datetime import date


def try_akshare_fallback(symbol: str) -> list[dict]:
    if not symbol.endswith(".HK"):
        return []

    today = date.today().isoformat()
    code = symbol.replace(".HK", "")

    try:
        import akshare as ak
    except ImportError:
        return []

    try:
        df = ak.stock_hk_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return []

        latest = float(row["最新价"].iloc[0])
        change_pct = float(row["涨跌幅"].iloc[0])
        volume = int(row["成交量"].iloc[0]) if "成交量" in row.columns else 0

        return [
            {
                "field": "current_price",
                "value": latest,
                "unit": "HKD",
                "period": "latest",
                "source": "akshare_hk",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.85,
                "confidence_tier": "machine",
            },
            {
                "field": "price_change_pct",
                "value": change_pct,
                "unit": "percent",
                "period": "1d",
                "source": "akshare_hk",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.85,
                "confidence_tier": "machine",
            },
            {
                "field": "avg_volume_20d",
                "value": volume,
                "unit": "shares",
                "period": "latest",
                "source": "akshare_hk",
                "source_url": None,
                "as_of_date": today,
                "confidence": 0.80,
                "confidence_tier": "machine",
            },
        ]
    except Exception:
        return []


def try_hk_historical_fallback(symbol: str, days: int = 60) -> list[dict]:
    if not symbol.endswith(".HK"):
        return []

    today = date.today().isoformat()
    code = symbol.replace(".HK", "")

    try:
        import akshare as ak
    except ImportError:
        return []

    try:
        df = ak.stock_hk_hist(symbol=code, period="daily", adjust="qfq")
        if df.empty:
            return []
        df = df.tail(days)
        close = df["收盘"].astype(float)
        latest = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else latest

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = round(float(100 - 100 / (1 + rs.iloc[-1])), 1) if len(close) >= 14 else 0

        returns = close.pct_change().dropna()
        volatility = round(float(returns.std() * (252 ** 0.5) * 100), 2) if len(returns) >= 5 else 0

        return [
            {"field": "current_price", "value": latest, "unit": "HKD",
             "period": "latest", "source": "akshare_hk_hist", "source_url": None,
             "as_of_date": today, "confidence": 0.85, "confidence_tier": "machine"},
            {"field": "price_change_pct", "value": round((latest - prev) / prev * 100, 2),
             "unit": "percent", "period": "1d", "source": "akshare_hk_hist", "source_url": None,
             "as_of_date": today, "confidence": 0.85, "confidence_tier": "machine"},
            {"field": "rsi_14", "value": rsi, "unit": "index",
             "period": "latest", "source": "akshare_hk_hist", "source_url": None,
             "as_of_date": today, "confidence": 0.80, "confidence_tier": "machine"},
            {"field": "volatility_20d_annualized", "value": volatility,
             "unit": "percent", "period": "latest", "source": "akshare_hk_hist", "source_url": None,
             "as_of_date": today, "confidence": 0.80, "confidence_tier": "machine"},
        ]
    except Exception:
        return []


__all__ = ["try_akshare_fallback", "try_hk_historical_fallback"]