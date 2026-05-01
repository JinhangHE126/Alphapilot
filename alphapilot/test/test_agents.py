

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent

load_dotenv()


def _normalize_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # 兼容 text block / 其他结构
                parts.append(str(item.get("text", item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _contains_any(text, keywords: list[str]) -> bool:
    normalized = _normalize_to_text(text).lower()
    return any(k.lower() in normalized for k in keywords)



def _assert_metric_groups(output: str, metric_groups: dict[str, list[str]]) -> None:
    missing = []
    for group, keywords in metric_groups.items():
        if not _contains_any(output, keywords):
            missing.append(group)

    assert not missing, (
        f"Missing metric groups: {missing}\n"
        f"--- Agent output start ---\n{output}\n--- Agent output end ---"
    )


def test_market_agent():
    """测试 Market Data Agent 输出格式（多语言鲁棒版本）"""
    symbol = "TSLA"
    result = market_agent.invoke({
        "messages": [{"role": "user", "content": f"请分析 {symbol} 的技术面"}]
    })
    output = result["messages"][-1].content

    metric_groups = {
        # 中英繁体（偏粤语书面）同义词
        "price": [
            "Current Price", "Price", "当前价格", "現價", "股价", "股價", "最新价", "最新價"
        ],
        "rsi": [
            "RSI", "Relative Strength Index", "相对强弱指数", "相對強弱指數"
        ],
        "macd": [
            "MACD", "Signal", "Histogram", "异同移动平均", "異同移動平均"
        ],
        "volatility": [
            "Volatility", "波动率", "波動率", "波幅", "20-Day Volatility"
        ],
    }

    _assert_metric_groups(output, metric_groups)
    print("✅ Market Agent 测试通过（多语言断言）")


def test_fundamental_agent():
    """测试 Fundamental Agent 输出格式"""
    symbol = "TSLA"
    result = fundamental_agent.invoke({
        "messages": [{"role": "user", "content": f"请解析 {symbol} 的最新财报"}]
    })
    output = result["messages"][-1].content
    assert any(x in output for x in ["Revenue", "EPS", "毛利率", "收入增长", "gross margin"])
    print("✅ Fundamental Agent 测试通过")


def test_news_agent():
    """测试 News & Sentiment Agent 输出格式"""
    symbol = "TSLA"
    result = news_agent.invoke({
        "messages": [{"role": "user", "content": f"请分析 {symbol} 的最新新闻舆情"}]
    })
    output = result["messages"][-1].content
    assert any(x in output for x in ["Positive", "情绪", "Sentiment", "Key Events"])
    print("✅ News Agent 测试通过")


if __name__ == "__main__":
    test_market_agent()
    test_fundamental_agent()
    test_news_agent()
    print("\n🎉 全部 3 个 Agent 单元测试通过！")