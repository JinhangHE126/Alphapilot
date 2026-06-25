import json
import re
from typing import Any, Generator

from graph.workflow import app as langgraph_app
from graph.user_profile import load_user_profile


AGENT_LABELS: dict[str, dict[str, str]] = {
    "evidence_packet_builder": {"label": "Evidence Builder", "icon": "\U0001f4e6"},
    "orchestrator": {"label": "Orchestrator", "icon": "\U0001f9e0"},
    "market_data_expert": {"label": "Market", "icon": "\U0001f4c8"},
    "fundamental_expert": {"label": "Fundamental", "icon": "\U0001f4ca"},
    "news_expert": {"label": "News", "icon": "\U0001f4f0"},
    "news_sentiment_expert": {"label": "News & Sentiment", "icon": "\U0001f4f0"},
    "risk_expert": {"label": "Risk", "icon": "\u26a0\ufe0f"},
    "strategy_expert": {"label": "Strategy", "icon": "\U0001f3af"},
    "portfolio_agent": {"label": "Portfolio", "icon": "\U0001f4bc"},
    "recommendation_agent": {"label": "Recommendation", "icon": "\u2b50"},
    "comparison_agent": {"label": "Comparison", "icon": "\U0001f500"},
    "backtesting_agent": {"label": "Backtest", "icon": "\U0001f4c9"},
    "alert_agent": {"label": "Alert", "icon": "\U0001f514"},
    "portfolio_optimization_agent": {"label": "Portfolio Optimization", "icon": "\U0001f4a0"},
    "supervisor": {"label": "Supervisor", "icon": "\U0001f9e0"},
    "guard_agent": {"label": "Guard", "icon": "\U0001f6e1\ufe0f"},
    "debate_stage": {"label": "Debate", "icon": "\u2694\ufe0f"},
    "bull_researcher": {"label": "Bull Researcher", "icon": "\U0001f4c8"},
    "bear_researcher": {"label": "Bear Researcher", "icon": "\U0001f4c9"},
}

REPORT_EXCLUDE_NODES = frozenset({
    "evidence_packet_builder",
    "orchestrator",
    "guard_agent",
    "guard",
})


def _safe_text(message_obj: Any) -> str:
    if hasattr(message_obj, "content"):
        raw = message_obj.content
        if isinstance(raw, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in raw
            )
        return str(raw)
    if isinstance(message_obj, dict):
        content = message_obj.get("content", "")
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
    return str(message_obj)


def _format_agent_content(raw: str) -> str:
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return raw
        lines = []
        for k, v in obj.items():
            label = k.replace("_", " ").title()
            if isinstance(v, (int, float)):
                lines.append(f"- **{label}**: {v}")
            elif isinstance(v, str) and v:
                lines.append(f"- **{label}**: {v}")
            elif isinstance(v, list):
                lines.append(f"- **{label}**: {', '.join(str(i) for i in v)}")
            else:
                lines.append(f"- **{label}**: {v}")
        return "\n".join(lines)
    except (json.JSONDecodeError, ValueError):
        return raw


