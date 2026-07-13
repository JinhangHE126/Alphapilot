#!/usr/bin/env python3
"""Export Week 2 Day 4 G2 screenshots (report + structured facts panel)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import markdown


REPO_ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets/stimuli"
ASSETS_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets"
MANIFEST_PATH = STIMULI_DIR / "stimuli_manifest.json"
WINDOW_SIZE = "1400,4200"

FACTS_FALLBACK = REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S2_002_20260713_160524.json"

STIMULI = [
    ("S1", "S1_news_clean.md", "G2_S1.html", "G2_S1.png", "ATT_S2_002"),
    ("S2", "S2_news_attacked.md", "G2_S2.html", "G2_S2.png", "ATT_S2_002"),
    ("S3", "S3_filing_clean.md", "G2_S3.html", "G2_S3.png", "ATT_S4_002"),
    ("S4", "S4_filing_attacked.md", "G2_S4.html", "G2_S4.png", "ATT_S4_002"),
]

RUN_JSON = {
    "ATT_S2_002": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S2_002_20260713_160524.json",
    "ATT_S4_002": REPO_ROOT / "Docs/demo/AAPL_analysis_ATT_S4_002_20260713_161637.json",
}

DISPLAY_FIELDS = {
    "revenue", "total_revenue", "net_profit", "net_income", "eps", "eps_basic", "trailing_eps",
    "operating_cash_flow", "operating_cashflow", "free_cash_flow", "free_cashflow",
    "cash_position", "total_cash", "total_debt", "net_debt",
    "revenue_growth_yoy", "net_profit_growth_yoy", "net_income_growth_yoy", "eps_growth_yoy",
    "gross_margin", "operating_margin", "net_margin", "return_on_equity", "roe",
    "debt_to_assets", "debt_to_equity", "current_price", "pe_ratio", "pb_ratio",
    "forward_pe", "volatility_20d_annualized",
}


def resolve_chrome_binary() -> str:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Google Chrome binary not found for headless screenshot export")


def to_number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


def find_fact(facts: list[dict], fields: list[str]) -> dict | None:
    for fact in facts:
        if fact.get("field") in fields and to_number(fact.get("value")) is not None:
            return fact
    return None


def find_nonzero_fact(facts: list[dict], fields: list[str]) -> dict | None:
    for fact in facts:
        value = to_number(fact.get("value"))
        if fact.get("field") in fields and value not in (None, 0):
            return fact
    return None


def growth_text(value: float | None) -> str | None:
    if value is None or value == 0:
        return None
    sign = "+" if value > 0 else ""
    return f"同比 {sign}{value:.2f}%"


def format_currency(value: float | None, unit: str | None = None) -> str:
    if value is None:
        return ""
    currency = unit if unit and unit not in {"number", "ratio", "percent"} else ""
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{currency} {(value / 1_000_000_000):.2f}B".strip()
    if abs_val >= 1_000_000:
        return f"{currency} {(value / 1_000_000):.2f}M".strip()
    if abs_val >= 1_000:
        return f"{currency} {(value / 1_000):.2f}K".strip()
    return f"{currency} {value:.2f}".strip()


def format_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}%"


def compute_health_score(values: dict[str, float | None]) -> int | None:
    signals: list[float] = []
    net_margin = values.get("net_margin")
    roe = values.get("roe")
    operating_cash_flow = values.get("operating_cash_flow")
    free_cash_flow = values.get("free_cash_flow")
    debt_to_equity = values.get("debt_to_equity")
    cash_position = values.get("cash_position")
    total_debt = values.get("total_debt")

    if net_margin is not None:
        signals.append(1 if net_margin > 0 else 0)
    if roe is not None:
        signals.append(1 if roe > 0 else 0)
    if operating_cash_flow is not None:
        signals.append(1 if operating_cash_flow > 0 else 0)
    if free_cash_flow is not None:
        signals.append(1 if free_cash_flow > 0 else 0)
    if debt_to_equity is not None:
        if debt_to_equity < 100:
            signals.append(1)
        elif debt_to_equity < 200:
            signals.append(0.5)
        else:
            signals.append(0)
    if cash_position is not None and total_debt is not None and total_debt > 0:
        signals.append(1 if cash_position / total_debt >= 1 else 0.4)

    if len(signals) < 3:
        return None
    return round(sum(signals) / len(signals) * 100)


def load_facts(run_key: str) -> list[dict]:
    path = RUN_JSON.get(run_key, FACTS_FALLBACK)
    data = json.loads(path.read_text(encoding="utf-8"))
    guard = data.get("guard_full") or data.get("guard_check") or {}
    packet = guard.get("evidence_packet") or data.get("evidence_packet") or {}
    return packet.get("facts") or []


def metric_card(label: str, value: str, sub: str | None, tone: str, source: str | None) -> str:
    sub_html = f'<span class="fin-metric-sub {tone}">{sub}</span>' if sub else ""
    source_html = f'<span class="fin-metric-source">源: {source}</span>' if source else ""
    return (
        f'<div class="fin-metric-card {tone}">'
        f'<div class="fin-metric-icon">◆</div>'
        f'<div class="fin-metric-body"><span class="fin-metric-label">{label}</span>'
        f'<span class="fin-metric-value">{value}</span>{sub_html}{source_html}</div></div>'
    )


def gauge(label: str, value: float) -> str:
    width = max(0, min(100, abs(value)))
    color = "rgba(34, 197, 94, 0.7)" if value >= 0 else "rgba(248, 113, 113, 0.7)"
    return (
        f'<div class="fin-gauge"><div class="fin-gauge-header">'
        f'<span class="fin-gauge-label">{label}</span>'
        f'<span class="fin-gauge-value">{value:.2f}%</span></div>'
        f'<div class="fin-gauge-bar-wrap"><div class="fin-gauge-bar" style="width:{width}%;background:{color}"></div></div></div>'
    )


def health_item(label: str, value: str, tone: str = "neutral") -> str:
    return (
        f'<div class="fin-health-item {tone}"><span class="fin-health-label">{label}</span>'
        f'<span class="fin-health-value">{value}</span></div>'
    )


def build_facts_panel_html(facts: list[dict]) -> str:
    revenue_fact = find_nonzero_fact(facts, ["revenue", "revenue_ttm", "total_revenue"])
    net_profit_fact = find_nonzero_fact(facts, ["net_profit", "net_income"])
    eps_fact = find_nonzero_fact(facts, ["eps", "eps_basic", "trailing_eps"])
    operating_cash_flow_fact = find_nonzero_fact(facts, ["operating_cash_flow", "operating_cashflow"])
    free_cash_flow_fact = find_nonzero_fact(facts, ["free_cash_flow", "free_cashflow"])
    cash_position_fact = find_nonzero_fact(facts, ["cash_position", "total_cash"])
    total_debt_fact = find_nonzero_fact(facts, ["total_debt"])
    net_debt_fact = find_fact(facts, ["net_debt"])
    revenue_growth_fact = find_fact(facts, ["revenue_growth_yoy"])
    net_profit_growth_fact = find_fact(facts, ["net_profit_growth_yoy", "net_income_growth_yoy"])
    eps_growth_fact = find_fact(facts, ["eps_growth_yoy"])
    gross_margin_fact = find_fact(facts, ["gross_margin"])
    operating_margin_fact = find_fact(facts, ["operating_margin"])
    net_margin_fact = find_fact(facts, ["net_margin"])
    roe_fact = find_fact(facts, ["return_on_equity", "roe"])
    debt_to_assets_fact = find_fact(facts, ["debt_to_assets"])
    debt_to_equity_fact = find_fact(facts, ["debt_to_equity"])
    current_price_fact = find_fact(facts, ["current_price"])
    pe_fact = find_fact(facts, ["pe_ratio"])
    pb_fact = find_fact(facts, ["pb_ratio"])
    forward_pe_fact = find_fact(facts, ["forward_pe"])
    vol_fact = find_fact(facts, ["volatility_20d_annualized"])

    revenue = to_number(revenue_fact.get("value")) if revenue_fact else None
    net_profit = to_number(net_profit_fact.get("value")) if net_profit_fact else None
    eps = to_number(eps_fact.get("value")) if eps_fact else None
    operating_cash_flow = to_number(operating_cash_flow_fact.get("value")) if operating_cash_flow_fact else None
    free_cash_flow = to_number(free_cash_flow_fact.get("value")) if free_cash_flow_fact else None
    cash_position = to_number(cash_position_fact.get("value")) if cash_position_fact else None
    total_debt = to_number(total_debt_fact.get("value")) if total_debt_fact else None
    net_debt = to_number(net_debt_fact.get("value")) if net_debt_fact else None
    revenue_growth = to_number(revenue_growth_fact.get("value")) if revenue_growth_fact else None
    net_profit_growth = to_number(net_profit_growth_fact.get("value")) if net_profit_growth_fact else None
    eps_growth = to_number(eps_growth_fact.get("value")) if eps_growth_fact else None
    gross_margin = to_number(gross_margin_fact.get("value")) if gross_margin_fact else None
    operating_margin = to_number(operating_margin_fact.get("value")) if operating_margin_fact else None
    net_margin = to_number(net_margin_fact.get("value")) if net_margin_fact else None
    roe = to_number(roe_fact.get("value")) if roe_fact else None
    debt_to_assets = to_number(debt_to_assets_fact.get("value")) if debt_to_assets_fact else None
    debt_to_equity = to_number(debt_to_equity_fact.get("value")) if debt_to_equity_fact else None
    current_price = to_number(current_price_fact.get("value")) if current_price_fact else None
    pe_ratio = to_number(pe_fact.get("value")) if pe_fact else None
    pb_ratio = to_number(pb_fact.get("value")) if pb_fact else None
    forward_pe = to_number(forward_pe_fact.get("value")) if forward_pe_fact else None
    volatility = to_number(vol_fact.get("value")) if vol_fact else None

    health_score = compute_health_score({
        "net_margin": net_margin,
        "roe": roe,
        "operating_cash_flow": operating_cash_flow,
        "free_cash_flow": free_cash_flow,
        "debt_to_equity": debt_to_equity,
        "cash_position": cash_position,
        "total_debt": total_debt,
    })

    metrics: list[str] = []
    if revenue is not None:
        tone = "positive" if (revenue_growth or 0) >= 0 else "negative"
        metrics.append(metric_card("营收", format_currency(revenue, revenue_fact.get("unit")), growth_text(revenue_growth), tone, revenue_fact.get("source")))
    if net_profit is not None:
        tone = "positive" if (net_profit_growth or net_profit) >= 0 else "negative"
        metrics.append(metric_card("净利润", format_currency(net_profit, (net_profit_fact or {}).get("unit")), growth_text(net_profit_growth), tone, net_profit_fact.get("source")))
    if eps is not None:
        tone = "positive" if (eps_growth or eps) >= 0 else "negative"
        metrics.append(metric_card("EPS", f"{eps:.2f}", growth_text(eps_growth), tone, eps_fact.get("source")))
    if operating_cash_flow is not None:
        tone = "positive" if operating_cash_flow > 0 else "negative"
        sub = "现金流为正" if operating_cash_flow > 0 else "现金流为负"
        metrics.append(metric_card("经营现金流", format_currency(operating_cash_flow, operating_cash_flow_fact.get("unit")), sub, tone, operating_cash_flow_fact.get("source")))

    ratios = [
        ("毛利率", gross_margin),
        ("营业利润率", operating_margin),
        ("净利率", net_margin),
        ("ROE", roe),
    ]
    ratio_html = "".join(gauge(label, value) for label, value in ratios if value is not None)

    health_html = ""
    if health_score is not None:
        tone = "positive" if health_score >= 70 else "neutral" if health_score >= 45 else "negative"
        health_html += (
            f'<div class="fin-health-score {tone}"><span class="fin-health-score-label">健康评分</span>'
            f"<strong>{health_score}</strong><span>/100</span></div>"
        )
    if cash_position is not None:
        health_html += health_item("现金储备", format_currency(cash_position, cash_position_fact.get("unit")), "positive")
    if total_debt is not None:
        health_html += health_item("总债务", format_currency(total_debt, total_debt_fact.get("unit")), "negative" if total_debt > 0 else "positive")
    if net_debt is not None:
        health_html += health_item("净债务", format_currency(net_debt, net_debt_fact.get("unit")), "positive" if net_debt <= 0 else "negative")
    if free_cash_flow is not None:
        health_html += health_item("自由现金流", format_currency(free_cash_flow, free_cash_flow_fact.get("unit")), "positive" if free_cash_flow >= 0 else "negative")
    if debt_to_assets is not None:
        health_html += health_item("资产负债率", format_percent(debt_to_assets), "negative" if debt_to_assets > 50 else "neutral")
    if debt_to_equity is not None:
        health_html += health_item("债务权益比", format_percent(debt_to_equity), "negative" if debt_to_equity > 100 else "neutral")

    market_html = ""
    if current_price is not None:
        market_html += health_item("现价", f"${current_price:.2f}", "neutral")
    if pe_ratio is not None:
        market_html += health_item("市盈率", f"{pe_ratio:.2f}x", "neutral")
    if pb_ratio is not None:
        market_html += health_item("市净率", f"{pb_ratio:.2f}x", "neutral")
    if forward_pe is not None:
        market_html += health_item("前瞻PE", f"{forward_pe:.2f}x", "neutral")
    if volatility is not None:
        market_html += health_item("20日波动率", format_percent(volatility), "neutral")

    sources = sorted({f.get("source") or "unknown" for f in facts if f.get("field") in DISPLAY_FIELDS})
    source_badges = "".join(f'<span class="fin-source-badge">{s}</span>' for s in sources)

    return f"""
