import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from tools.market_tools import fetch_market_data
from config.llm import get_llm
from config.proxy import get_requests_proxies


model = get_llm("market")

_MARKET_AGENT = create_react_agent(
    model=model,
    tools=[fetch_market_data],
    name="market_data_expert",
    prompt="""
You are a professional Technical Market Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages to find pre-verified market data (current_price, RSI, MACD, volatility, etc.).
- If the Evidence Packet contains current_price, rsi_14, macd, and volatility — DO NOT call `fetch_market_data`. Analyze directly from the packet.
- ONLY call `fetch_market_data` if the Evidence Packet has NO market data facts at all.

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


def market_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## Market Analysis: NOT AVAILABLE\n"
                    f"- Reason: Evidence insufficient (output level: {output_level})\n"
                    "- Action: Await verified market data before technical analysis"
                ),
            }],
        }

    return _MARKET_AGENT.invoke(state)