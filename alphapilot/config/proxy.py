import os
from dotenv import load_dotenv

load_dotenv()

# ==================== 所有代理配置（最终版） ====================
MARKET_PROXY = os.getenv("MARKET_PROXY", "http://127.0.0.1:7896")
NEWS_PROXY = os.getenv("NEWS_PROXY", "http://127.0.0.1:7898")
LLM_PROXY = os.getenv("LLM_PROXY", "http://127.0.0.1:7899")
FUNDAMENTAL_PROXY = os.getenv("FUNDAMENTAL_PROXY", "http://127.0.0.1:7901")
REASONER_PROXY = os.getenv("REASONER_PROXY", "http://127.0.0.1:7900")
# xAI Embedding（Chroma）专用；空字符串视为未设置。端口须与本机代理监听一致（常见笔误 7998→7898）
_EMB_RAW = os.getenv("EMBEDDING_PROXY")
EMBEDDING_PROXY = _EMB_RAW.strip() if (_EMB_RAW and _EMB_RAW.strip()) else None

def get_proxy_for_agent(agent: str) -> str | None:
    """根据 Agent 类型返回对应代理地址（已按方案一配置）"""
    proxies = {
        "market": MARKET_PROXY or LLM_PROXY,
        "news": NEWS_PROXY,
        "llm": LLM_PROXY,
        "fundamental": FUNDAMENTAL_PROXY or LLM_PROXY,
        "strategy": REASONER_PROXY or LLM_PROXY,         # ← 独立 7900
        "risk": REASONER_PROXY or LLM_PROXY,             # ← 独立 7900
        "portfolio": REASONER_PROXY or LLM_PROXY,        # 复用推理代理
        "backtesting": REASONER_PROXY or LLM_PROXY,      # 回测复用推理代理
        "recommendation": REASONER_PROXY or LLM_PROXY,    # 推荐复用推理代理
        "optimization": REASONER_PROXY or LLM_PROXY,      # 组合优化复用推理代理
        "alert": REASONER_PROXY or LLM_PROXY,              # 警报复用推理代理
        "orchestrator": REASONER_PROXY or LLM_PROXY,
        "bull_researcher": REASONER_PROXY or LLM_PROXY,
        "bear_researcher": REASONER_PROXY or LLM_PROXY,
        "embedding": EMBEDDING_PROXY or NEWS_PROXY or REASONER_PROXY or LLM_PROXY,
    }
    proxy = proxies.get(agent)
    return proxy

def get_requests_proxies(agent: str) -> dict[str, str] | None:
    """返回 requests / httpx 使用的格式"""
    proxy = get_proxy_for_agent(agent)
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def get_embedding_proxy_candidates() -> list[str | None]:
    """xAI embeddings：先试 NEWS 出口（通常已与 Grok/HTTPS 验证过），再试 EMBEDDING_PROXY，避免错误端口长时间占用。"""
    ordered = [
        NEWS_PROXY,
        EMBEDDING_PROXY,
        REASONER_PROXY,
        LLM_PROXY,
        None,
    ]
    seen: set[str | None] = set()
    out: list[str | None] = []
    for p in ordered:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out



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