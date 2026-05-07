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


AGENT_LLM_ROUTES = {
    "market": {
        # "profile": "gemini_fast",
        "profile": "deepseek_fast", 
        "temperature": 0.1,
        "max_retries": 5,
        "timeout": 180,
    },
    "news": {
        "profile": "grok_fast",
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
}

# def get_llm(agent: str = "market"):
#     """获取 LLM，并自动使用该 Agent 专属代理"""
#     """获取 LLM（已加入调试信息）"""
#     route = AGENT_LLM_ROUTES[agent]
#     profile = LLM_PROFILES[route["profile"]]
#     proxy_url = get_proxy_for_agent(agent)   # 假设你已导入

#     print(f"🚀 [LLM] {agent.upper():12} → {profile['model']:25} | proxy: {proxy_url or '直连'} | temp={route['temperature']}", flush=True)
#     route = AGENT_LLM_ROUTES[agent]
#     profile = LLM_PROFILES[route["profile"]]
#     provider = profile["provider"]

#     # 动态获取该 Agent 对应的代理
#     proxy_url = get_proxy_for_agent(agent)

#     if provider == "gemini":
#         # 【关键修改】让 Gemini 也走代理
#         return ChatGoogleGenerativeAI(
#             model=profile["model"],
#             api_key=profile["api_key"],
#             temperature=route["temperature"],
#             max_retries=route["max_retries"],
#             timeout=route["timeout"],
#             # Gemini 代理配置（两种写法都兼容）
#             client_options={
#                 "proxies": {
#                     "http": proxy_url,
#                     "https": proxy_url,
#                 } if proxy_url else None
#             } if proxy_url else None,
#         )

#     if provider == "openai_compatible":
#         return ChatOpenAI(
#             model=profile["model"],
#             api_key=profile["api_key"],
#             base_url=profile["base_url"],
#             temperature=route["temperature"],
#             max_retries=route["max_retries"],
#             timeout=route["timeout"],
#             openai_proxy=proxy_url,          # Grok 和 DeepSeek 已经走代理
#         )

#     raise ValueError(f"Unsupported LLM provider: {provider}")

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
# PROXIES = {
#     "market": os.getenv("MARKET_PROXY", "http://127.0.0.1:7896"),
#     "news": os.getenv("NEWS_PROXY", "http://127.0.0.1:7898"),
#     "llm": os.getenv("LLM_PROXY", "http://127.0.0.1:7899"),
# }


# LLM_PROFILES = {
#     "gemini_fast": {
#         "provider": "gemini",
#         "model": os.getenv("GEMINI_FAST_MODEL", "gemini-2.5-flash"),
#         "api_key": os.getenv("GOOGLE_API_KEY"),
#     },
#     "gemini_balanced": {
#         "provider": "gemini",
#         "model": os.getenv("GEMINI_BALANCED_MODEL", "gemini-2.5-flash"),
#         "api_key": os.getenv("GOOGLE_API_KEY"),
#     },
#     "grok_fast": {
#         "provider": "openai_compatible",
#         "model": os.getenv("GROK_MODEL", "grok-4-1-fast-reasoning"),
#         "api_key": os.getenv("XAI_API_KEY"),
#         "base_url": "https://api.x.ai/v1",
#     },
#     "deepseek_fast": {
#         "provider": "openai_compatible",
#         "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
#         "api_key": os.getenv("DEEPSEEK_API_KEY"),
#         "base_url": "https://api.deepseek.com",
#     },
#     "deepseek_reasoner": {
#         "provider": "openai_compatible",
#         "model": os.getenv("DEEPSEEK_REASONER_MODEL", "deepseek-reasoner"),
#         "api_key": os.getenv("DEEPSEEK_API_KEY"),
#         "base_url": "https://api.deepseek.com",
#     },
# }


# AGENT_LLM_ROUTES = {
#     "market": {
#         "profile": "gemini_fast",
#         "temperature": 0.1,
#         "max_retries": 5,
#         "timeout": 60,
#     },
#     "news": {
#         # "profile": os.getenv("NEWS_LLM_PROFILE", "grok-4-1-fast-reasoning"),
#         "profile": "grok_fast",
#         "temperature": 0.1,
#         "max_retries": 5,
#         "timeout": 60,
#     },
#     "fundamental": {
#         "profile": "gemini_balanced",
#         "temperature": 0.1,
#         "max_retries": 5,
#         "timeout": 90,
#     },
#     "strategy": {
#         "profile": "deepseek_reasoner",
#         "temperature": 0.2,
#         "max_retries": 5,
#         "timeout": 120,
#     },
#     "risk": {
#         "profile": "deepseek_reasoner",
#         "temperature": 0.15,
#         "max_retries": 5,
#         "timeout": 120,
#     },
# }


# def get_llm(agent: str = "market"):
#     route = AGENT_LLM_ROUTES[agent]
#     profile = LLM_PROFILES[route["profile"]]
#     provider = profile["provider"]
#     if provider == "gemini":
#         return ChatGoogleGenerativeAI(
#             model=profile["model"],
#             api_key=profile["api_key"],
#             temperature=route["temperature"],
#             max_retries=route["max_retries"],
#             timeout=route["timeout"],
#         )
#     if provider == "openai_compatible":
#         return ChatOpenAI(
#             model=profile["model"],
#             api_key=profile["api_key"],
#             base_url=profile["base_url"],
#             temperature=route["temperature"],
#             max_retries=route["max_retries"],
#             timeout=route["timeout"],
#             openai_proxy=PROXIES["llm"],
#         )
#     raise ValueError(f"Unsupported LLM provider: {provider}")


# def get_proxy(service: str = "llm") -> str | None:
#     """返回requests/httpx/ aiohttp 可直接使用的 proxies 格式"""
#     return PROXIES.get(service)
# def get_requests_proxies(service: str = "llm") -> dict | None:
#     """返回requests/httpx/ aiohttp 可直接使用的 proxies 格式"""
#     proxy = PROXIES.get(service)
#     if not proxy:
#         return None
#     return{
#         "http": proxy,
#         "https": proxy,
#     }
