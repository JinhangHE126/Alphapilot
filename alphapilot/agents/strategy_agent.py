from langgraph.prebuilt import create_react_agent
from config.llm import get_llm
from pydantic import BaseModel, Field
from typing import Literal
import json
import re
from pydantic import ValidationError

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
    recommendation: Literal["Buy", "Hold", "Sell"]
    confidence_score: float = Field(description="Overall confidence score (0-100)")
    reasoning: str = Field(description="Detailed Chain-of-Thought reasoning process")
    weight_summary: str = Field(description="Summary of factor weights")

def run_strategy_analysis(user_text: str) -> StrategyRecommendation:
    result = strategy_agent.invoke({
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



strategy_agent = create_react_agent(
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

Return JSON only (no markdown):
{"recommendation": "Buy|Hold|Sell", "confidence_score": 0-100, "reasoning": "...", "weight_summary": "..."}
""",
)

__all__ = ["strategy_agent"]