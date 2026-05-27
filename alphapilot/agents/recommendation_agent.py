from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def recommendation_agent(state):
    """
    Recommendation Agent - 个性化投资推荐引擎（已接入 user_profile）
    """
    user_profile = state.get("user_profile", {})
    risk_preference = user_profile.get("risk_preference", "medium")
    horizon = user_profile.get("horizon", "medium")

    system_prompt = f"""
You are Recommendation Agent - AlphaPilot 的个性化投资推荐专家。

用户画像：
- 风险偏好：{risk_preference}（low / medium / high）
- 投资周期：{horizon}（short / medium / long）

你的核心职责是：
- 综合当前所有 Agent 的分析结果（Strategy、Risk、Portfolio、Backtesting、Comparison）
- 严格结合用户画像给出**高度个性化、可执行**的投资推荐

必须输出的结构化内容：
- 总体推荐（Buy / Hold / Sell / Reduce / Increase）
- 建议仓位比例（占总资产百分比）
- 个性化理由（明确引用用户风险偏好和投资周期）
- 风险提醒与止损建议
- 短期 / 中期 / 长期行动计划

风格：专业、谨慎、数据驱动，像资深理财顾问一样给出建议。
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
    return agent.invoke(state)