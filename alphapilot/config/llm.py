import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from .proxy import get_proxy_for_agent

load_dotenv()

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

_DEFAULT_NEWS_PROFILE = "deepseek_fast"
_news_llm_profile_raw = (os.getenv("NEWS_LLM_PROFILE") or "").strip()
if _news_llm_profile_raw and _news_llm_profile_raw not in LLM_PROFILES:
    print(
        f"⚠️ NEWS_LLM_PROFILE={_news_llm_profile_raw!r} 未知，回退为 {_DEFAULT_NEWS_PROFILE}",
        flush=True,
    )
_NEWS_LLM_PROFILE = (
    _news_llm_profile_raw
    if _news_llm_profile_raw in LLM_PROFILES
    else _DEFAULT_NEWS_PROFILE
)


AGENT_LLM_ROUTES = {
    "market": {
        # "profile": "gemini_fast",
        "profile": "deepseek_fast", 
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 180,
    },
    "news": {
        "profile": _NEWS_LLM_PROFILE,
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 60,
    },
    "fundamental": {
        # "profile": "gemini_balanced",
        "profile": "deepseek_reasoner",
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 300,
    },
    "strategy": {
        "profile": "deepseek_reasoner",
        "temperature": 0.2,
        "max_retries": 5,
        "timeout": 120,
    },
    "risk": {
        "profile": "deepseek_reasoner",
        "temperature": 0.15,
        "max_retries": 5,
        "timeout": 120,
    },
    "orchestrator": {
        "profile": "deepseek_reasoner",
        "temperature": 0.2,
        "max_retries": 5,
        "timeout": 90,
    },
    "guard": {
        "profile": "deepseek_reasoner",
        "temperature": 0.15,
        "max_retries": 5,
        "timeout": 90,
    },
}

def get_llm(agent: str = "market"):
    """获取 LLM（已修复 Gemini base_url 报错 + 增加调试信息）"""
    route = AGENT_LLM_ROUTES[agent]
    profile = LLM_PROFILES[route["profile"]]
    provider = profile["provider"]

    # 动态获取该 Agent 对应的代理地址
    proxy_url = get_proxy_for_agent(agent)

    # ==================== 调试信息（方便我们排查）====================
    print(
        f"🚀 [LLM] {agent.upper():12} → {profile['model']:25} "
        f"| proxy: {proxy_url or '直连'} | temp={route['temperature']} | timeout={route['timeout']}s",
        flush=True
    )

    if provider == "gemini":
        # 【修复版】只传 Gemini 支持的参数，绝不传 base_url 或错误的 client_options
        return ChatGoogleGenerativeAI(
            model=profile["model"],
            api_key=profile["api_key"],
            temperature=route["temperature"],
            max_retries=route["max_retries"],
            timeout=route["timeout"],
            # 暂时不加代理（避免 ValidationError），后续可改用 httpx 方式
        )

    if provider == "openai_compatible":
        # Grok / DeepSeek 继续正常走独立代理
        return ChatOpenAI(
            model=profile["model"],
            api_key=profile["api_key"],
            base_url=profile["base_url"],
            temperature=route["temperature"],
            max_retries=route["max_retries"],
            timeout=route["timeout"],
            openai_proxy=proxy_url,          # ← 关键：使用对应代理
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")

