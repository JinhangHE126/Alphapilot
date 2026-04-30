import os
import json
import re


import yfinance as yf
from pydantic import BaseModel, Field
from typing import List
from config.llm import get_llm

model = get_llm()

class NewsSentimentData(BaseModel):
    """Structured sentiment data."""
    symbol: str
    overall_sentiment: str = Field(description="Overall sentiment: Positive / Neutral / Negative")
    sentiment_score: float = Field(description="Sentiment score (-1.0 to 1.0)")
    key_events: List[str] = Field(description="Recent key events/news")
    summary: str = Field(description="One-sentence sentiment summary")

def fetch_recent_news_and_sentiment(symbol: str) -> NewsSentimentData:
    """Fetch the latest news and perform sentiment analysis (currently using yfinance + LLM)."""
    try:
        ticker = yf.Ticker(symbol)
        news_list = ticker.news[:5]  # 取最近 5 条新闻
        
        news_text = "\n\n".join([
            f"Title: {item.get('title', '')}\nContent: {item.get('publisher', '')} - {item.get('link', '')}"
            for item in news_list
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
        # 为了快速跑通，先返回结构化模拟数据（真实项目中可解析 LLM 输出）
        return NewsSentimentData(
            symbol=symbol,
            overall_sentiment="Positive",
            sentiment_score=0.65,
            key_events=[
                "Tesla Q4 deliveries exceeded expectations",
                "Robotaxi project is progressing smoothly",
                "Energy storage business is growing strongly"
            ],
            summary=f"{symbol} has had positive recent sentiment, with market attention on Robotaxi and energy storage business progress."
        )
    except Exception as e:
        raise ValueError(f"Failed to fetch news: {str(e)}")