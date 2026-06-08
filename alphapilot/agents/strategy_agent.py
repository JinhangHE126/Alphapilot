from langgraph.prebuilt import create_react_agent
from config.llm import get_llm
from graph.lang_labels import inject_language
from pydantic import BaseModel, Field
from typing import Literal
import json
import re

model = get_llm("strategy")


def _extract_json_text(text: str) -> str:
    block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if block:
        return block.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1].strip()

    raise ValueError("No valid JSON found in model output.")
class StrategyRecommendation(BaseModel):
    """Structured output for the Strategy Agent."""
    recommendation: Literal["Buy", "Hold", "Sell", "N/A"]
    confidence_score: float = Field(description="Overall confidence score (0-100)")
    reasoning: str = Field(description="Detailed Chain-of-Thought reasoning process")
    weight_summary: str = Field(description="Summary of factor weights")

def run_strategy_analysis(user_text: str) -> StrategyRecommendation:
    result = _strategy_agent.invoke({
        "messages": [{"role": "user", "content": user_text}]
    })

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        raw = "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in raw
        )

    json_text = _extract_json_text(str(raw))
    payload = json.loads(json_text)
    return StrategyRecommendation.model_validate(payload)



_strategy_agent = create_react_agent(
    model=model,
    tools=[],
    name="strategy_expert",
    prompt="""
You are AlphaPilot's Chief Strategy Analyst (Strategy Expert).

CRITICAL: Check the Evidence Packet in the conversation context BEFORE analyzing.
- If evidence_score < 50 or output_level is "limited_analysis" or worse:
  Output ONLY: "## Strategy Analysis: NOT AVAILABLE - Insufficient data (evidence score below threshold)."
  Do NOT fabricate analysis. Do NOT summarize other agents' output.
- If evidence_score >= 50: synthesize the outputs of Market/Fundamental/News agents.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with plain text only, no tool calls, no XML tags.

Your responsibility:
- Summarize key points from Market Data (30%), Fundamental Analysis (40%), News Sentiment (30%)
- Provide Buy / Hold / Sell recommendation with confidence_score (0-100)
- Include Chain-of-Thought reasoning and weight_summary

Return JSON only (no markdown, no body text):
{"recommendation": "Buy|Hold|Sell", "confidence_score": 0-100, "reasoning": "...", "weight_summary": "..."}

CRITICAL: Output ONLY the JSON. Do NOT write a prose summary before or after the JSON.
The recommendation field in the JSON is the single source of truth.
Do NOT write "Final Recommendation: BUY" or similar text outside the JSON.
""",
)

_NA_STRATEGY = (
    '{"recommendation":"N/A","confidence_score":0,'
    '"reasoning":"Insufficient data for strategy analysis. '
    'Evidence output level is limited_analysis or worse.",'
    '"weight_summary":"Strategy unavailable at this output level."}'
)

_PARTIAL_PREFIX = '{"data_quality":"partial",'


def strategy_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")
    language = state.get("language", "")

    if output_level in ("limited_analysis", "data_summary_only", "insufficient_evidence"):
        return {
            "messages": [{"role": "assistant", "content": _NA_STRATEGY}],
        }

    inject_language(state, language)
    result = _strategy_agent.invoke(state)

    if output_level == "limited_analysis_partial":
        raw = result["messages"][-1].content
        text = str(raw) if raw else ""
        if text.strip().startswith("{") and '"data_quality"' not in text:
            result["messages"][-1].content = _PARTIAL_PREFIX + text[1:]

    return result


__all__ = ["strategy_agent"]