from langgraph.prebuilt import create_react_agent
# from langchain_openai import ChatOpenAI   # 如果你想统一用 Google，可改成 from your_global_settings import get_llm
from config.llm import get_llm
from graph.lang_labels import inject_language
from pydantic import BaseModel, Field
from typing import Any, Literal
import json
import re

# model = ChatOpenAI(model="gpt-4o", temperature=0)
model = get_llm("risk")


class RiskAssessment(BaseModel):
    """Structured output for the Risk Agent."""
    volatility_risk: str = Field(description="Volatility risk level: Low / Medium / High")
    macro_risk: str = Field(description="Macro risk level: Low / Medium / High")
    stop_loss_suggestion: str = Field(description="Stop-loss suggestion (price or percentage)")
    position_suggestion: str = Field(description="Position sizing suggestion (e.g., no more than XX% of total position)")
    overall_risk_score: int = Field(description="Overall risk score 0-100 (higher means more dangerous)")
    risk_reasoning: str = Field(description="Detailed risk reasoning process")
    key_risks: list[str] = Field(default_factory=list, description="Top 3-5 key risk points, each a short sentence")


def _extract_json_text(text: str) -> str:
    block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if block:
        return block.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    raise ValueError("No valid JSON found in model output.")


def _to_risk_level(value: Any) -> str:
    """Normalize numeric/text risk to Low/Medium/High labels."""
    if isinstance(value, (int, float)):
        score = float(value)
        if score >= 67:
            return "High"
        if score >= 34:
            return "Medium"
        return "Low"

    text = str(value).strip().lower()
    if text in {"low", "medium", "high"}:
        return text.capitalize()
    if text in {"low risk", "low-risk"}:
        return "Low"
    if text in {"medium risk", "medium-risk", "mid", "moderate"}:
        return "Medium"
    if text in {"high risk", "high-risk"}:
        return "High"
    return str(value)


def _normalize_payload(payload: dict) -> dict:
    """Make model output robust before Pydantic validation."""
    normalized = dict(payload)
    normalized["volatility_risk"] = _to_risk_level(payload.get("volatility_risk", "Medium"))
    normalized["macro_risk"] = _to_risk_level(payload.get("macro_risk", "Medium"))

    overall = payload.get("overall_risk_score", 50)
    try:
        normalized["overall_risk_score"] = max(0, min(100, int(round(float(overall)))))
    except (TypeError, ValueError):
        normalized["overall_risk_score"] = 50

    for key in ("stop_loss_suggestion", "position_suggestion", "risk_reasoning"):
        normalized[key] = str(payload.get(key, "")).strip()

    # key_risks: ensure it's a list of strings
    raw_risks = payload.get("key_risks", [])
    if isinstance(raw_risks, list):
        normalized["key_risks"] = [str(r).strip() for r in raw_risks if str(r).strip()]
    else:
        normalized["key_risks"] = []

    return normalized


def run_risk_assessment(user_text: str) -> RiskAssessment:
    result = risk_agent.invoke({
        "messages": [{"role": "user", "content": user_text}]
    })

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        raw = "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw
        )

    json_text = _extract_json_text(str(raw))
    payload = _normalize_payload(json.loads(json_text))
    return RiskAssessment.model_validate(payload)


