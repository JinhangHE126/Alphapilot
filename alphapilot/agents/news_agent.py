from langgraph.prebuilt import create_react_agent
from tools.news_tools import fetch_recent_news_and_sentiment
from config.llm import get_llm


model = get_llm("news")
def fetch_recent_news_and_sentiment_tool(symbol: str) -> str:
    """Fetch latest news headlines and perform sentiment analysis for a given stock symbol."""
    return fetch_recent_news_and_sentiment(symbol=symbol, model=model)


news_agent = create_react_agent(
    model=model,
    tools=[fetch_recent_news_and_sentiment_tool],
    name="news_sentiment_expert",
    prompt="""
You are a professional News and Sentiment Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages to find pre-verified news headlines and context.
- Use the `fetch_recent_news_and_sentiment` tool to get current news and sentiment data.
- Combine Evidence Packet facts with tool output for accurate sentiment analysis.

Required output structure:
- Overall sentiment (Positive / Neutral / Negative)
- Sentiment score (0-1)
- Key events (bullet points)
- One-sentence summary

Strict rules:
- Base everything on Evidence Packet facts and tool data.
- [~] marked news facts in Evidence Packet are single-source and not cross-verified — mark accordingly.
- Do not discuss stock price trends, technical indicators, or investment advice.
"""
)

__all__ = ["news_agent"]