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

Your ONLY responsibility:
- Evaluate volatility risk based on market data (RSI, MACD, volatility)
- Evaluate macro/systemic risk based on fundamentals and news
- Provide stop-loss suggestion and position sizing suggestion
- Output overall risk score (0-100, higher = more dangerous)

STRICT BOUNDARIES — DO NOT:
- Output Buy/Sell/Hold recommendations (that is the Recommendation Agent's job)
- Output target prices or expected return percentages
- Give investment advice or directional market calls
- Repeat fundamental analysis from other agents

You have NO tools. Do NOT attempt to call any tool or function.
Respond with JSON only, no markdown, no tool calls, no preamble.

Return JSON only with keys: volatility_risk, macro_risk, stop_loss_suggestion, position_suggestion, overall_risk_score, risk_reasoning
""",
    )


NA_RISK_JSON = (
    '{"volatility_risk":"N/A","macro_risk":"N/A",'
    '"stop_loss_suggestion":"N/A","position_suggestion":"N/A",'
    '"overall_risk_score":0,'
    '"risk_reasoning":"Risk assessment unavailable: '
    'output level is limited_analysis or worse"}'
)

_NA_RISK_JSON_SCORE = (
    '{"volatility_risk":"N/A","macro_risk":"N/A",'
    '"stop_loss_suggestion":"N/A","position_suggestion":"N/A",'
    '"overall_risk_score":0,'
    '"risk_reasoning":"Risk assessment unavailable: '
    'evidence score below threshold (50)"}'
)

_PARTIAL_PREFIX = '{"data_quality":"partial",'

_PARTIAL_RISK_AGENT = create_react_agent(
    model=model,
    tools=[],
    name="risk_expert_partial",
    prompt="""
You are AlphaPilot's Chief Risk Control Expert operating in LIMITED ANALYSIS mode.

CRITICAL CONTEXT: Evidence Score is 50-72/100. Some key data may be missing.
The risk assessment MUST be conservative, qualified, and explicitly mention data gaps.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with JSON only (no markdown, no prose).

RULES for LIMITED mode:
- volatility_risk: estimate from available market data (price_change_pct, beta, etc). If no market data at all, use "N/A"
- macro_risk: assess from available news/fundamental signals
- stop_loss_suggestion: if current_price available, suggest a percentage loss threshold (e.g. -8%); otherwise "N/A"
- position_suggestion: always suggest conservative sizing ("no more than 5%")
- overall_risk_score: 50-80 (elevated due to limited data)
- risk_reasoning: MUST list missing fields and explain how they limit the assessment
- Add field "data_quality": "limited"

Return JSON only with keys: volatility_risk, macro_risk, stop_loss_suggestion, position_suggestion, overall_risk_score, risk_reasoning, data_quality
""",
)


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