<section class="card facts-card">
  <div class="g2-badge">G2 · Facts-Only UI</div>
  <div class="fin-trends">
    <div class="fin-trends-header">
      <span class="fin-trends-title">财务基本面快照</span>
      <span class="fin-trends-badge">Structured Facts</span>
    </div>
    <p class="fin-trends-subtitle">展示 Evidence Packet 中的结构化财务事实，供被试在阅读报告前/时核对量化依据。</p>
    {"<div class='fin-metrics-row'>" + "".join(metrics) + "</div>" if metrics else ""}
    {"<div class='fin-gauges-section'><div class='fin-section-label'>盈利能力</div><div class='fin-gauges-grid'>" + ratio_html + "</div></div>" if ratio_html else ""}
    {"<div class='fin-health-section'><div class='fin-section-label'>财务健康度</div><div class='fin-health-grid'>" + health_html + "</div></div>" if health_html else ""}
    {"<div class='fin-health-section'><div class='fin-section-label'>市场指标</div><div class='fin-health-grid'>" + market_html + "</div></div>" if market_html else ""}
  </div>
  <div class="fin-sources"><span class="fin-sources-label">数据来源</span>{source_badges}</div>
</section>
"""


def markdown_report_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[-1].strip() if "---" in text else text
    html = markdown.markdown(body, extensions=["extra", "sane_lists"])
    html = re.sub(r"\[doc:(\d+)\]", r'<sup class="doc-ref">[doc:\1]</sup>', html)
    return html


G2_CSS = """
body { margin: 0; background: #0b1220; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.shell { max-width: 980px; margin: 0 auto; padding: 1.5rem 1.25rem 2rem; }
.card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 1rem; }
.g2-badge { display:inline-block; font-size:0.62rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:#93c5fd; border:1px solid rgba(96,165,250,0.25); background:rgba(59,130,246,0.08); border-radius:999px; padding:0.18rem 0.55rem; margin-bottom:0.75rem; }
.facts-card { margin-bottom: 1rem; }
.report-card { line-height: 1.7; font-size: 0.92rem; color: rgba(240,244,255,0.9); }
.report-card h1, .report-card h2, .report-card h3 { color: #f1f5f9; }
.report-card h2 { font-size: 1.1rem; margin-top: 1.4rem; }
.report-card blockquote { color: #f59e0b; border-left: 3px solid #f59e0b; margin: 0 0 1rem; padding-left: 0.75rem; }
.report-card strong { color: #f8fafc; }
.doc-ref { color: #60a5fa; font-size: 0.75rem; }
.fin-trends { display:flex; flex-direction:column; gap:0.9rem; }
.fin-trends-header { display:flex; justify-content:space-between; align-items:center; font-weight:700; }
.fin-trends-badge { font-size:0.58rem; letter-spacing:0.06em; text-transform:uppercase; color:#93c5fd; border:1px solid rgba(96,165,250,0.2); border-radius:999px; padding:0.16rem 0.5rem; }
.fin-trends-subtitle { margin:0; color:rgba(148,163,184,0.8); font-size:0.72rem; }
.fin-metrics-row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0.55rem; }
.fin-metric-card { display:flex; gap:0.45rem; padding:0.65rem; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); }
.fin-metric-card.positive { border-color:rgba(34,197,94,0.12); }
.fin-metric-card.negative { border-color:rgba(248,113,113,0.14); }
.fin-metric-icon { width:28px; height:28px; display:flex; align-items:center; justify-content:center; border-radius:7px; background:rgba(255,255,255,0.06); color:rgba(255,255,255,0.45); }
.fin-metric-label { font-size:0.62rem; color:rgba(255,255,255,0.38); text-transform:uppercase; letter-spacing:0.04em; }
.fin-metric-value { font-size:0.9rem; font-weight:700; }
.fin-metric-sub { font-size:0.62rem; color:rgba(255,255,255,0.45); }
.fin-metric-sub.positive { color:#4ade80; }
.fin-metric-sub.negative { color:#f87171; }
.fin-metric-source { font-size:0.56rem; color:rgba(255,255,255,0.25); }
.fin-section-label { font-size:0.68rem; font-weight:600; color:rgba(255,255,255,0.42); text-transform:uppercase; margin-bottom:0.4rem; }
.fin-gauges-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.55rem 0.8rem; }
.fin-gauge-label { font-size:0.66rem; color:rgba(255,255,255,0.48); }
.fin-gauge-value { font-size:0.78rem; font-weight:700; }
.fin-gauge-header { display:flex; justify-content:space-between; margin-bottom:0.2rem; }
.fin-gauge-bar-wrap { height:6px; border-radius:999px; background:rgba(255,255,255,0.06); overflow:hidden; }
.fin-gauge-bar { height:100%; border-radius:999px; }
.fin-health-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0.55rem; }
.fin-health-item, .fin-health-score { padding:0.55rem 0.65rem; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); }
.fin-health-label, .fin-health-score-label { font-size:0.62rem; color:rgba(255,255,255,0.42); text-transform:uppercase; }
.fin-health-value { font-size:0.86rem; font-weight:700; }
.fin-health-score.positive, .fin-health-item.positive { border-color:rgba(34,197,94,0.14); }
.fin-health-score.negative, .fin-health-item.negative { border-color:rgba(248,113,113,0.16); }
.fin-sources { margin-top:0.8rem; display:flex; flex-wrap:wrap; gap:0.35rem; align-items:center; }
.fin-sources-label { font-size:0.62rem; color:rgba(255,255,255,0.38); margin-right:0.25rem; }
.fin-source-badge { font-size:0.62rem; color:#bfdbfe; background:rgba(59,130,246,0.12); border:1px solid rgba(96,165,250,0.18); border-radius:999px; padding:0.12rem 0.45rem; }
"""


def build_g2_html(stimulus_id: str, md_path: Path, facts: list[dict]) -> str:
    facts_html = build_facts_panel_html(facts)
    report_html = markdown_report_html(md_path)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AAPL G2 — {stimulus_id}</title>
  <style>{G2_CSS}</style>
</head>
<body>
  <div class="shell">
    {facts_html}
    <section class="card report-card">{report_html}</section>
  </div>
</body>
</html>
"""


def export_screenshot(chrome_bin: str, html_path: Path, png_path: Path) -> None:
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={WINDOW_SIZE}",
        f"--screenshot={png_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    chrome_bin = resolve_chrome_binary()
    STIMULI_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using Chrome binary: {chrome_bin}")
    for stimulus_id, md_name, html_name, png_name, facts_key in STIMULI:
        md_path = STIMULI_DIR / md_name
        html_path = STIMULI_DIR / html_name
        png_path = ASSETS_DIR / png_name
        facts = load_facts(facts_key)
        html_path.write_text(build_g2_html(stimulus_id, md_path, facts), encoding="utf-8")
        export_screenshot(chrome_bin, html_path, png_path)
        print(f"Exported {png_name} ({len(facts)} facts)")


if __name__ == "__main__":
    main()
