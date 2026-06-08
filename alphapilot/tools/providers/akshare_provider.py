from __future__ import annotations

import json
import os
import subprocess
from datetime import date

import pandas as pd
import requests

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider


def _curl_get_json(url: str) -> dict | list | None:
    try:
        result = subprocess.run(
            ["curl", "-4", "-s", "--max-time", "15",
             "-H", "User-Agent: Mozilla/5.0", url],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


class _ProxyAwareSession:
    """requests-based session that routes through MARKET_PROXY if set."""

    def __init__(self) -> None:
        proxy = os.getenv("MARKET_PROXY", "")
        self._sess = requests.Session()
        if proxy:
            self._sess.proxies = {"http": proxy, "https": proxy}
        self._sess.trust_env = False

    def get_json(self, url: str) -> dict | list | None:
        try:
            r = self._sess.get(url, timeout=15,
                               headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            return _curl_get_json(url)


def _compute_hk_yoy_growth(code: str, today: str) -> list:
    """Compute revenue_growth_yoy and eps_growth_yoy for HK stocks.

    Uses akshare's stock_hk_financial_indicator_em (multi-period financial data)
    to compare latest two annual periods. Only called when push2 f184/f185 fields
    in collect_fundamentals are empty.
    """
    facts: list = []

    try:
        import akshare as ak
    except ImportError:
        return []

    try:
        df = ak.stock_hk_financial_indicator_em(symbol=code)
    except Exception as exc:
        print(f"   ⚠️ YoY akshare fallback failed for {code}: {exc}")
        return []

    if df is None or df.empty or len(df) < 2:
        return []

    cols_lower = {str(c).lower(): str(c) for c in df.columns}
    date_col = None
    for c in cols_lower:
        if any(kw in c for kw in ('日期', 'date', '报告期', 'report')):
            date_col = cols_lower[c]
            break
    if date_col and date_col in df.columns:
        df = df.sort_values(date_col)

    revenue_col = None
    eps_col = None
    for low, orig in cols_lower.items():
        if revenue_col is None:
            if ('营业' in low and ('收入' in low or '营收' in low)) or ('revenue' in low and 'total' in low) or low == 'revenue':
                revenue_col = orig
        if eps_col is None:
            if ('每股收益' in low) or ('basic' in low and 'eps' in low):
                eps_col = orig

    if revenue_col is None and eps_col is None:
        print(f"   ⚠️ YoY akshare column match failed for {code}: {list(df.columns)[:8]}")
        return []

    for col_name, field_name in [(revenue_col, "revenue_growth_yoy"), (eps_col, "eps_growth_yoy")]:
        if col_name is None or col_name not in df.columns:
            continue
        series = df[col_name].dropna()
        if len(series) < 2:
            continue
        try:
            latest = float(series.iloc[-1])
            prev = float(series.iloc[-2])
        except (ValueError, TypeError):
            continue
        if prev <= 0:
            continue
        growth = round((latest - prev) / prev * 100, 1)
        facts.append(Fact(
            field=field_name, value=growth, unit="percent",
            period="latest", source="akshare", source_url=None,
            as_of_date=today, confidence=0.75, confidence_tier="machine",
        ))

    if facts:
        print(f"   ✅ YoY growth from akshare for {code}: {[(f.field, f.value) for f in facts]}")

    return facts


class AKShareProvider(DataProvider):
    name = "akshare"
    priority = 90

    def __init__(self) -> None:
        try:
            import akshare  # noqa: F401
        except ImportError:
            self.enabled = False

    def collect_market(self, symbol: str) -> list[Fact]:
        if not symbol.endswith(".HK"):
            return []

        today = date.today().isoformat()
        code = symbol.replace(".HK", "").zfill(5)
        facts = []

        fs = "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2"
        fields = "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
        url = f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs={fs}&fields={fields}"
        data = _curl_get_json(url)
        if data and data.get("data") and data["data"].get("diff"):
            for row in data["data"]["diff"]:
                if row.get("f12") == code:
                    try:
                        facts.append(Fact(
                            field="current_price", value=float(row["f2"]), unit="HKD",
                            period="latest", source="akshare_hk", source_url=None,
                            as_of_date=today, confidence=0.85, confidence_tier="machine",
                        ))
                        facts.append(Fact(
                            field="price_change_pct", value=float(row["f3"]), unit="percent",
                            period="1d", source="akshare_hk", source_url=None,
                            as_of_date=today, confidence=0.85, confidence_tier="machine",
                        ))
                        facts.append(Fact(
                            field="avg_volume_20d", value=int(row.get("f5", 0)), unit="shares",
                            period="latest", source="akshare_hk", source_url=None,
                            as_of_date=today, confidence=0.80, confidence_tier="machine",
                        ))
                    except (ValueError, KeyError):
                        pass
                    break

        secid = f"116.{code}"
        hist_url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=60"
        hist_data = _curl_get_json(hist_url)
        if hist_data and hist_data.get("data") and hist_data["data"].get("klines"):
            klines = hist_data["data"]["klines"]
            if len(klines) >= 2:
                parts = klines[-1].split(",")
                prev_parts = klines[-2].split(",")
                try:
                    latest_close = float(parts[2])
                    prev_close = float(prev_parts[2])
                    change = round((latest_close - prev_close) / prev_close * 100, 2)
                    facts.append(Fact(
                        field="current_price", value=latest_close, unit="HKD",
                        period="latest", source="akshare_hk_hist", source_url=None,
                        as_of_date=today, confidence=0.85, confidence_tier="machine",
                    ))
                    facts.append(Fact(
                        field="price_change_pct", value=change, unit="percent",
                        period="1d", source="akshare_hk_hist", source_url=None,
                        as_of_date=today, confidence=0.85, confidence_tier="machine",
                    ))

                    closes = [float(k.split(",")[2]) for k in klines[-20:]]
                    if len(closes) >= 5:
                        returns = pd.Series(closes).pct_change().dropna()
                        vol = round(float(returns.std() * (252 ** 0.5) * 100), 2)
                        facts.append(Fact(
                            field="volatility_20d_annualized", value=vol, unit="percent",
                            period="latest", source="akshare_hk_hist", source_url=None,
                            as_of_date=today, confidence=0.80, confidence_tier="machine",
                        ))
                    if len(closes) >= 14:
                        delta = pd.Series(closes).diff()
                        gain = delta.clip(lower=0).rolling(14).mean()
                        loss = (-delta.clip(upper=0)).rolling(14).mean()
                        rs = gain / loss.replace(0, 1e-9)
                        rsi = round(float(100 - 100 / (1 + rs.iloc[-1])), 1)
                        facts.append(Fact(
                            field="rsi_14", value=rsi, unit="index",
                            period="latest", source="akshare_hk_hist", source_url=None,
                            as_of_date=today, confidence=0.80, confidence_tier="machine",
                        ))
                    volumes = []
                    for k in klines[-20:]:
                        parts_v = k.split(",")
                        if len(parts_v) > 5:
                            try:
                                vol = float(parts_v[5])
                                if vol > 0:
                                    volumes.append(vol)
                            except ValueError:
                                continue
                    if volumes:
                        avg_vol = int(sum(volumes) / len(volumes))
                        facts = [f for f in facts if f.field != "avg_volume_20d"]
                        facts.append(Fact(
                            field="avg_volume_20d", value=avg_vol, unit="shares",
                            period="latest", source="akshare_hk_hist", source_url=None,
                            as_of_date=today, confidence=0.80, confidence_tier="machine",
                        ))
                except (ValueError, IndexError):
                    pass

        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        if not symbol.endswith(".HK"):
            return []

        today = date.today().isoformat()
        code = symbol.replace(".HK", "").zfill(5)
        facts = []

        secid = f"116.{code}"
        fields = "f104,f108,f109,f116,f117,f127,f160,f161,f173,f184,f185"
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}"
        data = _curl_get_json(url)
        if not data or not isinstance(data.get("data"), dict):
            return facts

        d = data["data"]
        field_map = {
            "f104": ("revenue", "HKD"),
            "f108": ("pe_ratio", "ratio"),
            "f109": ("net_profit", "HKD"),
            "f116": ("market_cap", "HKD"),
            "f117": ("circulating_market_cap", "HKD"),
            "f127": ("industry", "text"),
            "f160": ("eps", "HKD"),
            "f161": ("employee_count", "integer"),
            "f173": ("return_on_equity", "percent"),
            "f184": ("revenue_growth_yoy", "percent"),
            "f185": ("eps_growth_yoy", "percent"),
        }
        for fcode, (field_name, unit) in field_map.items():
            val = d.get(fcode)
            if val is None or val == "-" or val == "":
                continue
            try:
                if unit == "integer":
                    parsed = int(val)
                    if field_name == "employee_count" and parsed > 1_000_000:
                        continue
                elif unit == "text":
                    parsed = str(val)
                else:
                    parsed = float(val)
                facts.append(Fact(
                    field=field_name,
                    value=parsed,
                    unit=unit,
                    period="latest",
                    source="akshare_hk",
                    source_url=None,
                    as_of_date=today,
                    confidence=0.85,
                    confidence_tier="machine",
                ))
            except (ValueError, TypeError):
                continue

        pe_fact = next((f for f in facts if f.field == "pe_ratio"), None)
        mcap_fact = next((f for f in facts if f.field == "market_cap"), None)
        np_fact = next((f for f in facts if f.field == "net_profit"), None)
        def _append_derived_pe(pe_value: float, source: str) -> None:
            nonlocal facts
            facts = [f for f in facts if f.field != "pe_ratio"]
            facts.append(Fact(
                field="pe_ratio",
                value=round(pe_value, 2),
                unit="ratio",
                period="latest",
                source=source,
                source_url=None,
                as_of_date=today,
                confidence=0.75,
                confidence_tier="machine",
            ))

        if mcap_fact and np_fact and float(np_fact.value) > 0:
            try:
                pe_derived = float(mcap_fact.value) / float(np_fact.value)
                if pe_fact:
                    pe_raw = float(pe_fact.value)
                    if pe_raw > 0 and pe_derived > 0:
                        deviation = abs(pe_raw - pe_derived) / max(pe_raw, pe_derived)
                        if deviation > 0.5:
                            print(
                                f"   ⚠️ AKShare PE={pe_raw} vs derived={pe_derived:.1f} "
                                f"(dev={deviation:.0%}), using derived PE"
                            )
                            _append_derived_pe(pe_derived, "akshare_hk_derived")
                elif pe_derived > 0:
                    _append_derived_pe(pe_derived, "akshare_hk_derived")
            except (ValueError, TypeError):
                pass
        roe_fact = next((f for f in facts if f.field == "return_on_equity"), None)
        if roe_fact is not None:
            try:
                roe_val = float(roe_fact.value)
                if roe_val < 0.01 or roe_val > 100:
                    print(f"   ⚠️ AKShare ROE={roe_val} out of plausible range (0.01-100), dropping")
                    facts = [f for f in facts if f.field != "return_on_equity"]
            except (ValueError, TypeError):
                pass

        facts.extend(_compute_hk_yoy_growth(code, today))

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        if not symbol.endswith(".HK"):
            from tools.data_collector import collect_news_facts
            results: list[Fact] = []
            for raw in collect_news_facts(symbol):
                try:
                    results.append(Fact(**raw))
                except Exception:
                    continue
            return results

        today = date.today().isoformat()
        code = symbol.replace(".HK", "").zfill(5)
        facts: list[Fact] = []

        try:
            import akshare as ak
            df = ak.stock_hk_news_em(symbol=code)
        except Exception:
            return facts

        if df is None or df.empty:
            return facts

        for _, row in df.head(5).iterrows():
            try:
                title = str(row.get("标题", row.get("title", "")))
                if not title or title == "nan":
                    continue
                pub_time = str(row.get("发布时间", row.get("pub_time", "")))
                url = str(row.get("新闻链接", row.get("url", "")))
                source = str(row.get("来源", row.get("source", "akshare_hk_news")))
                facts.append(Fact(
                    field="news_headline", value=title,
                    unit="text", period="latest",
                    source=f"akshare_hk|{source}" if source else "akshare_hk",
                    source_url=url if url and url != "nan" else None,
                    as_of_date=pub_time[:10] if pub_time and pub_time != "nan" else today,
                    confidence=0.65, confidence_tier="llm_extracted",
                ))
            except Exception:
                continue

        return facts