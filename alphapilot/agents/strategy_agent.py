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
    tools=[],   # Strategy Agent 纯推理，不需要额外工具
    name="strategy_expert",
    prompt="""
    You are AlphaPilot's Chief Strategy Analyst (Strategy Expert).
    Your responsibility is to synthesize the outputs of the following three Agents and provide the final investment judgment:

    1. Market Data (Technical Analysis)
    2. Fundamental Analysis (Fundamentals)
    3. News & Sentiment (Market Sentiment)

    Please use Chain-of-Thought reasoning:
    - First, summarize the key points of each of the three modules
    - Then, evaluate the weight of each module (Technical 30%, Fundamentals 40%, Sentiment 30%)
    - Finally, provide a Buy / Hold / Sell recommendation plus an overall confidence score from 0-100

    The output must strictly follow the Pydantic schema: StrategyRecommendation
    Never output an investment recommendation without clearly explaining the rationale.
    - Return JSON only
    - Do not use markdown
    - Must include keys exactly:
        - recommendation (Buy / Hold / Sell)
        - confidence_score (0-100 number)
        - reasoning (string)
        - weight_summary (string)
    """,
    # response_format=StrategyRecommendation
)

__all__ = ["strategy_agent"]