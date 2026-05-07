import json
import os
import re
from contextlib import contextmanager
from typing import List

import yfinance as yf
from pydantic import BaseModel, Field

from config.llm import get_llm
from config.proxy import get_proxy_for_agent
from rag.vectorstore import rag

# model = get_llm("news")


@contextmanager
def proxy_env(agent: str):
    proxy = get_proxy_for_agent(agent)

    old_values = {
        "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
        "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
        "http_proxy": os.environ.get("http_proxy"),
        "https_proxy": os.environ.get("https_proxy"),
        "ALL_PROXY": os.environ.get("ALL_PROXY"),
        "all_proxy": os.environ.get("all_proxy"),
    }

    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy
    os.environ.pop("ALL_PROXY", None)
    os.environ.pop("all_proxy", None)

    try:
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _fetch_news_list(symbol: str):
    with proxy_env("news"):
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

    title = item.get("title") or content.get("title") or ""
    publisher = item.get("publisher") or content.get("provider", {}).get("displayName", "") or ""
    summary = item.get("summary") or content.get("summary") or ""

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


def fetch_recent_news_and_sentiment(symbol: str, model=None) -> str:
    """Fetch latest news and return validated sentiment JSON string."""
    try:
        news_list = _fetch_news_list(symbol)
        if not news_list:
            raise ValueError(f"No recent news found for {symbol}")

        normalized_news = [_extract_news_item(item) for item in news_list]
        normalized_news = [
            item for item in normalized_news if item["title"] or item["summary"] or item["link"]
        ]
        if not normalized_news:
            raise ValueError(f"News payload is empty or unrecognized for {symbol}")

        news_text = "\n\n".join(
            [
                (
                    f"Title: {item['title']}\n"
                    f"Publisher: {item['publisher']}\n"
                    f"Summary: {item['summary']}\n"
                    f"Link: {item['link']}"
                )
                for item in normalized_news
            ]
        )

        if model is None:
            from config.llm import get_llm
            model = get_llm("news")

        prompt = f"""
        Please analyze the latest news below about {symbol} for sentiment.
        Return strict JSON format that matches the following Pydantic schema:
        {NewsSentimentData.model_json_schema()}

        News content:
        {news_text[:6000]}
        """

        response = model.invoke(prompt)
        raw_content = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw_content, list):
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
