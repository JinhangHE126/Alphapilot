import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from config.llm import get_llm
from graph.lang_labels import get_label, inject_language

model = get_llm("market")

_MARKET_AGENT = create_react_agent(
    model=model,
    tools=[],
    name="market_data_expert",
    prompt="""
You are a professional Technical Market Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages to find pre-verified market data (current_price, RSI, MACD, volatility, etc.).
- You have NO tools. Do NOT attempt to call any tool or function.
- If Evidence Packet market facts are missing, output "NOT AVAILABLE" and explain the missing fields.

Required output structure:
- Current price and recent change
- Key indicators: RSI(14), MACD (including signal and histogram), 20-day volatility
- Interpretation of momentum, trend strength, and risk level
- A short risk note

STRICT PROHIBITIONS — VIOLATION WILL CAUSE REPORT REJECTION:
- Do NOT output any section titled "投资建议", "中线投资建议", "操作建议", or similar.
- Do NOT use words like "建议", "推荐", "观望", "轻仓", "重仓", "介入", "建仓", "减仓", "买入", "卖出".
- Do NOT suggest entry points, exit points, or position sizing.
- Do NOT give price targets or directional trading calls.
- Your output ends after "风险提示". Nothing more.

Strict rules:
- Base everything strictly on Evidence Packet facts and tool data.
- NEVER fabricate or assume data points not present in the Evidence Packet or tool output.
- [~] and [?] marked facts in Evidence Packet are lower confidence — treat with caution.
- Do not discuss fundamentals, earnings, news, or macro events.
""",
)


def _build_market_fallback(ep: dict, language: str = "") -> str:
    facts = {f["field"]: f for f in ep.get("facts", [])}
    lang = language or "en"

    price = facts.get("current_price", {})
    change = facts.get("price_change_pct", {})
    rsi = facts.get("rsi_14", {})
    macd = facts.get("macd", {})
    macd_sig = facts.get("macd_signal", {})
    vol = facts.get("volatility_20d_annualized", {})
    avg_vol = facts.get("avg_volume_20d", {})

    lines = []
    pv = price.get("value")
    pu = price.get("unit", "")
    ps = price.get("source", "?")
    if pv is not None:
        label_price = get_label("market_current_price", lang)
        label_src = get_label("market_source", lang)
        lines.append(f"- {label_price}：{pv} {pu}（{label_src}：{ps}）")
    cv = change.get("value")
    if cv is not None:
        label_change = get_label("market_day_change", lang)
        lines.append(f"- {label_change}：{cv}%")
    lines.append("")

    rv = rsi.get("value")
    if rv is not None:
        if rv < 30:
            zone = get_label("market_rsi_oversold", lang)
        elif rv > 70:
            zone = get_label("market_rsi_overbought", lang)
        else:
            zone = get_label("market_rsi_neutral", lang)
        lines.append(f"- RSI(14)：{rv}（{zone}）")
    mv = macd.get("value")
    sv = macd_sig.get("value")
    if mv is not None and sv is not None:
        hist = round(mv - sv, 4)
        lines.append(f"- MACD：{mv}；信号线：{sv}；柱状图：{hist}")
    vv = vol.get("value")
    if vv is not None:
        label_vol = get_label("market_20d_vol", lang)
        lines.append(f"- {label_vol}：{vv}%")
    av = avg_vol.get("value")
    if av is not None and av > 0:
        label_avg_vol = get_label("market_20d_avg_vol", lang)
        label_shares = get_label("market_shares", lang)
        lines.append(f"- {label_avg_vol}：{av} {label_shares}")

    lines.append("")
    lines.append(f"**{get_label('market_disclaimer', lang).replace('：', '：')}**")
    return "\n".join(lines)


def market_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")
    language = state.get("language", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    f"{get_label('market_not_available', language)}\n"
                    f"- {get_label('market_na_reason', language)} (output level: {output_level})\n"
                    f"- {get_label('market_na_action', language)}"
                ),
            }],
        }

    inject_language(state, language)
    result = _MARKET_AGENT.invoke(state)
    inject_language(state, language)  # ensure LLM outputs in correct language
    raw_content = result["messages"][-1].content
    text = str(raw_content) if raw_content else ""

    if len(text) < 30 or "无法提供" in text or "NOT AVAILABLE" in text:
        fallback = _build_market_fallback(ep, language)
        if fallback.strip():
            result["messages"][-1].content = f"{get_label('market_title', language)}\n\n{fallback}"

    return result