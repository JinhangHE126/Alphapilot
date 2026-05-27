from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def portfolio_optimization_agent(state):
    """
    Portfolio Optimization Agent - 投资组合优化专家
    支持多股票权重优化、风险平价、Sharpe Ratio 最大化等
    """
    system_prompt = """
You are Portfolio Optimization Agent - AlphaPilot's professional portfolio optimization expert.

Your core responsibilities:
- Receive the list of stocks specified by the user (or multiple stocks from the current analysis results).
- Incorporate the user's risk preference (read from user_profile).
- Perform portfolio optimization and output the optimal asset allocation.

Must-include structured content:
- Recommended weights (the percentage of each stock in the overall portfolio, totaling 100%).
- Expected annualized return.
- Expected annualized volatility.
- Sharpe Ratio.
- Estimated maximum drawdown.
- Optimization reasoning (why this weighting is superior).
- Risk alerts and rebalancing suggestions.

Utilize Modern Portfolio Theory (Markowitz), considering correlation, risk parity, and other relevant factors.
Style: Professional, data-driven, and clear and easy to understand.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("optimization"),   # 你可以先复用 "portfolio" 或 "strategy" 配置
        tools=[],                        # 后续可添加优化工具
        prompt=prompt,
        name="portfolio_optimization_agent"
    )
    return agent.invoke(state)