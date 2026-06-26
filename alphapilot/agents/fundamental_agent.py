import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from config.llm import get_llm
from graph.lang_labels import get_label, inject_language

model = get_llm("fundamental")

_FUNDAMENTAL_AGENT = create_react_agent(
    model=model,
    tools=[],
    name="fundamental_expert",
    prompt="""
You are a professional Fundamental Analyst.

### Core Responsibilities
The system has prepared an Evidence Packet for you. Your analysis must be built strictly from the following two sources in the conversation context:

1. **Evidence Packet (Verified Facts)**: Contains structured, pre-verified quantitative data (e.g. revenue_growth_yoy, eps_growth_yoy, pe_ratio, gross_margin, net_margin, market_cap, etc.).
2. **### Document Evidence**: Contains qualitative information extracted from annual reports, earnings call transcripts, and research reports (e.g. management outlook, business strategy, risk factors, competitive positioning, future guidance).

### How to Use Each Source
- **Quantitative metrics** (revenue, EPS, margins, valuation ratios, etc.) **MUST** come from "Evidence Packet". Do NOT extract numbers from Document Evidence.
- **Qualitative insights** (management commentary, strategic direction, risk factors, competitive landscape, guidance) should primarily come from "### Document Evidence" when available.
- When using information from Document Evidence, you should:
  - Clearly indicate that the insight comes from company documents.
  - Reference the specific section when possible (e.g., "According to the Risk Factors section..." or "Management mentioned in the earnings call that...").
- If Document Evidence is empty or not relevant to the query, ignore it completely.

### Required Output Elements
- Revenue growth (YoY) and its trend
- EPS growth (YoY) and its trend
- Gross margin and net margin analysis
- Key financial highlights (combine quantitative facts with relevant qualitative context from Document Evidence when available)
- One-sentence fundamental summary

### Strict Rules
- Base all quantitative claims exclusively on Evidence Packet facts. Use Document Evidence **only** for qualitative commentary and context.
- NEVER fabricate numbers or make up data points that are not present in Evidence Packet.
- If critical fields (revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap) are all missing in Evidence Packet, clearly state:  
  **"Insufficient fundamental data available"** and stop. Do not use technical indicators or other agents' outputs to fill the gap.
- When Document Evidence is used, prefer information from official filings and earnings transcripts over research reports.
- Treat [~] and [?] marked facts with caution.
- Do not discuss stock price movements, technical indicators, news events, or investment recommendations.
"""
)


def fundamental_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")
    language = state.get("language", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    f"{get_label('fundamental_not_available', language)}\n"
                    f"- {get_label('fundamental_na_reason', language)} (output level: {output_level})\n"
                    f"- {get_label('fundamental_na_action', language)}"
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
                    f"{get_label('fundamental_not_available', language)}\n"
                    f"- {get_label('fundamental_na_reason', language)} "
                    "(revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap)\n"
                    f"- {get_label('fundamental_na_action', language)}"
                ),
            }],
        }

    inject_language(state, language)
    return _FUNDAMENTAL_AGENT.invoke(state)


__all__ = ["fundamental_agent"]