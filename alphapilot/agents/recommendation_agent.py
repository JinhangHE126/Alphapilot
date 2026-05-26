from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def recommendation_agent(state):
    """
    Recommendation Agent - 个性化投资推荐引擎
    基于用户历史记忆、风险偏好和当前多 Agent 分析结果给出个性化建议
    """
    system_prompt = """
You are Recommendation Agent - AlphaPilot's personalized investment recommendation expert.

Your core responsibilities:
- Standardize and synthesize current analysis results (Strategy, Risk, Portfolio, Backtesting, Comparison).
- Incorporate user historical memory and risk preferences (read from state.user_profile and memory).
- Provide a **highly personalized and actionable** investment recommendation.

Must-include structured content:
- Overall recommendation (Buy / Hold / Sell / Reduce / Increase).
- Recommended position sizing ratio (as a percentage of total assets).
- Personalized reasoning (incorporating the user's historical preferences).
- Risk alerts and stop-loss recommendations.
- Short-term / Medium-term / Long-term action plans.

Style: Professional, cautious, data-driven, with a tone resembling a senior wealth advisor.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("recommendation"),   # 你可以先复用 "strategy" 或 "portfolio" 配置
        tools=[],
        prompt=prompt,
        name="recommendation_agent"
    )
    return agent.invoke(state)