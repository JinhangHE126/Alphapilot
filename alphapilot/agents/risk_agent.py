from langgraph.prebuilt import create_react_agent
# from langchain_openai import ChatOpenAI   # 如果你想统一用 Google，可改成 from your_global_settings import get_llm
from config.llm import get_llm
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


risk_agent = create_react_agent(
    model=model,
    tools=[],
    name="risk_expert",
    prompt="""
You are AlphaPilot's Chief Risk Control Expert (Risk Expert).

CRITICAL: Check the Evidence Packet in the conversation context BEFORE analyzing.
- If evidence_score < 50 or output_level is "limited_analysis" or worse:
  Output ONLY JSON: {"volatility_risk":"N/A","macro_risk":"N/A","stop_loss_suggestion":"N/A","position_suggestion":"N/A","overall_risk_score":0,"risk_reasoning":"Insufficient data for risk assessment. Evidence score below threshold."}
  Do NOT synthesize strategy. Do NOT give investment recommendations. Do NOT summarize other agent output.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with JSON only, no markdown, no tool calls.

Your ONLY responsibility:
- Evaluate volatility risk based on market data (RSI, MACD, volatility)
- Evaluate macro/systemic risk based on fundamentals and news
- Provide stop-loss suggestion and position sizing suggestion
- Output overall risk score (0-100, higher = more dangerous)

Return JSON only with keys: volatility_risk, macro_risk, stop_loss_suggestion, position_suggestion, overall_risk_score, risk_reasoning
""",
)

__all__ = ["risk_agent", "run_risk_assessment"]