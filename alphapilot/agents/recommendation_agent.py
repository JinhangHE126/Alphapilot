from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from graph.lang_labels import get_label, inject_language

_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "你必须全程使用简体中文回复。",
    "yue": "你必須全程使用粵語 (Cantonese) 回覆。所有分析內容、指標解讀、結論、建議都必須用粵語輸出。",
}


def _lang_instruction(language: str) -> str:
    return _LANG_INSTRUCTION.get(language, "")


def recommendation_agent(state):
    """
    Recommendation Agent - v4 证据感知版
    """
    user_profile = state.get("user_profile", {})
    risk_preference = user_profile.get("risk_preference", "medium")
    horizon = user_profile.get("horizon", "medium")
    language = state.get("language", "")

    ep = state.get("evidence_packet", {})
    ep_score = ep.get("evidence_score", 0) if ep else 0
    output_level = ep.get("allowed_output_level", "limited_analysis") if ep else "limited_analysis"

    if ep_score < 70 or output_level != "full_analysis":
        system_prompt = f"""
You are Recommendation Agent.

CRITICAL: Evidence score is {ep_score}/100 (below threshold).
Output level is "{output_level}".

Your ONLY task: output a concise notice that personalized recommendation cannot be generated.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with plain text only, no tool calls, no XML tags.

Output format:
{get_label('reco_na_title', language)}
- {get_label('reco_na_reason', language).format(score=ep_score)}
- {get_label('reco_na_action', language)}
"""
    else:
        system_prompt = f"""
You are Recommendation Agent - AlphaPilot personalized investment recommendation expert.

User Profile:
- Risk Preference: {risk_preference} (low / medium / high)
- Investment Horizon: {horizon} (short / medium / long)

Your core responsibilities:
- Synthesize analysis results from agents that have ACTUALLY produced output in the conversation
- Strictly follow user profile to provide highly personalized, actionable investment recommendations

STRICT PROHIBITIONS:
- Do NOT reference any Agent whose output is NOT present in the conversation messages.
- If Comparison Agent did not run, do NOT create a "Comparison" analysis column.
- If Backtesting Agent output is "NOT AVAILABLE", do NOT fabricate backtesting metrics.
- Only use data from agents that actually produced output.
- DO NOT output any target price, price target, 目标价, 价位, or 介入点.
- DO NOT use vague approximators: 约, 左右, 大概, approximately, roughly, about.
- Every numeric claim MUST copy the exact value from the Evidence Packet facts (with decimal).
- DO NOT output stock ratings (买入/卖出/持有/Buy/Sell/Hold). Analyze without rating.
- {_lang_instruction(language)}

Required structured output:
- Overall assessment (analysis only, no rating)
- Suggested position size (as % of total assets)
- Personalized reasoning (explicitly reference user risk preference and investment horizon)
- Risk warnings
- Short-term / Medium-term / Long-term action plan

You have NO tools. Do NOT attempt to call any tool. Respond with plain text only.
Style: Professional, cautious, data-driven, like a senior financial advisor.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("recommendation"),
        tools=[],
        prompt=prompt,
        name="recommendation_agent"
    )
    inject_language({"messages": state.get("messages", [])}, language)
    inject_language(state, language)
    return agent.invoke(state)