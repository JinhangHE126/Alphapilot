from langgraph.prebuilt import create_react_agent
from tools.news_tools import fetch_recent_news_and_sentiment, NewsSentimentData
from pydantic import BaseModel
from config.llm import get_llm


model = get_llm()

class NewsOutput(BaseModel):
    """Agent output schema."""
    analysis: str

news_agent = create_react_agent(
    model=model,
    tools=[fetch_recent_news_and_sentiment],
    name="news_sentiment_expert",
    prompt="""
    You are a professional sentiment and news analyst.
    Your only responsibility is to fetch the latest news, extract key events, and perform sentiment analysis.
    You must use the fetch_recent_news_and_sentiment tool.
    The output must include: overall sentiment, sentiment score, key events, and a one-sentence summary.
    Do not include stock price analysis, technical analysis, or investment advice.
    """,
    response_format=NewsOutput
)

__all__ = ["news_agent"]