def _create_risk_agent():
    return create_react_agent(
        model=model,
        tools=[],
        name="risk_expert",
        prompt="""
You are AlphaPilot's Chief Risk Control Expert (Risk Expert).

Your ONLY responsibility is to evaluate and quantify risks. You must strictly follow the boundaries below.

### Core Responsibilities
- Evaluate **volatility risk** based on market data (RSI, MACD, historical volatility, etc.)
- Evaluate **macro and company-specific risk** based on fundamentals, news, **and especially "### Document Evidence"**
- Provide stop-loss suggestion and position sizing suggestion
- Output an overall risk score (0-100, higher = more dangerous)

### How to Use Document Evidence
When "### Document Evidence" is available, you **must actively review** it for risk-related information, including:
- Risk factors disclosed in annual reports (e.g., regulatory, competitive, operational, financial risks)
- Management discussion of risks and uncertainties in earnings calls or MD&A
- Any forward-looking risk warnings or contingent liabilities

Use Document Evidence to enrich your assessment of **macro_risk** and to populate the **key_risks** array. When referencing information from documents, clearly indicate the source (e.g., "Risk Factors section of 2024 Annual Report" or "Q4 earnings call transcript").

### STRICT BOUNDARIES — DO NOT:
- Output Buy / Sell / Hold recommendations (this is the Recommendation Agent's job)
- Output target prices or expected returns
- Give investment advice or directional market calls
- Repeat or redo fundamental analysis from other agents

You have NO tools. Do NOT attempt to call any tool or function.
Respond with JSON only. No markdown, no tool calls, no preamble, no extra text.

### Output JSON Structure
Return ONLY a valid JSON object with the following keys:

{
  "volatility_risk": <0-100>,
  "macro_risk": <0-100>,
  "stop_loss_suggestion": "<e.g. 8-12% below current price>",
  "position_suggestion": "<e.g. Reduce position size to 3-5% of portfolio>",
  "overall_risk_score": <0-100>,
  "risk_reasoning": "<explain key risk drivers, including insights from Document Evidence when relevant>",
  "key_risks": [
    "<short risk point with source if from documents>",
    "..."
  ]
}

- Provide 3-5 items in `key_risks`.
- When a risk comes from Document Evidence, try to briefly note the source (e.g., "Regulatory risk - Data security concerns mentioned in annual report").

CRITICAL: Output ONLY the JSON. Do not add any text before or after it.
"""
    )
# def _create_risk_agent():
#     return create_react_agent(
#         model=model,
#         tools=[],
#         name="risk_expert",
#         prompt="""
# You are AlphaPilot's Chief Risk Control Expert (Risk Expert).

# Your ONLY responsibility:
# - Evaluate volatility risk based on market data (RSI, MACD, volatility)
# - Evaluate macro/systemic risk based on fundamentals, news, and "### Document Evidence" (risk disclosures in annual reports, earnings call risk factors)
# - Provide stop-loss suggestion and position sizing suggestion
# - Output overall risk score (0-100, higher = more dangerous)

# STRICT BOUNDARIES — DO NOT:
# - Output Buy/Sell/Hold recommendations (that is the Recommendation Agent's job)
# - Output target prices or expected return percentages
# - Give investment advice or directional market calls
# - Repeat fundamental analysis from other agents

# You have NO tools. Do NOT attempt to call any tool or function.
# Respond with JSON only, no markdown, no tool calls, no preamble.

# Return JSON only with keys: volatility_risk, macro_risk, stop_loss_suggestion, position_suggestion, overall_risk_score, risk_reasoning, key_risks
# - key_risks: array of 3-5 short risk points, e.g. ["高波动率 42%", "宏观利率上行压力", "行业政策不确定性"]
# """,
#     )


NA_RISK_JSON = (
    '{"volatility_risk":"N/A","macro_risk":"N/A",'
    '"stop_loss_suggestion":"N/A","position_suggestion":"N/A",'
    '"overall_risk_score":0,'
    '"risk_reasoning":"Risk assessment unavailable: '
    'output level is limited_analysis or worse",'
    '"key_risks":[]}'
)

_NA_RISK_JSON_SCORE = (
    '{"volatility_risk":"N/A","macro_risk":"N/A",'
    '"stop_loss_suggestion":"N/A","position_suggestion":"N/A",'
    '"overall_risk_score":0,'
    '"risk_reasoning":"Risk assessment unavailable: '
    'evidence score below threshold (50)",'
    '"key_risks":[]}'
)

_PARTIAL_PREFIX = '{"data_quality":"partial",'

