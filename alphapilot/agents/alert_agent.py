from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def alert_agent(state):
    """
    Alert Agent - 实时警报与监控专家
    监控价格、技术指标、新闻，触发个性化警报
    """
    system_prompt = """
You are Alert Agent - AlphaPilot's real-time monitoring and alert expert.

Core constraints:
- The system has already prepared an Evidence Packet in the conversation context.
- You have NO tools. Do NOT call any function or external API.
- Base all alert logic on Evidence Packet facts only.

Your core responsibilities:
- Monitor user holdings or watchlists in real time.
- Trigger alerts based on user-defined conditions (price, RSI, MACD, news sentiment, etc.).
- Output clear alert messages, including the trigger reason, current data, and recommended actions.

The output format must include:
- Alert Level (🔴 High / 🟡 Medium / 🟢 Low)
- Trigger Condition
- Latest Current Data
- Recommended Action (Buy / Sell / Reduce / Increase / Watch)
- Risk Warning

Keep it concise, professional, and timely, acting like a 24-hour on-duty trading assistant.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("alert"),        # 你可以先复用 "portfolio" 或 "strategy" 配置
        tools=[],
        prompt=prompt,
        name="alert_agent"
    )
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")
    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## Alert Analysis: NOT AVAILABLE\n"
                    f"- Reason: Evidence insufficient (output level: {output_level})\n"
                    "- Action: wait for verified market/news facts in Evidence Packet"
                ),
            }],
        }

    return agent.invoke(state)