from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

def comparison_agent(state):
    """
    Comparison Agent - 多股票对比分析专家
    支持同时对比 2~5 只股票，生成结构化对比报告
    """
    system_prompt = """
You are Comparison Agent - AlphaPilot's multi-stock comparative analysis expert.

Your core responsibilities:
- Receive multiple stocks provided by the user (e.g., TSLA, NVDA, AAPL).
- Compare their differences in technicals, fundamentals, news sentiment, strategy recommendations, and risk levels.
- Output clear comparison tables and summary conclusions.

Output must include:
- Stock list and current prices.
- Technical analysis comparison (RSI, MACD, trends).
- Fundamental analysis comparison (Revenue, EPS, gross margin, etc.).
- News sentiment comparison.
- Investment recommendation comparison (Buy/Hold/Sell + reasoning).
- Risk comparison.
- Final recommendation ranking (which one deserves the most attention).

Maintain objectivity and professionalism, and use Markdown tables to present the comparison results.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("comparison"),   # 你可以先复用 "strategy" 配置
        tools=[],                      # 后续可添加对比专用工具
        prompt=prompt,
        name="comparison_agent"
    )
    return agent.invoke(state)