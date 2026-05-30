import json
from typing import Any, Generator

from graph.workflow import app as langgraph_app
from graph.user_profile import load_user_profile


AGENT_LABELS: dict[str, dict[str, str]] = {
    "market_data_expert": {"label": "Market", "icon": "\U0001f4c8"},
    "fundamental_expert": {"label": "Fundamental", "icon": "\U0001f4ca"},
    "news_expert": {"label": "News", "icon": "\U0001f4f0"},
    "risk_expert": {"label": "Risk", "icon": "\u26a0\ufe0f"},
    "strategy_expert": {"label": "Strategy", "icon": "\U0001f3af"},
    "recommendation_agent": {"label": "Recommendation", "icon": "\u2b50"},
    "comparison_agent": {"label": "Comparison", "icon": "\U0001f500"},
    "backtesting_agent": {"label": "Backtest", "icon": "\U0001f4c9"},
    "alert_agent": {"label": "Alert", "icon": "\U0001f514"},
    "portfolio_optimization_agent": {"label": "Portfolio", "icon": "\U0001f4a0"},
    "supervisor": {"label": "Supervisor", "icon": "\U0001f9e0"},
    "guard_agent": {"label": "Guard", "icon": "\U0001f6e1\ufe0f"},
}


def _safe_text(message_obj: Any) -> str:
    if hasattr(message_obj, "content"):
        return str(message_obj.content)
    return str(message_obj)


def _extract_text(update: dict) -> str:
    if update.get("final_report"):
        return str(update["final_report"])
    messages = update.get("messages")
    if messages and isinstance(messages, list) and len(messages) > 0:
        return _safe_text(messages[-1])
    return ""


def _run_workflow_sync(user_message: str, stock_symbol: str, user_id: str, thread_id: str) -> dict[str, Any]:
    """Run LangGraph workflow synchronously and return final results."""
    final_report = ""
    recommendation = None

    enriched_message = f"[股票代码: {stock_symbol}] {user_message}"

    initial_state = {
        "stock_symbol": stock_symbol,
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
    }
    config = {"configurable": {"thread_id": thread_id}}

    for chunk in langgraph_app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if update.get("final_report"):
                final_report = str(update["final_report"])
            if node_name == "recommendation_agent" and update.get("messages"):
                recommendation = _safe_text(update["messages"][-1])

    return {
        "final_report": final_report or "\u5206\u6790\u5b8c\u6210",
        "recommendation": recommendation,
    }


def run_analysis_once(
    user_message: str,
    stock_symbol: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    return _run_workflow_sync(user_message, stock_symbol, user_id, thread_id)


def run_comparison_once(symbols: list[str], user_id: str) -> dict[str, Any]:
    symbols_str = ", ".join(symbols)
    message = f"\u8bf7\u5bf9\u6bd4\u5206\u6790\u4ee5\u4e0b\u80a1\u7968: {symbols_str}\uff0c\u5305\u62ec\u6280\u672f\u9762\u3001\u57fa\u672c\u9762\u3001\u65b0\u95fb\u60c5\u7eea\u548c\u6295\u8d44\u5efa\u8bae\u7684\u5168\u9762\u5bf9\u6bd4"
    return _run_workflow_sync(message, symbols[0], user_id, f"compare_{user_id}")


def run_backtest_once(symbol: str, strategy_desc: str, user_id: str) -> dict[str, Any]:
    desc = strategy_desc or f"\u5bf9 {symbol} \u7684\u7b56\u7565\u8fdb\u884c\u5386\u53f2\u56de\u6d4b"
    message = f"\u8bf7\u5bf9 {symbol} \u8fdb\u884c\u5386\u53f2\u56de\u6d4b\u5206\u6790\u3002\u7b56\u7565\u63cf\u8ff0: {desc}\u3002\u8bf7\u8f93\u51fa\u603b\u6536\u76ca\u3001\u5e74\u5316\u6536\u76ca\u3001\u590f\u666e\u6bd4\u7387\u3001\u6700\u5927\u56de\u64a4\u3001\u80dc\u7387\u7b49\u5173\u952e\u6307\u6807"
    return _run_workflow_sync(message, symbol, user_id, f"backtest_{user_id}")


def run_alert_once(symbol: str, condition: str, user_id: str) -> dict[str, Any]:
    cond = condition or f"\u76d1\u63a7 {symbol} \u7684\u4ef7\u683c\u3001RSI\u3001MACD \u7b49\u5173\u952e\u6280\u672f\u6307\u6807\uff0c\u5982\u6709\u5f02\u5e38\u8bf7\u89e6\u53d1\u8b66\u62a5"
    message = f"\u8bf7\u5bf9 {symbol} \u8fdb\u884c\u5b9e\u65f6\u76d1\u63a7\u3002\u89e6\u53d1\u6761\u4ef6: {cond}"
    return _run_workflow_sync(message, symbol, user_id, f"alert_{user_id}")


def run_optimize_once(symbols: list[str], risk_preference: str, user_id: str) -> dict[str, Any]:
    symbols_str = ", ".join(symbols)
    message = f"\u8bf7\u5bf9\u4ee5\u4e0b\u6295\u8d44\u7ec4\u5408\u8fdb\u884c\u4f18\u5316: {symbols_str}\u3002\u98ce\u9669\u504f\u597d: {risk_preference}"
    return _run_workflow_sync(message, symbols[0], user_id, f"optimize_{user_id}")


def stream_analysis_events(
    user_message: str,
    stock_symbol: str,
    user_id: str,
    thread_id: str,
    session_id: str,
) -> Generator[str, None, dict[str, Any]]:
    final_report = ""
    recommendation = None
    guard_check = None

    enriched_message = f"[股票代码: {stock_symbol}] {user_message}"

    initial_state = {
        "stock_symbol": stock_symbol,
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
    }
    config = {"configurable": {"thread_id": thread_id}}

    yield _sse("analysis_start", {
        "session_id": session_id,
        "thread_id": thread_id,
        "stock_symbol": stock_symbol,
        "analysis_type": "analyze",
    })

    for chunk in langgraph_app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            agent_meta = AGENT_LABELS.get(node_name, {"label": node_name, "icon": "\U0001f916"})
            label = agent_meta["label"]
            icon = agent_meta["icon"]

            yield _sse("agent_start", {
                "agent": node_name,
                "label": label,
                "icon": icon,
            })

            content = _extract_text(update)
            if content:
                yield _sse("agent_output", {
                    "agent": node_name,
                    "content": content,
                })

            if update.get("final_report"):
                final_report = str(update["final_report"])
            if node_name == "recommendation_agent" and update.get("messages"):
                recommendation = _safe_text(update["messages"][-1])
            if node_name in ("guard_agent", "guard") and isinstance(update.get("guard_check"), dict) and update["guard_check"]:
                guard_check = update["guard_check"]

            yield _sse("agent_done", {"agent": node_name})

    done_payload = {
        "final_report": final_report or "\u5206\u6790\u5b8c\u6210",
        "recommendation": recommendation,
        "guard_check": guard_check,
    }
    yield _sse("analysis_complete", done_payload)
    return done_payload


def _sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
