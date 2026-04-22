import os
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from tools.market_tools import fetch_market_data


model = ChatGoogleGenerativeAI(
    model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1,
)

market_agent = create_react_agent(
    model=model,
    tools=[fetch_market_data],
    name="market_data_expert",
    prompt="你是一位专业市场数据分析师，只负责提供价格、成交量、技术指标，绝不做基本面或情绪分析。"
)