def _extract_json_block(text: str) -> dict | None:
    """Extract the last JSON code block or raw JSON object from an agent's output text."""
    if not text:
        return None
    # Try fenced JSON blocks first, preferring the last metadata block.
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    for block in reversed(blocks):
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    # Try raw JSON object (find outermost braces on their own)
    start = text.rfind("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1].strip())
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _strip_json_blocks(text: str) -> str:
    """Remove machine-readable JSON blocks before showing agent text in the UI/report."""
    if not text:
        return ""
    without_blocks = re.sub(r"```(?:json)?\s*[\s\S]*?\s*```", "", text).strip()
    without_blocks = re.sub(r"\n?\s*\{[\s\S]*\}\s*$", "", without_blocks).strip()
    if without_blocks.startswith("{") and without_blocks.endswith("}"):
        return ""
    return without_blocks


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_risk_level_payload(payload: dict) -> dict | None:
    """Normalize risk agent JSON into a stable SSE payload."""
    if not isinstance(payload, dict):
        return None

    overall = payload.get("overall_risk_score")
    if overall is None:
        overall = payload.get("risk_score")
    if overall is None:
        return None

    try:
        score = max(0, min(100, int(round(float(overall)))))
    except (TypeError, ValueError):
        return None

    if score == 0 and str(payload.get("volatility_risk", "")).upper() == "N/A":
        return None

    key_risks = payload.get("key_risks", [])
    if not isinstance(key_risks, list):
        key_risks = []

    return {
        "overall_risk_score": score,
        "volatility_risk": str(payload.get("volatility_risk", "")).strip() or None,
        "macro_risk": str(payload.get("macro_risk", "")).strip() or None,
        "stop_loss_suggestion": payload.get("stop_loss_suggestion"),
        "position_suggestion": str(payload.get("position_suggestion", "")).strip() or None,
        "risk_reasoning": str(payload.get("risk_reasoning", "")).strip() or None,
        "key_risks": [str(r).strip() for r in key_risks if str(r).strip()],
    }


def _extract_risk_level(update: dict) -> dict | None:
    """Parse risk_expert output; prefer raw JSON over markdown conversion."""
    messages = update.get("messages")
    if not messages:
        return None
    text = _safe_text(messages[-1]).strip()
    if not text:
        return None

    if text.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                normalized = _normalize_risk_level_payload(payload)
                if normalized:
                    return normalized
        except (json.JSONDecodeError, ValueError):
            pass

    payload = _extract_json_block(text)
    if isinstance(payload, dict):
        return _normalize_risk_level_payload(payload)
    return None


def _format_risk_markdown(raw_json: str) -> str:
    """Convert risk agent JSON into a well-structured Markdown report."""
    import json as _json
    try:
        obj = _json.loads(raw_json)
    except (_json.JSONDecodeError, ValueError):
        return raw_json

    overall = obj.get("overall_risk_score", obj.get("overall_risk", ""))
    vol = obj.get("volatility_risk", "")
    macro = obj.get("macro_risk", "")
    stop = obj.get("stop_loss_suggestion", "")
    position = obj.get("position_suggestion", "")
    reasoning = obj.get("risk_reasoning", "")
    risks = obj.get("key_risks", [])

    # risk level badge
    if isinstance(overall, (int, float)):
        if overall >= 80:
            level = ("🔴", "极高")
        elif overall >= 60:
            level = ("🟠", "较高")
        elif overall >= 40:
            level = ("🟡", "中等")
        else:
            level = ("🟢", "较低")
        score_str = f"{overall}/100"
    else:
        level = ("⚪", "—")
        score_str = str(overall) if overall else "—"

    lines = [
        "---",
        "## 风险评估",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| **综合风险评分** | {level[0]} **{level[1]} ({score_str})** |",
    ]

    if isinstance(vol, (int, float)):
        lines.append(f"| **波动率风险** | **{vol}/100** |")
    if isinstance(macro, (int, float)):
        lines.append(f"| **宏观风险** | **{macro}/100** |")

    lines.append("")

    if stop:
        lines.append("### 止损建议")
        lines.append("")
        lines.append(stop.strip())
        lines.append("")

    if position:
        lines.append("### 仓位建议")
        lines.append("")
        lines.append(position.strip())
        lines.append("")

    if reasoning:
        lines.append("### 风险分析")
        lines.append("")
        lines.append(reasoning.strip())
        lines.append("")

    if risks:
        lines.append("### 关键风险点")
        lines.append("")
        for i, r in enumerate(risks, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _extract_risk_raw_content(update: dict) -> str:
    """Format risk agent JSON as Markdown for frontend display."""
    messages = update.get("messages")
    if not messages:
        return _extract_text(update)
    text = _safe_text(messages[-1]).strip()
    if text.startswith("{"):
        return _format_risk_markdown(text)
    return _extract_text(update)


def _coerce_valuation_scenario(raw: dict | None) -> dict | None:
    """Normalize valuation JSON from Recommendation Agent into a stable SSE payload."""
    if not isinstance(raw, dict):
        return None

    low = _to_float_or_none(raw.get("valuation_low", raw.get("target_price_low")))
    mid = _to_float_or_none(raw.get("valuation_mid", raw.get("target_price_mid")))
    high = _to_float_or_none(raw.get("valuation_high", raw.get("target_price_high")))
    if low is None and mid is None and high is None:
        return None

    return {
        "target_price_low": low,
        "target_price_mid": mid,
        "target_price_high": high,
        "valuation_low": low,
        "valuation_mid": mid,
        "valuation_high": high,
        "upside_pct": _to_float_or_none(raw.get("upside_pct")),
        "downside_pct": _to_float_or_none(raw.get("downside_pct")),
        "consensus_summary": str(raw.get("consensus_summary", "")).strip() or None,
        "source": "recommendation_agent_valuation_scenario",
    }


def _extract_text(update: dict, agent_name: str = "") -> str:
    if update.get("final_report"):
        return str(update["final_report"])
    messages = update.get("messages")
    if messages and isinstance(messages, list) and len(messages) > 0:
        # 按 agent name 过滤消息，避免跨智能体内容污染
        target_msg = None
        if agent_name:
            for m in reversed(messages):
                msg_name = ""
                if hasattr(m, "name"):
                    msg_name = (getattr(m, "name") or "").strip()
                elif isinstance(m, dict):
                    msg_name = str(m.get("name", "") or m.get("additional_kwargs", {}).get("name", "")).strip()
                if msg_name == agent_name:
                    target_msg = m
                    break
        if target_msg is None:
            target_msg = messages[-1]

        text = _safe_text(target_msg)
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return _format_agent_content(stripped)
        if stripped.startswith("{'role':") or stripped.startswith('{"role":'):
            return _format_agent_content(stripped)
        return text
    return ""


def _serialize_debate_side(update: dict, side: str) -> str:
    """Build SSE payload for bull/bear from debate subgraph state."""
    data_key = f"{side}_debate_data"
    arg_key = f"{side}_argument"

    debate_data = update.get(data_key)
    if isinstance(debate_data, dict):
        claims = debate_data.get("claims")
        if isinstance(claims, list) and claims:
            return json.dumps(debate_data, ensure_ascii=False)
        summary = debate_data.get("summary")
        if isinstance(summary, str) and summary.strip():
            return json.dumps(debate_data, ensure_ascii=False)

    argument = update.get(arg_key)
    if isinstance(argument, str) and argument.strip():
        return argument.strip()

    messages = update.get("messages")
    if messages and isinstance(messages, list):
        raw = _safe_text(messages[-1]).strip()
        if raw:
            return raw
    return ""


def _format_strategy_markdown(raw_json: str) -> str:
    """Convert strategy JSON into a well-structured Markdown report for frontend display."""
    import json as _json
    try:
        obj = _json.loads(raw_json)
    except (_json.JSONDecodeError, ValueError):
        return raw_json  # not valid JSON, return as-is

    rec = obj.get("recommendation", "N/A")
    score = obj.get("confidence_score", 0)
    reasoning = obj.get("reasoning", "")
    weight = obj.get("weight_summary", "")
    missing = obj.get("missing_data", [])

    # recommendation badge
    badge_map = {
        "Buy": "买入",
        "Sell": "卖出",
        "Hold": "持有",
        "N/A": "暂无法评估",
    }
    rec_label = badge_map.get(rec, rec)
    rec_icon_map = {"Buy": "🟢", "Sell": "🔴", "Hold": "🟡", "N/A": "⚪"}
    rec_icon = rec_icon_map.get(rec, "⚪")

    lines = [
        "---",
        f"## 策略裁决",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| **最终建议** | {rec_icon} **{rec_label}** |",
        f"| **置信度评分** | **{score}/100** |",
    ]

    if missing:
        lines.append(f"| **缺失数据** | {', '.join(missing)} |")

    lines.append("")

    if reasoning:
        lines.append("### 决策推理")
        lines.append("")
        lines.append(reasoning.strip())
        lines.append("")

    if weight:
        lines.append("### 因子权重分配")
        lines.append("")
        lines.append(weight.strip())
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _extract_strategy_content(update: dict) -> str:
    """Format strategy JSON as Markdown for frontend display."""
    messages = update.get("messages")
    if not messages:
        return _extract_text(update, agent_name="strategy_expert")
    raw = _safe_text(messages[-1]).strip()
    if raw.startswith("{"):
        return _format_strategy_markdown(raw)
    return _extract_text(update, agent_name="strategy_expert")


def _extract_agent_content(node_name: str, update: dict) -> str:
    """Extract agent output; preserve JSON for structured downstream parsers."""
    if node_name == "strategy_expert":
        return _extract_strategy_content(update)
    if node_name == "risk_expert":
        return _extract_risk_raw_content(update)
    if node_name in ("bull_researcher", "bear_researcher"):
        side = "bull" if node_name == "bull_researcher" else "bear"
        debate_content = _serialize_debate_side(update, side)
        if debate_content:
            return debate_content
    return _extract_text(update, agent_name=node_name)


def _iter_stream_chunks(chunk: Any):
    """Normalize LangGraph stream chunks (with or without subgraph namespaces)."""
    if isinstance(chunk, tuple) and len(chunk) == 2:
        _, payload = chunk
        if isinstance(payload, dict):
            yield from payload.items()
        return
    if isinstance(chunk, dict):
        yield from chunk.items()


def _normalize_symbol(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def _run_workflow_sync(user_message: str, stock_symbol: str, user_id: str, thread_id: str, language: str | None = None) -> dict[str, Any]:
    """Run LangGraph workflow synchronously and return final results."""
    normalized_symbol = _normalize_symbol(stock_symbol)
    final_report = ""
    recommendation = None

    lang_instruction = _language_instruction(language)
    enriched_message = f"[股票代码: {normalized_symbol}] {user_message}{lang_instruction}"

    initial_state = {
        "stock_symbol": normalized_symbol,
        "language": language or "",
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
        "executed_agents": [],
        "guard_retry_count": 0,
        "evidence_packet": None,
    }
    config = {"configurable": {"thread_id": thread_id}}

    for chunk in langgraph_app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if update.get("final_report"):
                final_report = str(update["final_report"])
            if node_name == "recommendation_agent" and update.get("messages"):
                recommendation = _strip_json_blocks(_safe_text(update["messages"][-1]))

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


LANGUAGE_LABELS: dict[str, str] = {
    "zh": "简体中文",
    "yue": "粤语 (Cantonese)",
    "en": "English",
}


def _language_instruction(language: str | None) -> str:
    if not language or language == "en":
        return ""
    label = LANGUAGE_LABELS.get(language, language)
    return f"\n\n[语言要求] 请全程使用 {label} 回复。所有分析内容、指标解释、建议都必须用 {label} 输出。"


def stream_analysis_events(
    user_message: str,
    stock_symbol: str,
    user_id: str,
    thread_id: str,
    session_id: str,
    language: str | None = None,
) -> Generator[str, None, dict[str, Any]]:
    normalized_symbol = _normalize_symbol(stock_symbol)
    final_report = ""
    recommendation = None
    guard_check = None
    output_level = ""

    lang_instruction = _language_instruction(language)
    enriched_message = f"[股票代码: {normalized_symbol}] {user_message}{lang_instruction}"

    initial_state = {
        "stock_symbol": normalized_symbol,
        "language": language or "",
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
        "executed_agents": [],
        "guard_retry_count": 0,
        "evidence_packet": None,
    }
    config = {"configurable": {"thread_id": thread_id}}

    yield _sse("analysis_start", {
        "session_id": session_id,
        "thread_id": thread_id,
        "stock_symbol": normalized_symbol,
        "analysis_type": "analyze",
    })

    emitted_agents: set[str] = set()
    debate_sides_emitted: set[str] = set()
    agent_start_times: dict[str, float] = {}
    target_price: dict | None = None
    risk_level: dict | None = None

    import time as _time
    current_node_name: str | None = None
    try:
        for chunk in langgraph_app.stream(
            initial_state,
            config=config,
            stream_mode="updates",
            subgraphs=True,
        ):
            for node_name, update in _iter_stream_chunks(chunk):
                current_node_name = node_name
                agent_meta = AGENT_LABELS.get(node_name, {"label": node_name, "icon": "\U0001f916"})
                label = agent_meta["label"]
                icon = agent_meta["icon"]

                if node_name not in emitted_agents:
                    emitted_agents.add(node_name)
                    agent_start_times[node_name] = _time.time()
                    yield _sse("agent_start", {
                        "agent": node_name,
                        "label": label,
                        "icon": icon,
                    })

                # === evidence_packet ===
                if node_name == "evidence_packet_builder" and "evidence_packet" in update:
                    ep = update["evidence_packet"]
                    chart = update.get("chart_data", [])
                    yield _sse("evidence_packet", {
                        "symbol": ep.get("symbol", ""),
                        "facts": ep.get("facts", []),
                        "evidence_score": ep.get("evidence_score", 0),
                        "allowed_output_level": ep.get("allowed_output_level", ""),
                        "chart_data": chart,
                    })

                # 当 orchestrator 决定好下一批要运行的 agent 时，立即发出 agent_start，
                # 让前端在 agent 执行期间（可能耗时 30-120s）就显示 "运行中" 状态
                if node_name == "orchestrator":
                    next_agents = update.get("next")
                    if isinstance(next_agents, list):
                        for agent_id in next_agents:
                            if agent_id not in emitted_agents:
                                emitted_agents.add(agent_id)
                                meta = AGENT_LABELS.get(agent_id, {"label": agent_id, "icon": "\U0001f916"})
                                yield _sse("agent_start", {
                                    "agent": agent_id,
                                    "label": meta["label"],
                                    "icon": meta["icon"],
                                })
                    # 发射被跳过的 agent
                    skipped_agents = update.get("skipped_agents")
                    if isinstance(skipped_agents, list):
                        for sid in skipped_agents:
                            if sid not in emitted_agents and sid != "__end__":
                                emitted_agents.add(sid)
                                meta = AGENT_LABELS.get(sid, {"label": sid, "icon": "\U0001f916"})
                                yield _sse("agent_skipped", {
                                    "agent": sid,
                                    "label": meta["label"],
                                    "icon": meta["icon"],
                                })

                content = _extract_agent_content(node_name, update)
                is_guard = node_name in ("guard_agent", "guard")
                has_guard = isinstance(update.get("guard_check"), dict) and update["guard_check"]
                debate_subagents_emitted = False

                # debate_stage 子图在 subgraphs=False 时只上报顶层节点，此处作兜底拆包
                if node_name == "debate_stage":
                    for sub_agent, side in (
                        ("bull_researcher", "bull"),
                        ("bear_researcher", "bear"),
                    ):
                        if sub_agent in debate_sides_emitted:
                            continue
                        sub_content = _serialize_debate_side(update, side)
                        if not sub_content:
                            continue
                        debate_subagents_emitted = True
                        sub_meta = AGENT_LABELS.get(
                            sub_agent,
                            {"label": sub_agent, "icon": "\U0001f916"},
                        )
                        if sub_agent not in emitted_agents:
                            emitted_agents.add(sub_agent)
                            agent_start_times[sub_agent] = _time.time()
                            yield _sse("agent_start", {
                                "agent": sub_agent,
                                "label": sub_meta["label"],
                                "icon": sub_meta["icon"],
                            })
                        yield _sse("agent_output", {
                            "agent": sub_agent,
                            "content": sub_content,
                        })
                        debate_sides_emitted.add(sub_agent)
                        yield _sse("agent_done", {
                            "agent": sub_agent,
                            "duration_ms": round(
                                (_time.time() - agent_start_times.get(sub_agent, _time.time())) * 1000
                            ),
                        })

                if node_name == "recommendation_agent" and update.get("messages"):
                    raw_recommendation = _safe_text(update["messages"][-1])
                    rec_json = _extract_json_block(raw_recommendation)
                    valuation = _coerce_valuation_scenario(rec_json)
                    if valuation:
                        target_price = valuation
                        yield _sse("target_price", target_price)
                    recommendation = _strip_json_blocks(raw_recommendation) or raw_recommendation
                    content = recommendation

                if content and not is_guard and not (
                    node_name == "debate_stage" and debate_subagents_emitted
                ):
                    yield _sse("agent_output", {
                        "agent": node_name,
                        "content": content,
                    })
                    if node_name in ("bull_researcher", "bear_researcher"):
                        debate_sides_emitted.add(node_name)

                if update.get("final_report"):
                    final_report = str(update["final_report"])
                if node_name == "risk_expert":
                    coerced_risk = _extract_risk_level(update)
                    if coerced_risk:
                        risk_level = coerced_risk
                        yield _sse("risk_level", risk_level)
                if is_guard and has_guard:
                    guard_check = update["guard_check"]
                    output_level = update.get("output_level", "")
                    gc = guard_check
                    guard_text = (
                        f"- **Valid**: {gc.get('is_valid', 'N/A')}\n"
                        f"- **Confidence Score**: {gc.get('confidence_score', 'N/A')}/100\n"
                        f"- **Issues**: {', '.join(gc.get('issues', [])) if gc.get('issues') else 'none'}\n"
                        f"- **Reasoning**: {gc.get('final_reasoning', 'N/A')}"
                    )
                    yield _sse("agent_output", {
                        "agent": node_name,
                        "content": guard_text,
                    })

                yield _sse("agent_done", {
                    "agent": node_name,
                    "duration_ms": round((_time.time() - agent_start_times.get(node_name, _time.time())) * 1000),
                })

    except Exception as exc:
        import traceback
        print(f"[analysis_service] agent error for {current_node_name}: {exc}")
        traceback.print_exc()
        if current_node_name and current_node_name not in ("strategy_aggregator",):
            meta = AGENT_LABELS.get(current_node_name, {"label": current_node_name, "icon": "\U0001f916"})
            yield _sse("agent_error", {
                "agent": current_node_name,
                "label": meta["label"],
                "icon": meta["icon"],
                "message": str(exc)[:500],
                "duration_ms": round((_time.time() - agent_start_times.get(current_node_name, _time.time())) * 1000),
            })
        final_report = f"分析过程中发生错误: {str(exc)[:200]}"
        guard_check = {
            "is_valid": False,
            "confidence_score": 0,
            "issues": [f"Pipeline error: {str(exc)[:150]}"],
            "corrections": [],
            "final_reasoning": f"Agent {current_node_name} 执行失败",
        }

    if not final_report and recommendation:
        final_report = recommendation

    done_payload = {
        "final_report": final_report or "\u5206\u6790\u5b8c\u6210",
        "recommendation": recommendation,
        "guard_check": guard_check,
        "target_price": target_price,
        "risk_level": risk_level,
    }

    ep = guard_check.get("evidence_packet", {}) if guard_check else {}
    output_level = ep.get("allowed_output_level", "") if isinstance(ep, dict) else ""
    if output_level == "limited_analysis_partial":
        done_payload["disclaimer"] = (
            "\u672c\u5206\u6790\u56e0\u90e8\u5206\u5173\u952e\u6570\u636e\u7f3a\u5931\uff0c"
            "\u7b56\u7565\u4e0e\u98ce\u9669\u8bc4\u4f30\u4e3a\u53c2\u8003\u6027\u8d28\u3002"
        )

    yield _sse("analysis_complete", done_payload)
    return done_payload


def _sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
