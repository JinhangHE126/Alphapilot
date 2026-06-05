import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from config.llm import get_llm


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