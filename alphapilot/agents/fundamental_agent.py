import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from config.llm import get_llm

model = get_llm("fundamental")


_FUNDAMENTAL_AGENT = create_react_agent(
    model=model,
    tools=[],
    name="fundamental_expert",
    prompt="""
You are a professional Fundamental Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages to find pre-verified fundamental data (revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap, etc.).
- You have NO tools. Do NOT attempt to call any tool or function.
- Build analysis strictly from Evidence Packet facts.

Required output elements:
- Revenue growth (YoY)
- EPS growth
- Gross margin and net margin
- Key financial highlights
- One-sentence fundamental summary

Strict rules:
- Base everything on Evidence Packet facts.
- NEVER fabricate or assume data points not in the Evidence Packet.
- If critical fundamental fields (revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap) are ALL missing:
  state clearly "Insufficient fundamental data available" and STOP. Do NOT fill the gap with technical indicators (RSI, MACD, volatility, price) or other agents' data.
- [~] and [?] marked facts are lower confidence — treat with caution.
- Do not discuss stock price movement, technical indicators, news, or investment recommendations.
"""
)


def fundamental_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## Fundamental Analysis: NOT AVAILABLE\n"
                    f"- Reason: Evidence insufficient (output level: {output_level})\n"
                    "- Action: Await verified fundamental data before analysis"
                ),
            }],
        }

    facts = ep.get("facts", []) if isinstance(ep, dict) else []
    available_fields = {
        f.get("field")
        for f in facts
        if isinstance(f, dict) and f.get("field")
    }
    critical_fields = {"revenue_growth_yoy", "eps_growth_yoy", "pe_ratio", "market_cap"}
    if critical_fields.isdisjoint(available_fields):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## Fundamental Analysis: NOT AVAILABLE\n"
                    "- Reason: critical fundamental fields are missing "
                    "(revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap)\n"
                    "- Action: collect/verify fundamental data before analysis"
                ),
            }],
        }

    return _FUNDAMENTAL_AGENT.invoke(state)


__all__ = ["fundamental_agent"]