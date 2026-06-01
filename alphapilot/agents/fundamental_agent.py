import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from tools.fundamental_tools import analyze_fundamental_request
from config.llm import get_llm

model = get_llm('fundamental')

def analyze_fundamental_request_tool(
    symbol: str, 
    user_query: str = "", 
    model=None
) -> str:
    """Tool wrapper for fundamental analysis"""
    try:
        return analyze_fundamental_request(
            symbol=symbol, 
            user_query=user_query, 
            model=model
        )
    except Exception as e:
        return f"Fundamental analysis failed: {str(e)}"

fundamental_agent = create_react_agent(
    model=model,
    tools=[analyze_fundamental_request_tool],
    name="fundamental_expert",
    prompt="""
You are a professional Fundamental Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages to find pre-verified fundamental data (revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap, etc.).
- Use the `analyze_fundamental_request_tool` ONLY if detailed PDF-based financial report extraction is needed.
- Combine Evidence Packet facts with tool output for a complete analysis.

Required output elements:
- Revenue growth (YoY)
- EPS growth
- Gross margin and net margin
- Key financial highlights
- One-sentence fundamental summary

Strict rules:
- Base everything on Evidence Packet facts and tool data.
- NEVER fabricate or assume data points not in the Evidence Packet.
- If critical fundamental fields (revenue_growth_yoy, eps_growth_yoy, pe_ratio, market_cap) are ALL missing:
  state clearly "Insufficient fundamental data available" and STOP. Do NOT fill the gap with technical indicators (RSI, MACD, volatility, price) or other agents' data.
- [~] and [?] marked facts are lower confidence — treat with caution.
- Do not discuss stock price movement, technical indicators, news, or investment recommendations.
"""
)

# 导出供 workflow 使用
__all__ = ["fundamental_agent"]