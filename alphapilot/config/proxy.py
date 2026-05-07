import os
from dotenv import load_dotenv

load_dotenv()

# ==================== 所有代理配置（最终版） ====================
MARKET_PROXY = os.getenv("MARKET_PROXY", "http://127.0.0.1:7896")
NEWS_PROXY = os.getenv("NEWS_PROXY", "http://127.0.0.1:7898")
LLM_PROXY = os.getenv("LLM_PROXY", "http://127.0.0.1:7899")
FUNDAMENTAL_PROXY = os.getenv("FUNDAMENTAL_PROXY", "http://127.0.0.1:7901")
REASONER_PROXY = os.getenv("REASONER_PROXY", "http://127.0.0.1:7900")

def get_proxy_for_agent(agent: str) -> str | None:
    """根据 Agent 类型返回对应代理地址（已按方案一配置）"""
    proxies = {
        # "market": MARKET_PROXY,
        "market": None, # 直连
        "news": NEWS_PROXY,
        "llm": LLM_PROXY,
        # "fundamental": FUNDAMENTAL_PROXY or LLM_PROXY,   # ← 独立 7901
        "fundamental": None, # 直连
        "strategy": REASONER_PROXY or LLM_PROXY,         # ← 独立 7900
        "risk": REASONER_PROXY or LLM_PROXY,             # ← 独立 7900
    }
    proxy = proxies.get(agent)
    return proxy

def get_requests_proxies(agent: str) -> dict[str, str] | None:
    """返回 requests / httpx 使用的格式"""
    proxy = get_proxy_for_agent(agent)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}



# import os
# from dotenv import load_dotenv
# load_dotenv()

# MARKET_PROXY = os.getenv("MARKET_PROXY", "http://127.0.0.1:7896")
# NEWS_PROXY = os.getenv("NEWS_PROXY", "http://127.0.0.1:7898")
# LLM_PROXY = os.getenv("LLM_PROXY", "http://127.0.0.1:7899")
# Fundamental_PROXY = os.getenv("FUNDAMENTAL_PROXY", "http://127.0.0.1:7901")
# REASONER_PROXY = os.getenv("REASONER_PROXY", "http://127.0.0.1:7900")   # strategy + risk 共用



# def get_proxy_for_agent(agent: str) -> str | None:
#     """
#     根据 Agent 类型返回对应的代理地址
#     """
#     proxies = {
#         "market": MARKET_PROXY,
#         "news": NEWS_PROXY,
#         "llm": LLM_PROXY,
#         "fundamental": LLM_PROXY,
#         "strategy": LLM_PROXY,
#         "risk": LLM_PROXY,
#     }
#     return proxies[agent]


# def get_requests_proxies(agent: str) -> dict[str, str] | None:
#     """
#     返回requests/httpx/ aiohttp 可直接使用的 proxies 格式
#     """
#     proxy = get_proxy_for_agent(agent)
#     if not proxy:
#         return None
#     return {
#         "http": proxy,
#         "https": proxy,
#     }