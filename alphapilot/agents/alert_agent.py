from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from tools.market_tools import fetch_market_data  # 用于实时数据监控

def alert_agent(state):
    """
    Alert Agent - 实时警报与监控专家
    监控价格、技术指标、新闻，触发个性化警报
    """
    system_prompt = """
You are Alert Agent - AlphaPilot's real-time monitoring and alert expert.

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
        tools=[fetch_market_data],
        prompt=prompt,
        name="alert_agent"
    )
    return agent.invoke(state)