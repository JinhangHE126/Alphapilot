import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.prebuilt import create_react_agent
from tools.fundamental_tools import parse_financial_pdf, FundamentalData
from pydantic import BaseModel
from config.llm import get_llm

model = get_llm()


class FundamentalOutput(BaseModel):
    """Agent output schema."""
    analysis: str

fundamental_agent = create_react_agent(
    model=model,
    tools=[parse_financial_pdf],
    name="fundamental_expert",
    prompt="""
    You are a professional fundamental analyst.
    Your only responsibility is to parse the company's latest financial report PDF and provide a clear, professional, structured fundamental analysis.
    You must use the parse_financial_pdf tool.
    The output must include: revenue growth, EPS growth, gross margin, net profit margin, key highlights, and a one-sentence summary.
    Do not include stock price trends, technical indicators, news, or investment advice.
    """,
    response_format=FundamentalOutput
)

# 导出供 workflow 使用
__all__ = ["fundamental_agent"]