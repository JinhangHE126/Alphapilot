

import os

MARKET_PROXY = os.getenv("MARKET_PROXY", "http://127.0.0.1:7896")
NEWS_PROXY = os.getenv("NEWS_PROXY", "http://127.0.0.1:7898")
LLM_PROXY = os.getenv("LLM_PROXY", "http://127.0.0.1:7899")


def get_proxy_for_agent(agent: str) -> str:
    proxies = {
        "market": MARKET_PROXY,
        "news": NEWS_PROXY,
        "llm": LLM_PROXY,
        "fundamental": LLM_PROXY,
        "strategy": LLM_PROXY,
    }
    return proxies[agent]


def get_requests_proxies(agent: str) -> dict[str, str]:
    proxy = get_proxy_for_agent(agent)
    return {
        "http": proxy,
        "https": proxy,
    }