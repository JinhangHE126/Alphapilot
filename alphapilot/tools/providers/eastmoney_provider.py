

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import Any

import requests

from schemas.evidence_packet import Fact
from tools.providers.base import DataProvider

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_SECID_PREFIX_HK = "116"
_ZERO_INVALID_FIELDS = {"revenue", "net_profit", "eps"}


def _curl_get_json(url: str) -> dict | list | None:
    try:
        result = subprocess.run(
            ["curl", "-4", "-s", "--max-time", "15",
             "-H", f"User-Agent: {UA}", url],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def _resolve_secid_prefix(symbol: str) -> str | None:
    if symbol.endswith(".HK"):
        return _SECID_PREFIX_HK
    code = symbol.split(".")[0]
    search_url = (
        "https://searchadapter.eastmoney.com/api/suggest/get"
        f"?input={code}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
        "&marketfilter=106,105,107,116&count=3"
    )
    data = _curl_get_json(search_url)
    if not data or not isinstance(data, dict):
        return None
    items = data.get("QuotationCodeTable", {}).get("Data", [])
    if not items:
        return None
    for item in items:
        mkt = item.get("MktNum")
        if mkt:
            return str(mkt)
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "-" or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _eastmoney_push2_quote(secid: str) -> dict:
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    fields = "f43,f44,f45,f46,f47,f48,f55,f57,f58,f59,f60,f170"
    r = _curl_get_json(f"{url}?secid={secid}&fields={fields}")
    if not r or not isinstance(r.get("data"), dict):
        return {}
    d = r["data"]
    dec = d.get("f59", 3)
    divisor = 10 ** dec

    def _p(key):
        v = d.get(key)
        if v is None or v == "-":
            return None
        try:
            return round(float(v) / divisor, dec)
        except (ValueError, TypeError):
            return None

    return {
        "code": d.get("f57"),
        "name": d.get("f58"),
        "price": _p("f43"),
        "high": _p("f44"),
        "low": _p("f45"),
        "open": _p("f46"),
        "volume": d.get("f47"),
        "amount": d.get("f48"),
        "turnover_rate": d.get("f55"),
        "prev_close": _p("f60"),
        "change_pct": round(float(d["f170"]) / 100, 2) if d.get("f170") not in (None, "-") else None,
    }


class EastmoneyProvider(DataProvider):
    name = "eastmoney"
    priority = 30

    def collect_market(self, symbol: str) -> list[Fact]:
        today = date.today().isoformat()
        symbol = symbol.strip()
        is_hk = symbol.endswith(".HK")
        code = symbol.replace(".HK", "")
        if is_hk:
            code = code.zfill(5)

        prefix = _SECID_PREFIX_HK if is_hk else _resolve_secid_prefix(symbol)
        print(f"   🔍 eastmoney: symbol={symbol!r} is_hk={is_hk} prefix={prefix!r}")
        if not prefix:
            return []

        secid = f"{prefix}.{code}"
        q = _eastmoney_push2_quote(secid)
        if not q or q.get("price") is None:
            print(f"   ⚠️ eastmoney: push2 quote empty for {symbol} (secid={secid})")
            return []

        print(f"   ✅ eastmoney: push2 quote OK for {symbol} (price={q.get('price')}, name={q.get('name')})")
        unit = "HKD" if is_hk else "USD"
        source = "eastmoney_push2"

        facts: list[Fact] = []
        facts.append(Fact(
            field="current_price", value=float(q["price"]), unit=unit,
            period="latest", source=source, source_url=None,
            as_of_date=today, confidence=0.85, confidence_tier="machine",
        ))
        if q.get("change_pct") is not None:
            facts.append(Fact(
                field="price_change_pct", value=float(q["change_pct"]), unit="percent",
                period="1d", source=source, source_url=None,
                as_of_date=today, confidence=0.85, confidence_tier="machine",
            ))

        return facts

    def collect_fundamentals(self, symbol: str) -> list[Fact]:
        today = date.today().isoformat()
        symbol = symbol.strip()
        is_hk = symbol.endswith(".HK")
        code = symbol.replace(".HK", "")
        if is_hk:
            code = code.zfill(5)
        facts: list[Fact] = []

        prefix = _SECID_PREFIX_HK if is_hk else _resolve_secid_prefix(symbol)
        print(f"   🔍 eastmoney: fundamentals symbol={symbol!r} is_hk={is_hk} prefix={prefix!r}")
        if not prefix:
            return facts

        secid = f"{prefix}.{code}"

        push2_fields = "f104,f108,f109,f116,f117,f127,f160,f161,f173,f184,f185"
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={push2_fields}"
        data = _curl_get_json(url)
        if data and isinstance(data.get("data"), dict):
            d = data["data"]
            print(f"   ✅ eastmoney: push2 fundamentals OK for {symbol} ({len(d)} fields)")
            unit = "HKD" if is_hk else "USD"
            field_map = {
                "f104": ("revenue", unit),
                "f108": ("pe_ratio", "ratio"),
                "f109": ("net_profit", unit),
                "f116": ("market_cap", unit),
                "f117": ("circulating_market_cap", unit),
                "f127": ("industry", "text"),
                "f160": ("eps", unit),
                "f161": ("employee_count", "integer"),
                "f173": ("return_on_equity", "percent"),
                "f184": ("revenue_growth_yoy", "percent"),
                "f185": ("eps_growth_yoy", "percent"),
            }
            for fcode, (field_name, fu) in field_map.items():
                val = d.get(fcode)
                if val is None or val == "-" or val == "":
                    continue
                try:
                    if fu == "text":
                        parsed = str(val)
                    elif fu == "integer":
                        parsed = int(val)
                        if field_name == "employee_count" and parsed > 1_000_000:
                            continue
                    else:
                        parsed = float(val)
                        if field_name in _ZERO_INVALID_FIELDS and parsed == 0:
                            continue
                    facts.append(Fact(
                        field=field_name, value=parsed, unit=fu,
                        period="latest", source="eastmoney_push2",
                        source_url=None, as_of_date=today,
                        confidence=0.80, confidence_tier="machine",
                    ))
                except (ValueError, TypeError):
                    continue

        roe_fact = next((f for f in facts if f.field == "return_on_equity"), None)
        if roe_fact is not None:
            try:
                roe_val = float(roe_fact.value)
                if roe_val < 0.01 or roe_val > 100:
                    facts = [f for f in facts if f.field != "return_on_equity"]
            except (ValueError, TypeError):
                pass

        try:
            gma_facts = _fetch_gmaindicator(symbol, is_hk, today)
            if gma_facts:
                print(f"   ✅ eastmoney: GMAININDICATOR got {len(gma_facts)} facts for {symbol}")
            facts.extend(gma_facts)
        except Exception as e:
            print(f"   ⚠️ eastmoney: GMAININDICATOR failed for {symbol}: {e}")

        return facts

    def collect_news(self, symbol: str) -> list[Fact]:
        from tools.data_collector import collect_news_facts
        results: list[Fact] = []
        for raw in collect_news_facts(symbol):
            try:
                results.append(Fact(**raw))
            except Exception:
                continue
        return results


def _fetch_gmaindicator(symbol: str, is_hk: bool, today: str) -> list[Fact]:
    code = symbol.replace(".HK", "")
    seccode = f"{code}.HK" if is_hk else f"{code}.{'O' if code.isalpha() and len(code) <= 4 else 'N'}"
    report_name = "RPT_HK_F10_FINANCE_GMAININDICATOR" if is_hk else "RPT_USF10_FINANCE_GMAININDICATOR"
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": f'(SECUCODE="{seccode}")',
        "pageNumber": "1",
        "pageSize": "5",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        r = requests.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=params,
            headers={"User-Agent": UA},
            timeout=15,
        )
        d = r.json()
        rows = d.get("result", {}).get("data", [])
    except Exception:
        return []

    facts: list[Fact] = []
    if not rows:
        return facts

    indicator_map = {
        "ROE_AVG": ("return_on_equity", "percent"),
        "NP_GONGLY_YOY": ("eps_growth_yoy", "percent"),
        "OPER_REV_YOY": ("revenue_growth_yoy", "percent"),
        "GROSS_PROFIT_RATIO": ("gross_margin", "percent"),
        "NET_PROFIT_RATIO": ("net_margin", "percent"),
        "DEBT_ASSET_RATIO": ("debt_to_assets", "percent"),
    }

    # 第一行 = 最新期（保持现有行为）
    for key, (field_name, unit) in indicator_map.items():
        val = rows[0].get(key)
        if val is None or val == "-" or val == "":
            continue
        try:
            v = float(val)
            if v > 10000 or v < -10000:
                continue
            facts.append(Fact(
                field=field_name, value=v, unit=unit,
                period="latest", source="eastmoney_gmaindicator",
                source_url=None, as_of_date=today,
                confidence=0.75, confidence_tier="machine",
            ))
        except (ValueError, TypeError):
            continue

    return facts

