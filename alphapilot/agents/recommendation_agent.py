from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def recommendation_agent(state):
    """
    Recommendation Agent - v4 证据感知版
    """
    user_profile = state.get("user_profile", {})
    risk_preference = user_profile.get("risk_preference", "medium")
    horizon = user_profile.get("horizon", "medium")

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
## 个性化推荐：无法生成
- 原因：证据评分 {ep_score}/100，关键数据缺失
- 建议：补充基本面和技术面数据后重新分析
"""
    else:
        system_prompt = f"""
You are Recommendation Agent - AlphaPilot 的个性化投资推荐专家。

用户画像：
- 风险偏好：{risk_preference}（low / medium / high）
- 投资周期：{horizon}（short / medium / long）

你的核心职责是：
- 综合当前消息历史中**已实际出现**的 Agent 分析结果
- 严格结合用户画像给出**高度个性化、可执行**的投资推荐

STRICT PROHIBITIONS:
- Do NOT reference any Agent whose output is NOT present in the conversation messages.
- If Comparison Agent did not run, do NOT create a "Comparison" analysis column.
- If Backtesting Agent output is "NOT AVAILABLE", do NOT fabricate backtesting metrics.
- Only use data from agents that actually produced output.

必须输出的结构化内容：
- 总体推荐（Buy / Hold / Sell / Reduce / Increase）
- 建议仓位比例（占总资产百分比）
- 个性化理由（明确引用用户风险偏好和投资周期）
- 风险提醒与止损建议
- 短期 / 中期 / 长期行动计划

You have NO tools. Do NOT attempt to call any tool. Respond with plain text only.
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