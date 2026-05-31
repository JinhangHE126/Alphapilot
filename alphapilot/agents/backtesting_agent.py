from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from tools.market_tools import fetch_market_data

def backtesting_agent(state):
    """
    Backtesting Agent - v4 硬拦截版
    """
    ep = state.get("evidence_packet", {})
    ep_facts = ep.get("facts", []) if ep else []
    has_price_data = any(
        f.get("field") in ("current_price", "price_change_pct") for f in ep_facts
    )
    ep_score = ep.get("evidence_score", 0) if ep else 0

    if not has_price_data or ep_score < 50:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## Backtesting Report: NOT AVAILABLE\n"
                    "- Reason: Insufficient historical price data\n"
                    "- Required: 60+ days of daily OHLCV data"
                ),
            }],
        }

    system_prompt = """
You are Backtesting Agent - AlphaPilot's professional historical backtesting expert.

Your core responsibilities:
- Use `fetch_market_data` to retrieve historical price data.
- Simulate trading based on the Strategy Agent's Buy/Hold/Sell signal.
- Calculate: Total Return, Annualized Return, Sharpe Ratio, Max Drawdown, Win Rate.
- Compare against benchmark (SPY or buy-and-hold).

Output a structured report. If data insufficient, state clearly.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("backtesting"),
        tools=[fetch_market_data],
        prompt=prompt,
        name="backtesting_agent"
    )
    return agent.invoke(state)