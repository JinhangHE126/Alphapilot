from langgraph.prebuilt import create_react_agent
from tools.news_tools import fetch_recent_news_and_sentiment,retrieve_news_context
from config.llm import get_llm


model = get_llm("news")
def fetch_recent_news_and_sentiment_tool(symbol: str) -> str:
    return fetch_recent_news_and_sentiment(symbol=symbol, model=model)


news_agent = create_react_agent(
    model=model,
    tools=[fetch_recent_news_and_sentiment, retrieve_news_context],
    name="news_sentiment_expert",
    prompt="""
    You are a professional sentiment and news analyst.
    Your only responsibility is to fetch the latest news, extract key events, and perform sentiment analysis.
    You must use the fetch_recent_news_and_sentiment tool.
    The output must include: overall sentiment, sentiment score, key events, and a one-sentence summary.
    Do not include stock price analysis, technical analysis, or investment advice.
    """
)

__all__ = ["news_agent"]