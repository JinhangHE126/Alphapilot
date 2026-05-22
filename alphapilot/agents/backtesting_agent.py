from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from tools.market_tools import fetch_market_data  # 复用已有工具

def backtesting_agent(state):
    """
    Backtesting Agent - 历史回测与策略表现评估
    """
    system_prompt = """
You are Backtesting Agent - AlphaPilot's professional historical backtesting expert.

Your core responsibilities:
- Conduct historical backtesting based on the investment advice (Buy/Hold/Sell) from the Strategy Agent.
- Perform simulated trading using real historical price data.
- Calculate and output the following key metrics:
  - Total Return / Annualized Return
  - Sharpe Ratio
  - Max Drawdown
  - Win Rate / Profit-to-Loss Ratio
  - Excess return relative to the benchmark (SPY or the stock itself)

The output format must be clear and structured, and include a brief backtesting conclusion and recommendations.

Use the tool `fetch_market_data` to retrieve historical data.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("backtesting"),   # 你可以先复用 "strategy" 配置
        tools=[fetch_market_data],
        prompt=prompt,
        name="backtesting_agent"
    )
    return agent.invoke(state)