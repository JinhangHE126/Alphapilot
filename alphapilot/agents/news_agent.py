from langgraph.prebuilt import create_react_agent
from tools.news_tools import fetch_recent_news_and_sentiment,retrieve_news_context
from config.llm import get_llm
from tools.rag_tools import retrieve_knowledge


model = get_llm("news")
def fetch_recent_news_and_sentiment_tool(symbol: str) -> str:
    return fetch_recent_news_and_sentiment(symbol=symbol, model=model)


# news_agent = create_react_agent(
#     model=model,
#     tools=[fetch_recent_news_and_sentiment, retrieve_news_context, retrieve_knowledge],
#     name="news_sentiment_expert",
#     prompt="""
#     You are a professional sentiment and news analyst.
#     Your only responsibility is to fetch the latest news, extract key events, and perform sentiment analysis.
#     You must use the fetch_recent_news_and_sentiment tool.
#     The output must include: overall sentiment, sentiment score, key events, and a one-sentence summary.
#     Do not include stock price analysis, technical analysis, or investment advice.
#     """
# )
news_agent = create_react_agent(
    model=model,
    tools=[fetch_recent_news_and_sentiment, retrieve_knowledge],
    name="news_sentiment_expert",
    prompt="""
You are a professional News and Sentiment Analyst.

Core responsibilities:
- First, ALWAYS use the `retrieve_knowledge` tool to gather the latest news, events, or sentiment-related knowledge about the stock.
- Then, call the `fetch_recent_news_and_sentiment` tool to get current news and sentiment data.
- Combine RAG knowledge with the tool output to produce accurate sentiment analysis.

Required output structure:
- Overall sentiment (Positive / Neutral / Negative)
- Sentiment score (0-1)
- Key events (bullet points)
- One-sentence summary

Strict rules:
- Do not discuss stock price trends, technical indicators, or investment advice.
- When using RAG knowledge, clearly cite the source.
"""
)

__all__ = ["news_agent"]