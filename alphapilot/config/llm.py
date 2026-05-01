import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv()

"""
    Multi-Model Support

    market_agent      -> Gemini fast
    news_agent        -> Grok
    fundamental_agent -> Gemini balanced
    strategy_agent    -> DeepSeek reasoner
"""


# def get_llm(temperature: float = 0.1, max_retries: int = 3):
#     return ChatGoogleGenerativeAI(
#         model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
#         api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=temperature,
#         max_retries=max_retries,
#     )

# alphapilot/config/llm.py




PROXIES = {
    "market": os.getenv("MARKET_PROXY", "http://127.0.0.1:7896"),
    "news": os.getenv("NEWS_PROXY", "http://127.0.0.1:7898"),
    "llm": os.getenv("LLM_PROXY", "http://127.0.0.1:7899"),
}


LLM_PROFILES = {
    "gemini_fast": {
        "provider": "gemini",
        "model": os.getenv("GEMINI_FAST_MODEL", "gemini-2.5-flash"),
        "api_key": os.getenv("GOOGLE_API_KEY"),
    },
    "gemini_balanced": {
        "provider": "gemini",
        "model": os.getenv("GEMINI_BALANCED_MODEL", "gemini-2.5-flash"),
        "api_key": os.getenv("GOOGLE_API_KEY"),
    },
    "grok_fast": {
        "provider": "openai_compatible",
        "model": os.getenv("GROK_MODEL", "grok-4-1-fast-reasoning"),
        "api_key": os.getenv("XAI_API_KEY"),
        "base_url": "https://api.x.ai/v1",
    },
    "deepseek_fast": {
        "provider": "openai_compatible",
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com",
    },
    "deepseek_reasoner": {
        "provider": "openai_compatible",
        "model": os.getenv("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner"),
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com",
    },
}


AGENT_LLM_ROUTES = {
    "market": {
        "profile": "gemini_fast",
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 60,
    },
    "news": {
        "profile": os.getenv("NEWS_LLM_PROFILE", "grok-4-1-fast-reasoning"),
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 60,
    },
    "fundamental": {
        "profile": "gemini_balanced",
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 90,
    },
    "strategy": {
        "profile": "deepseek_reasoner",
        "temperature": 0.2,
        "max_retries": 5,
        "timeout": 120,
    },
}


def get_llm(agent: str = "market"):
    route = AGENT_LLM_ROUTES[agent]
    profile = LLM_PROFILES[route["profile"]]
    provider = profile["provider"]
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=profile["model"],
            api_key=profile["api_key"],
            temperature=route["temperature"],
            max_retries=route["max_retries"],
            timeout=route["timeout"],
        )
    if provider == "openai_compatible":
        return ChatOpenAI(
            model=profile["model"],
            api_key=profile["api_key"],
            base_url=profile["base_url"],
            temperature=route["temperature"],
            max_retries=route["max_retries"],
            timeout=route["timeout"],
            openai_proxy=PROXIES["llm"],
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")