_PARTIAL_RISK_AGENT = create_react_agent(
    model=model,
    tools=[],
    name="risk_expert_partial",
    prompt="""
You are AlphaPilot's Chief Risk Control Expert operating in LIMITED ANALYSIS mode.

CRITICAL CONTEXT: Evidence Score is between 50-72/100. Some key quantitative data may be missing. 
Your assessment must be conservative, clearly qualified, and transparent about data limitations.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with JSON only. No markdown, no prose, no extra text.

### How to Use Available Information
- **volatility_risk**: Estimate based on available market data (price_change_pct, beta, etc.). If no market data is available, use "N/A".
- **macro_risk**: Assess using available news, fundamental signals, **and "### Document Evidence"** when present.
- **Document Evidence Usage**: Even in limited mode, actively review "### Document Evidence" for risk-related qualitative information, such as:
  - Risk factors and uncertainties disclosed in annual reports
  - Management discussion of risks in earnings calls or MD&A
  - Regulatory, operational, or competitive risks mentioned in filings
  Use this information to supplement `macro_risk` and `key_risks` when structured data is insufficient.

### RULES for LIMITED mode:
- Be conservative in all assessments.
- Clearly state data gaps and how they affect the reliability of the risk evaluation.
- `position_suggestion`: Always recommend conservative sizing ("no more than 5% of portfolio" or similar).
- `overall_risk_score`: Should generally be in the 50-80 range (elevated due to limited data).
- `risk_reasoning`: MUST explicitly list missing key fields and explain their impact. Also mention any useful risk insights obtained from Document Evidence.
- `data_quality`: Must be set to "limited".
- `key_risks`: Provide 3-5 short, specific risk points. When a risk comes from Document Evidence, briefly note the source.

### Output JSON Structure
Return ONLY a valid JSON object with these exact keys:

{
  "volatility_risk": <number or "N/A">,
  "macro_risk": <number 0-100>,
  "stop_loss_suggestion": "<e.g. -8% or N/A>",
  "position_suggestion": "<conservative suggestion>",
  "overall_risk_score": <number 50-80>,
  "risk_reasoning": "<explain data gaps + how Document Evidence was used if available>",
  "data_quality": "limited",
  "key_risks": [
    "<short risk description, note source if from documents>"
  ]
}

CRITICAL: Output ONLY the JSON object. Do not add any text before or after it.
"""
)
# _PARTIAL_RISK_AGENT = create_react_agent(
#     model=model,
#     tools=[],
#     name="risk_expert_partial",
#     prompt="""
# You are AlphaPilot's Chief Risk Control Expert operating in LIMITED ANALYSIS mode.

# CRITICAL CONTEXT: Evidence Score is 50-72/100. Some key data may be missing.
# The risk assessment MUST be conservative, qualified, and explicitly mention data gaps.

# You have NO tools. Do NOT attempt to call any tool or function.
# Respond with JSON only (no markdown, no prose).

# RULES for LIMITED mode:
# - volatility_risk: estimate from available market data (price_change_pct, beta, etc). If no market data at all, use "N/A"
# - macro_risk: assess from available news/fundamental signals
# - stop_loss_suggestion: if current_price available, suggest a percentage loss threshold (e.g. -8%); otherwise "N/A"
# - position_suggestion: always suggest conservative sizing ("no more than 5%")
# - overall_risk_score: 50-80 (elevated due to limited data)
# - risk_reasoning: MUST list missing fields and explain how they limit the assessment
# - Add field "data_quality": "limited"
# - key_risks: array of 3-5 short risk points

# Return JSON only with keys: volatility_risk, macro_risk, stop_loss_suggestion, position_suggestion, overall_risk_score, risk_reasoning, data_quality, key_risks
# """,
# )


def risk_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    ep_score = int(ep.get("evidence_score", 0)) if isinstance(ep, dict) else (int(ep.evidence_score) if hasattr(ep, 'evidence_score') else 0)
    output_level = ep.get("allowed_output_level", "")
    language = state.get("language", "")

    if output_level in ("data_summary_only", "insufficient_evidence"):
        return {
            "messages": [{"role": "assistant", "content": NA_RISK_JSON}],
        }

    if output_level == "limited_analysis" and ep_score >= 50:
        agent = _PARTIAL_RISK_AGENT
    elif ep_score >= 50 or output_level in ("full_analysis", "limited_analysis_partial"):
        agent = _create_risk_agent()
    else:
        return {
            "messages": [{"role": "assistant", "content": _NA_RISK_JSON_SCORE}],
        }

    inject_language(state, language)
    result = agent.invoke(state)

    raw = result["messages"][-1].content
    text = str(raw) if raw else ""
    if text.strip().startswith("{"):
        try:
            obj = json.loads(text)
            if output_level == "limited_analysis":
                obj["data_quality"] = "limited"
                try:
                    obj["overall_risk_score"] = min(int(round(float(obj.get("overall_risk_score", 60)))), 80)
                except (TypeError, ValueError):
                    obj["overall_risk_score"] = 60
            elif output_level == "limited_analysis_partial":
                obj["data_quality"] = "partial"
            result["messages"][-1].content = json.dumps(obj, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            if output_level == "limited_analysis_partial" and '"data_quality"' not in text:
                result["messages"][-1].content = _PARTIAL_PREFIX + text[1:]

    return result

__all__ = ["risk_agent", "run_risk_assessment"]