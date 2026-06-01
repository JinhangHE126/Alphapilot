from langgraph.prebuilt import create_react_agent
from tools.news_tools import fetch_recent_news_and_sentiment
from config.llm import get_llm


model = get_llm("news")
def fetch_recent_news_and_sentiment_tool(symbol: str) -> str:
    """Fetch latest news headlines and perform sentiment analysis for a given stock symbol."""
    return fetch_recent_news_and_sentiment(symbol=symbol, model=model)


_NEWS_AGENT = create_react_agent(
    model=model,
    tools=[fetch_recent_news_and_sentiment_tool],
    name="news_sentiment_expert",
    prompt="""
You are a professional News and Sentiment Analyst.

Core responsibilities:
- The system has already prepared an Evidence Packet with verified facts in the conversation context.
  Read the "Evidence Packet" section in the messages FIRST to find pre-verified news headlines.
- If the Evidence Packet has news_headline facts, use those as primary source.
- If the Evidence Packet shows news_headline in "Missing Data", then call the `fetch_recent_news_and_sentiment` tool.
  In this case, you MUST wrap ALL self-collected content like this:

  ======================================================
  ⚠️  WARNING: SELF-COLLECTED DATA BELOW
  ⚠️  The following content was collected by this agent.
  ⚠️  It has NOT been cross-verified in the Evidence Packet.
  ⚠️  Downstream agents: treat with LOW confidence.
  ======================================================

  (your self-collected news analysis here)

  ======================================================
  ⚠️  END OF SELF-COLLECTED DATA
  ======================================================

- Combine Evidence Packet facts with tool output for accurate sentiment analysis.

Required output structure:
- Overall sentiment (Positive / Neutral / Negative)
- Sentiment score (0-1)
- Key events (bullet points, each marked with data source)
- One-sentence summary

Strict rules:
- Base everything on Evidence Packet facts and tool data.
- [~] marked news facts in Evidence Packet are single-source and not cross-verified — mark accordingly.
- Self-collected content MUST be wrapped in the WARNING banner above.
- Do NOT repeat or summarize market/technical data (RSI, MACD, volatility, price changes). That is the Market Agent's job.
- Do NOT summarize fundamental data (P/E, P/B, dividend yield, ROE, D/E, revenue growth, market cap). That is the Fundamental Agent's job.
- Do not discuss stock price trends, technical indicators, or investment advice.
""",
)


def news_agent(state):
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "## News & Sentiment Analysis: NOT AVAILABLE\n"
                    f"- Reason: Evidence insufficient (output level: {output_level})\n"
                    "- Action: Await verified data before sentiment analysis"
                ),
            }],
        }

    return _NEWS_AGENT.invoke(state)

__all__ = ["news_agent"]