# /Users/yvchuan/Desktop/Projects/Alphapilot/alphapilot/tools/providers/sina_tencent_provider.py

from __future__ import annotations

import os
import re
from datetime import date

import requests

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class _ProxyAwareSession:
    def __init__(self) -> None:
        proxy = os.getenv("MARKET_PROXY", "")
        self._sess = requests.Session()
        if proxy:
            self._sess.proxies = {"http": proxy, "https": proxy}
        self._sess.trust_env = False

    def get(self, url: str, headers: dict | None = None,
            timeout: int = 15) -> requests.Response | None:
        try:
            return self._sess.get(url, headers=headers, timeout=timeout)
        except requests.RequestException:
            return None


_session = _ProxyAwareSession()


def _sina_us_quote(ticker: str) -> dict:
    url = f"https://hq.sinajs.cn/list=gb_{ticker.lower()}"
    resp = _session.get(url, headers={
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": UA,
    })
    if resp is None:
        return {}
    resp.encoding = "gbk"
    m = re.search(r'"(.+)"', resp.text)
    if not m:
        return {}
    f = m.group(1).split(",")
    if len(f) < 30:
        return {}
    return {
        "name": f[0],
        "price": float(f[1]) if f[1] else 0,
        "change_pct": float(f[2]) if f[2] else 0,
        "prev_close": float(f[26]) if f[26] else 0,
        "open": float(f[5]) if f[5] else 0,
        "high": float(f[6]) if f[6] else 0,
        "low": float(f[7]) if f[7] else 0,
        "volume": float(f[10]) if f[10] else 0,
        "high_52w": float(f[8]) if f[8] else 0,
        "low_52w": float(f[9]) if f[9] else 0,
        "market_cap": float(f[12]) if f[12] else 0,
        "eps": float(f[13]) if f[13] else 0,
        "pe": float(f[14]) if f[14] else 0,
    }


def _tencent_hk_quote(code: str) -> dict:
    url = f"https://qt.gtimg.cn/q=r_hk{code}"
    resp = _session.get(url)
    if resp is None:
        return {}
    resp.encoding = "gbk"
    m = re.search(r'"(.+)"', resp.text)
    if not m:
        return {}
    f = m.group(1).split("~")
    if len(f) < 50:
        return {}
    return {
        "name": f[1],
        "name_en": f[2],
        "price": float(f[3]) if f[3] else 0,
        "prev_close": float(f[4]) if f[4] else 0,
        "open": float(f[5]) if f[5] else 0,
        "high": float(f[33]) if f[33] else 0,
        "low": float(f[34]) if f[34] else 0,
        "volume": int(f[6]) if f[6] else 0,
        "change_pct": float(f[32]) if f[32] else 0,
        "pe": float(f[39]) if f[39] else 0,
        "pb": float(f[56]) if f[56] else 0,
        "high_52w": float(f[35]) if f[35] else 0,
        "low_52w": float(f[36]) if f[36] else 0,
        "market_cap": float(f[44]) if f[44] else 0,
    }


def _tencent_us_quote(ticker: str) -> dict:
    url = f"https://qt.gtimg.cn/q=us{ticker.upper()}"
    resp = _session.get(url)
    if resp is None:
        return {}
    resp.encoding = "gbk"
    m = re.search(r'"(.+)"', resp.text)
    if not m:
        return {}
    f = m.group(1).split("~")
    if len(f) < 50:
        return {}
    return {
        "name": f[1],
        "name_en": f[27],
        "price": float(f[3]) if f[3] else 0,
        "prev_close": float(f[4]) if f[4] else 0,
        "open": float(f[5]) if f[5] else 0,
        "volume": int(f[6]) if f[6] else 0,
        "high": float(f[33]) if f[33] else 0,
        "low": float(f[34]) if f[34] else 0,
        "change_pct": float(f[32]) if f[32] else 0,
        "market_cap": float(f[44]) if f[44] else 0,
        "pe": float(f[53]) if f[53] else 0,
        "pb": float(f[56]) if f[56] else 0,
    }


class SinaTencentProvider(DataProvider):
    name = "sina_tencent"
    priority = 35

    def __init__(self) -> None:
        try:
            import requests as _r  # noqa: F401
        except ImportError:
            self.enabled = False

    def collect_market(self, symbol: str) -> list[Fact]:
        today = date.today().isoformat()
        symbol = symbol.strip()
        print(f"   🔍 sina_tencent: collect_market symbol={symbol!r} is_hk={symbol.endswith('.HK')}")
        facts: list[Fact] = []

        if symbol.endswith(".HK"):
            code = symbol.replace(".HK", "").zfill(5)
            q = _tencent_hk_quote(code)
            if not q or q.get("price") == 0:
                print(f"   ⚠️ sina_tencent: tencent_hk quote empty for {symbol}")
                return facts
            print(f"   ✅ sina_tencent: tencent_hk got {len(q)} fields for {symbol} (price={q.get('price')})")
            facts.append(Fact(
                field="current_price", value=q["price"], unit="HKD",
                period="latest", source="tencent_hk", source_url=None,
                as_of_date=today, confidence=0.85, confidence_tier="machine",
            ))
            facts.append(Fact(
                field="price_change_pct", value=q.get("change_pct", 0), unit="percent",
                period="1d", source="tencent_hk", source_url=None,
                as_of_date=today, confidence=0.85, confidence_tier="machine",
            ))
            if q.get("pe") and q["pe"] > 0:
                facts.append(Fact(
                    field="pe_ratio", value=q["pe"], unit="ratio",
                    period="latest", source="tencent_hk", source_url=None,
                    as_of_date=today, confidence=0.80, confidence_tier="machine",
                ))
            if q.get("market_cap") and q["market_cap"] > 0:
                facts.append(Fact(
                    field="market_cap", value=q["market_cap"] * 1e8, unit="HKD",
                    period="latest", source="tencent_hk", source_url=None,
                    as_of_date=today, confidence=0.80, confidence_tier="machine",
                ))
        else:
            ticker = symbol.split(".")[0]
            sina = _sina_us_quote(ticker)
            tencent = _tencent_us_quote(ticker)
            quote = tencent if tencent.get("price") else sina
            source = "tencent_us" if tencent.get("price") else ("sina_us" if sina.get("price") else "")
            if not quote or not source:
                return facts

            facts.append(Fact(
                field="current_price", value=quote["price"], unit="USD",
                period="latest", source=source, source_url=None,
                as_of_date=today, confidence=0.85, confidence_tier="machine",
            ))
            facts.append(Fact(
                field="price_change_pct", value=quote.get("change_pct", 0), unit="percent",
                period="1d", source=source, source_url=None,
                as_of_date=today, confidence=0.85, confidence_tier="machine",
            ))
            if quote.get("pe") and quote["pe"] > 0:
                facts.append(Fact(
                    field="pe_ratio", value=quote["pe"], unit="ratio",
                    period="latest", source=source, source_url=None,
                    as_of_date=today, confidence=0.80, confidence_tier="machine",
                ))
            if quote.get("market_cap") and quote["market_cap"] > 0:
                cap = quote["market_cap"]
                if source == "tencent_us":
                    cap *= 1e8
                facts.append(Fact(
                    field="market_cap", value=cap, unit="USD",
                    period="latest", source=source, source_url=None,
                    as_of_date=today, confidence=0.80, confidence_tier="machine",
                ))

        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        return []

    def collect_news(self, symbol: str) -> list[Fact]:
        from tools.data_collector import collect_news_facts
        results: list[Fact] = []
        for raw in collect_news_facts(symbol):
            try:
                results.append(Fact(**raw))
            except Exception:
                continue
        return results