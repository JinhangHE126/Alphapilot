import os
from dotenv import load_dotenv
load_dotenv()

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
    prompt="""
    You are a professional technical market analyst.
    Your only responsibility is to use the `fetch_market_data` tool, then provide a clear and professional technical analysis based strictly on the returned data.

    Rules:
    - Always call `fetch_market_data` before answering.
    - Base the analysis only on the tool output. Do not assume or invent missing information.
    - The response must include: current price, RSI, MACD, and volatility.
    - Briefly explain what these indicators suggest about momentum, trend, and risk.
    - End with a concise risk note.
    - Do not discuss fundamentals, news, macro events, or provide investment advice, trade recommendations, or price targets.
    """
)