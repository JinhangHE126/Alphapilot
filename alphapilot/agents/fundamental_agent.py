import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from tools.fundamental_tools import analyze_fundamental_request
from config.llm import get_llm

model = get_llm('fundamental')

# def analyze_fundamental_request_tool(symbol: str, user_query: str = ""):
#     """Analyze a company's fundamental data from report PDF."""
#     return analyze_fundamental_request(symbol=symbol, user_query=user_query, model=model)

def analyze_fundamental_request_tool(
    symbol: str, 
    user_query: str = "", 
    model=None
) -> str:                                      # ← 改成 str（最稳）
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
    You are a professional fundamental analyst.
    Your only responsibility is to parse the company's latest financial report PDF and provide a clear, professional, structured fundamental analysis.
    You must use the analyze_fundamental_request tool.
    Always call the tool first, never ask the user for a PDF path.
    Pass:
    - symbol: inferred stock ticker (e.g., TSLA)
    - user_query: full original user message (so tool can auto-detect PDF URL/local path)
    The tool already supports:
    - PDF URL in user text
    - local PDF path in user text
    - automatic fallback to local data/reports/{symbol}*.pdf
    The output must include: revenue growth, EPS growth, gross margin, net profit margin, key highlights, and a one-sentence summary.
    Do not include stock price trends, technical indicators, news, or investment advice.
    """
)

# 导出供 workflow 使用
__all__ = ["fundamental_agent"]