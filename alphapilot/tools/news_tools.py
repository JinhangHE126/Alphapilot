import json
import re
import yfinance as yf
from pydantic import BaseModel, Field
from typing import List
from config.llm import get_llm
from config.proxy import get_proxy_for_agent
from rag.vectorstore import rag
try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None

model = get_llm("news")

def _build_yf_session(agent: str):
    """Create yfinance-compatible session (curl_cffi) with per-request proxy."""
    if curl_requests is None:
        return None
    proxy = get_proxy_for_agent(agent)
    session = curl_requests.Session(impersonate="chrome")
    session.proxies = {"http": proxy, "https": proxy}
    return session


def _fetch_news_list(symbol: str):
    """Try proxied session first, then fallback to default yfinance session."""
    session = _build_yf_session("news")
    ticker = yf.Ticker(symbol, session=session) if session is not None else yf.Ticker(symbol)
    news_list = ticker.news[:5]
    if not news_list:
        ticker = yf.Ticker(symbol)
        news_list = ticker.news[:5]
    return news_list


class NewsSentimentData(BaseModel):
    """Structured sentiment data."""
    symbol: str
    overall_sentiment: str = Field(description="Overall sentiment: Positive / Neutral / Negative")
    sentiment_score: float = Field(description="Sentiment score (-1.0 to 1.0)")
    key_events: List[str] = Field(description="Recent key events/news")
    summary: str = Field(description="One-sentence sentiment summary")


def _extract_news_item(item: dict) -> dict:
    """Normalize yfinance news payload across old/new schemas."""
    content = item.get("content") if isinstance(item, dict) else {}
    if not isinstance(content, dict):
        content = {}

    title = (
        item.get("title")
        or content.get("title")
        or ""
    )
    publisher = (
        item.get("publisher")
        or content.get("provider", {}).get("displayName", "")
        or ""
    )
    summary = (
        item.get("summary")
        or content.get("summary")
        or ""
    )

    link = item.get("link", "")
    if not link:
        canonical = content.get("canonicalUrl", {})
        if isinstance(canonical, dict):
            link = canonical.get("url", "")

    return {
        "title": str(title).strip(),
        "publisher": str(publisher).strip(),
        "summary": str(summary).strip(),
        "link": str(link).strip(),
    }


def fetch_recent_news_and_sentiment(symbol: str) -> str:
    """Fetch latest news and return validated sentiment JSON string."""
    try:
        news_list = _fetch_news_list(symbol)
        if not news_list:
            raise ValueError(f"No recent news found for {symbol}")
        
        normalized_news = [_extract_news_item(item) for item in news_list]
        normalized_news = [
            item for item in normalized_news
            if item["title"] or item["summary"] or item["link"]
        ]
        if not normalized_news:
            raise ValueError(f"News payload is empty or unrecognized for {symbol}")

        news_text = "\n\n".join([
            (
                f"Title: {item['title']}\n"
                f"Publisher: {item['publisher']}\n"
                f"Summary: {item['summary']}\n"
                f"Link: {item['link']}"
            )
            for item in normalized_news
        ])

        # 使用 LLM 做情绪分析
        llm = model
        
        prompt = f"""
        Please analyze the latest news below about {symbol} for sentiment.
        Return strict JSON format that matches the following Pydantic schema:
        {NewsSentimentData.model_json_schema()}

        News content:
        {news_text[:6000]}
        """

        response = llm.invoke(prompt)
        raw_content = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw_content, list):
            # Some providers return rich content blocks; keep only text chunks.
            raw_content = "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw_content
            )

        json_match = re.search(r"\{[\s\S]*\}", str(raw_content))
        if not json_match:
            raise ValueError(f"LLM did not return JSON: {raw_content}")

        parsed = json.loads(json_match.group(0))
        parsed["symbol"] = symbol
        validated = NewsSentimentData.model_validate(parsed)
        return validated.model_dump_json()
    except Exception as e:
        raise ValueError(f"Failed to fetch news: {str(e)}")

def retrieve_news_context(symbol: str, query: str) -> str:
    """Retrieve relevant news context from RAG"""
    context = rag.query(f"{symbol} {query}")
    if context:
        return "\n\n".join(context)
    return "No relevant news found."