import inspect
import os
import re
import sys
from html import escape
from pathlib import Path
from uuid import uuid4

import gradio as gr
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.workflow import app

load_dotenv()
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

SUPPORTED_SYMBOLS = ["AAPL", "NVDA", "GOOGL", "MSFT", "TSLA", "AMZN", "META"]
AGENT_ORDER = [
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "strategy_expert",
    "risk_expert",
    "guard_agent",
]
AGENT_META = {
    "market_data_expert": ("📈 Market", "行情/技术面"),
    "fundamental_expert": ("📊 Fundamental", "财务/估值"),
    "news_sentiment_expert": ("📰 News", "新闻/情绪"),
    "strategy_expert": ("🎯 Strategy", "建议/仓位"),
    "risk_expert": ("⚠️ Risk", "风险/反例"),
    "guard_agent": ("🛡️ Guard", "事实核验"),
}
AGENT_LABELS = {
    "orchestrator": "🧠 Orchestrator",
    "market_data_expert": AGENT_META["market_data_expert"][0],
    "fundamental_expert": AGENT_META["fundamental_expert"][0],
    "news_sentiment_expert": AGENT_META["news_sentiment_expert"][0],
    "strategy_expert": AGENT_META["strategy_expert"][0],
    "risk_expert": AGENT_META["risk_expert"][0],
    "guard": AGENT_META["guard_agent"][0],
    "guard_agent": AGENT_META["guard_agent"][0],
    "memory": "💾 Memory",
}
NODE_SUMMARY_KEY = {
    "market_data_expert": "market_data",
    "fundamental_expert": "fundamental_data",
    "news_sentiment_expert": "news_sentiment",
    "strategy_expert": "strategy_recommendation",
    "risk_expert": "risk_assessment",
}

CHATBOT_SUPPORTS_TYPE = "type" in inspect.signature(gr.Chatbot).parameters
LAUNCH_SUPPORTS_CSS = "css" in inspect.signature(gr.Blocks.launch).parameters
CHAT_MODE = "messages"

CSS = """
.gradio-container {
  background:
    radial-gradient(circle at top left, rgba(99,102,241,.18), transparent 34%),
    radial-gradient(circle at top right, rgba(34,211,238,.12), transparent 30%),
    linear-gradient(135deg, #070b16, #0b1328) !important;
}
.ap-shell { max-width: 1320px; margin: 0 auto; }
.ap-hero { padding: 22px; border-radius: 16px; background: linear-gradient(135deg, rgba(79,70,229,.34), rgba(15,23,42,.9)); border:1px solid rgba(148,163,184,.25); margin-bottom: 12px; }
.ap-hero h1 { margin: 0; font-size: 30px; }
.ap-hero p { margin: 8px 0 0; color:#cbd5e1; }
.ap-card { border:1px solid rgba(148,163,184,.25); border-radius:14px; background:rgba(15,23,42,.72); padding:12px; }
.ap-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.ap-title h3 { margin:0; font-size:15px; }
.ap-muted { color:#94a3b8; font-size:12px; }
.ap-grid { display:grid; grid-template-columns:repeat(3,minmax(120px,1fr)); gap:8px; }
.ap-agent { border:1px solid rgba(148,163,184,.24); border-radius:10px; background:rgba(30,41,59,.5); padding:8px; }
.ap-agent.done { border-color: rgba(34,197,94,.65); background: rgba(34,197,94,.12);}
.ap-agent.running { border-color: rgba(34,211,238,.65); background: rgba(34,211,238,.13);}
.ap-agent-name { font-size:12px; font-weight:700; }
.ap-agent-hint,.ap-agent-status { font-size:11px; color:#94a3b8; }
.ap-meter { height:7px; border-radius:999px; background:rgba(51,65,85,.7); overflow:hidden; margin-bottom:10px; }
.ap-meter span { display:block; height:100%; background:linear-gradient(90deg,#6366f1,#22d3ee);}
.ap-score { font-size:28px; font-weight:800; margin: 4px 0; }
.ap-green{color:#22c55e}.ap-yellow{color:#f59e0b}.ap-red{color:#ef4444}
.ap-chatbot { border:1px solid rgba(148,163,184,.23)!important; border-radius:14px!important; background:rgba(15,23,42,.72)!important; }
.ap-trace-item { border-top: 1px dashed rgba(148,163,184,.24); padding-top: 7px; margin-top: 7px; }
.ap-trace-title { font-size: 12px; font-weight: 700; color: #cbd5e1; }
.ap-trace-text { font-size: 11px; color: #94a3b8; margin-top: 3px; line-height: 1.4; }
.ap-trace-full { white-space: pre-wrap; font-size: 11px; color: #cbd5e1; background: rgba(15,23,42,.6); border-radius: 8px; padding: 8px; margin-top: 6px; }
"""


def _extract_stock_symbol(message: str) -> str:
    upper_msg = (message or "").upper()
    for code in SUPPORTED_SYMBOLS:
        if code in upper_msg:
            return code
    token_match = re.search(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,4})?\b", upper_msg)
    return token_match.group(0) if token_match else "TSLA"


def _normalize_history(history: list):
    out = []
    for item in history or []:
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}:
            out.append({"role": item["role"], "content": str(item.get("content", ""))})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"role": "user", "content": str(item[0] or "")})
            out.append({"role": "assistant", "content": str(item[1] or "")})
    return out


def _append_turn(history, user_text: str, assistant_text: str):
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": assistant_text})


def _set_last_assistant(history, assistant_text: str):
    for i in range(len(history) - 1, -1, -1):
        if isinstance(history[i], dict) and history[i].get("role") == "assistant":
            history[i] = {"role": "assistant", "content": assistant_text}
            return
    history.append({"role": "assistant", "content": assistant_text})


def _truncate(text: str, limit: int = 88) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _node_summary(node_name: str, update: dict) -> str:
    if not isinstance(update, dict):
        return ""
    if update.get("final_report"):
        return _truncate(str(update["final_report"]))
    key = NODE_SUMMARY_KEY.get(node_name)
    if key and isinstance(update.get(key), str) and update[key].strip():
        return _truncate(update[key])
    if node_name in {"guard", "guard_agent"}:
        guard = update.get("guard_check", {})
        if isinstance(guard, dict) and guard:
            return _truncate(str(guard.get("final_reasoning", "Guard 检查完成")))
    return ""


def _collect_agent_text(node_name: str, update: dict, guard_check: dict | None = None) -> str:
    """Extract a readable output snippet from each agent node update."""
    if not isinstance(update, dict):
        return ""

    # 1) Most react agents return content in `messages`
    messages = update.get("messages")
    if isinstance(messages, list) and messages:
        last_msg = messages[-1]
        content = ""
        if isinstance(last_msg, dict):
            content = str(last_msg.get("content", "")).strip()
        else:
            content = str(getattr(last_msg, "content", "")).strip()
            if not content:
                content = str(last_msg).strip()
        if content:
            # trim possible markdown fencing / tool traces noise
            content = re.sub(r"```[\s\S]*?```", "", content).strip()
            if content:
                return content

    # 2) Structured keys (if any custom state fields are returned)
    key = NODE_SUMMARY_KEY.get(node_name)
    if key and isinstance(update.get(key), str) and update[key].strip():
        return update[key].strip()

    # 3) Guard fallback
    if node_name in {"guard", "guard_agent"}:
        if guard_check and isinstance(guard_check, dict):
            conf = int(guard_check.get("confidence_score", 0) or 0)
            reason = str(guard_check.get("final_reasoning", "Guard 已完成检查"))
            return f"置信度 {conf}/100；{reason}"
    return ""


def _guard_level(conf: int):
    if conf >= 80:
        return "通过", "ap-green"
    if conf >= 60:
        return "需关注", "ap-yellow"
    return "高风险", "ap-red"


def _progress_html(current_node: str, completed: set[str], summary: str) -> str:
    current_key = "guard_agent" if current_node == "guard" else current_node
    done = len(completed.intersection(set(AGENT_ORDER)))
    pct = int((done / len(AGENT_ORDER)) * 100)
    cards = []
    for key in AGENT_ORDER:
        label, hint = AGENT_META[key]
        if key in completed:
            status, css = "已完成", "done"
        elif key == current_key:
            status, css = "执行中", "running"
        else:
            status, css = "等待中", ""
        cards.append(
            f"<div class='ap-agent {css}'><div class='ap-agent-name'>{label}</div>"
            f"<div class='ap-agent-hint'>{hint}</div><div class='ap-agent-status'>{status}</div></div>"
        )
    return (
        "<div class='ap-card'><div class='ap-title'><h3>实时分析进度</h3>"
        f"<span class='ap-muted'>{pct}%</span></div>"
        f"<div class='ap-meter'><span style='width:{pct}%'></span></div>"
        f"<div class='ap-muted'>最新摘要：{summary or '处理中...'}</div>"
        f"<div class='ap-grid'>{''.join(cards)}</div></div>"
    )


def _guard_html(guard_check: dict) -> str:
    if not guard_check:
        return "<div class='ap-card'><div class='ap-title'><h3>Guard 实时状态</h3><span class='ap-muted'>等待输出</span></div></div>"
    conf = int(guard_check.get("confidence_score", 0) or 0)
    status, cls = _guard_level(conf)
    issues = guard_check.get("issues") or []
    corrections = guard_check.get("corrections") or []
    sources = guard_check.get("sources") or []
    issues_txt = "；".join(str(i) for i in issues) if issues else "未发现关键问题"
    return (
        "<div class='ap-card'><div class='ap-title'><h3>Guard 实时状态</h3>"
        f"<span class='ap-muted'>状态：{status}</span></div>"
        f"<div class='ap-score {cls}'>{conf}/100</div>"
        f"<div class='ap-muted'>问题：{issues_txt}</div>"
        f"<div class='ap-muted'>修正建议：{len(corrections)} 条 · 引用来源：{len(sources)} 条</div></div>"
    )


def _agent_trace_html(agent_logs: dict[str, list[str]], current_node: str) -> str:
    """Render what each of the 6 agents has said so far."""
    blocks = []
    normalized_current = "guard_agent" if current_node == "guard" else current_node
    for key in AGENT_ORDER:
        label, hint = AGENT_META[key]
        status = "执行中" if key == normalized_current else ("已产出" if agent_logs.get(key) else "暂无")
        latest = agent_logs.get(key, [])
        latest_text = _truncate(latest[-1], 160) if latest else "等待该 Agent 输出..."
        if latest:
            full_text = "\n\n-----\n\n".join(latest)
            expand_block = (
                f"<details><summary>展开完整原文（{len(latest)}条）</summary>"
                f"<div class='ap-trace-full'>{escape(full_text)}</div></details>"
            )
        else:
            expand_block = "<div class='ap-trace-text'>暂无可展开内容。</div>"
        blocks.append(
            "<div class='ap-trace-item'>"
            f"<div class='ap-trace-title'>{label} · {hint} · {status}</div>"
            f"<div class='ap-trace-text'>{latest_text}</div>"
            f"{expand_block}"
            "</div>"
        )
    return (
        "<div class='ap-card'>"
        "<div class='ap-title'><h3>Agent 执行回放</h3><span class='ap-muted'>看每个 Agent 具体说了什么</span></div>"
        + "".join(blocks)
        + "</div>"
    )


def _extract_first(pattern: str, text: str, default: str = "--") -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m and m.group(1) else default


def _render_final_report(
    symbol: str,
    raw_report: str,
    guard_check: dict,
    message: str,
    agent_logs: dict[str, list[str]],
) -> str:
    price = _extract_first(r"(?:\$\s*|现价[:：]?\s*)(\d+(?:\.\d+)?)", raw_report)
    rsi = _extract_first(r"RSI[^0-9]*(\d+(?:\.\d+)?)", raw_report)
    macd = _extract_first(r"MACD[^0-9\-]*(\-?\d+(?:\.\d+)?)", raw_report)
    rec = _extract_first(r"(Buy|Hold|Sell|买入|持有|卖出)", raw_report, "待确认")
    conf = int(guard_check.get("confidence_score", 0) or 0) if guard_check else 0
    status, _ = _guard_level(conf)
    issues = guard_check.get("issues") or []
    corrections = guard_check.get("corrections") or []
    sources = guard_check.get("sources") or []
    reason = str(guard_check.get("final_reasoning", "N/A"))
    lines = [ln.strip("-* ").strip() for ln in raw_report.splitlines() if len(ln.strip()) > 12]
    key_points = "\n".join(f"- {l[:96]}" for l in lines[:3]) if lines else "- 报告已生成，展开查看详细内容。"
    agent_replay = []
    for key in AGENT_ORDER:
        label = AGENT_META[key][0]
        logs = agent_logs.get(key, [])
        if logs:
            merged = "\n\n".join(logs)
        else:
            merged = "- 本轮未捕获到结构化输出"
        agent_replay.append(
            f"<details><summary>{label}（{len(logs)}条）</summary>\n\n"
            f"```text\n{merged}\n```\n"
            "</details>"
        )
    agent_replay_md = "\n\n".join(agent_replay)
    return (
        f"## 🚀 AlphaPilot 分析报告 · `{symbol}`\n\n"
        "### ✅ 执行摘要\n"
        f"- **投资建议**：`{rec}`\n"
        f"- **目标周期**：`{'中线（1-3个月）' if '短线' not in message and '长线' not in message else ('短线（1-10个交易日）' if '短线' in message else '长线（6个月以上）')}`\n"
        f"- **置信度**：`{conf}/100`（{status}）\n\n"
        "### 🧭 关键理由（首屏）\n"
        f"{key_points}\n\n"
        "### 📊 关键指标卡片\n"
        f"- **标的**：`{symbol}`\n- **现价**：`${price}`\n- **RSI(14)**：`{rsi}`\n- **MACD**：`{macd}`\n\n"
        "### 🛡️ Guard 质量门控\n"
        f"- **状态**：{status}\n- **结论**：{reason[:140]}\n\n"
        "<details><summary>展开 Guard 详情（问题 / 修正）</summary>\n\n"
        "**问题列表**\n"
        + ("\n".join(f"- {i}" for i in issues) if issues else "- 未发现关键问题")
        + "\n\n**修正建议**\n"
        + ("\n".join(f"- {i}" for i in corrections) if corrections else "- 暂无修正建议")
        + "\n</details>\n\n"
        "<details><summary>展开详细分析正文</summary>\n\n"
        f"{raw_report.strip() if raw_report.strip() else '暂无详细正文。'}\n"
        "</details>\n\n"
        "<details><summary>展开引用来源（附录）</summary>\n\n"
        + ("\n".join(f"- {s}" for s in sources) if sources else "- 暂无来源信息")
        + "\n</details>\n\n"
        "<details><summary>展开六个 Agent 执行回放</summary>\n\n"
        f"{agent_replay_md}\n"
        "</details>"
    )


def analyze_stock(message: str, chat_history: list):
    history = _normalize_history(chat_history)
    progress_html = _progress_html("", set(), "")
    guard_html = _guard_html({})
    trace_html = _agent_trace_html({k: [] for k in AGENT_ORDER}, "")
    if not message or not message.strip():
        yield "", history, progress_html, guard_html, trace_html
        return

    symbol = _extract_stock_symbol(message)
    initial_state = {"stock_symbol": symbol, "messages": [{"role": "user", "content": message}]}
    config = {"configurable": {"thread_id": f"chat_{symbol}_{uuid4().hex}"}}

    _append_turn(history, message, "🔄 分析任务已启动...")
    yield "", history, progress_html, guard_html, trace_html

    report_parts, latest_guard, completed = [], {}, set()
    agent_logs: dict[str, list[str]] = {k: [] for k in AGENT_ORDER}
    latest_summary = ""
    current_node = ""
    try:
        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                current_node = node_name
                if isinstance(update, dict) and update.get("final_report"):
                    report_parts.append(str(update["final_report"]))
                summary = _node_summary(node_name, update if isinstance(update, dict) else {})
                if summary:
                    latest_summary = summary
                if node_name in {"guard", "guard_agent"} and isinstance(update, dict):
                    gc = update.get("guard_check", {})
                    if isinstance(gc, dict) and gc:
                        latest_guard = gc
                normalized_key = "guard_agent" if node_name == "guard" else node_name
                if normalized_key in AGENT_ORDER:
                    output_snippet = _collect_agent_text(node_name, update if isinstance(update, dict) else {}, latest_guard)
                    if output_snippet:
                        current_logs = agent_logs[normalized_key]
                        if not current_logs or current_logs[-1] != output_snippet:
                            current_logs.append(output_snippet)
                completed.add("guard_agent" if node_name == "guard" else node_name)
                _set_last_assistant(
                    history,
                    f"### 实时分析中\n- 当前节点：`{AGENT_LABELS.get(node_name, node_name)}`\n- 最新摘要：{latest_summary or '处理中...'}",
                )
                yield (
                    "",
                    history,
                    _progress_html(current_node, completed, latest_summary),
                    _guard_html(latest_guard),
                    _agent_trace_html(agent_logs, current_node),
                )
    except Exception as exc:
        _set_last_assistant(history, f"❌ 分析出错：{exc}")
        yield (
            "",
            history,
            _progress_html(current_node, completed, latest_summary),
            _guard_html(latest_guard),
            _agent_trace_html(agent_logs, current_node),
        )
        return

    raw_report = "\n\n".join(r.strip() for r in report_parts if r and r.strip())
    if not raw_report:
        raw_report = "✅ 分析完成！已执行全链路，但暂未返回结构化 final_report。"
    _set_last_assistant(history, _render_final_report(symbol, raw_report, latest_guard, message, agent_logs))
    yield (
        "",
        history,
        _progress_html("", set(AGENT_ORDER), latest_summary),
        _guard_html(latest_guard),
        _agent_trace_html(agent_logs, ""),
    )


def _reset_ui():
    return "", [], _progress_html("", set(), ""), _guard_html({}), _agent_trace_html({k: [] for k in AGENT_ORDER}, "")


with gr.Blocks(title="AlphaPilot - AI 智能投资分析") as demo:
    with gr.Column(elem_classes=["ap-shell"]):
        gr.HTML(
            """
            <div class="ap-hero">
              <h1>AlphaPilot</h1>
              <p>多智能体股票投资研究平台 · 实时流式分析仪表盘</p>
            </div>
            """
        )

        with gr.Row():
            live_progress = gr.HTML(value=_progress_html("", set(), ""))
            live_guard = gr.HTML(value=_guard_html({}))
        live_trace = gr.HTML(value=_agent_trace_html({k: [] for k in AGENT_ORDER}, ""))

        chatbot_kwargs = {"label": "主报告区域", "height": 620, "show_label": True, "elem_classes": ["ap-chatbot"]}
        if CHATBOT_SUPPORTS_TYPE:
            chatbot_kwargs["type"] = "messages"
        chatbot = gr.Chatbot(**chatbot_kwargs)

        with gr.Row():
            msg = gr.Textbox(label="输入分析需求", placeholder="例如：请全面分析 TSLA 并给出投资建议", scale=8)
            submit_btn = gr.Button("发送", variant="primary", scale=2)

        with gr.Row():
            tsla_btn = gr.Button("TSLA 综合分析", size="sm")
            nvda_btn = gr.Button("NVDA 短线机会", size="sm")
            msft_btn = gr.Button("MSFT 中线策略", size="sm")
            clear_btn = gr.Button("🗑️ 清空对话", size="sm")

    submit_btn.click(analyze_stock, [msg, chatbot], [msg, chatbot, live_progress, live_guard, live_trace])
    msg.submit(analyze_stock, [msg, chatbot], [msg, chatbot, live_progress, live_guard, live_trace])
    tsla_btn.click(lambda: "请全面分析 TSLA 并给出投资建议", None, msg, queue=False)
    nvda_btn.click(lambda: "请分析 NVDA 的短线机会、仓位与风险", None, msg, queue=False)
    msft_btn.click(lambda: "请给出 MSFT 的中线投资策略与风险提示", None, msg, queue=False)
    clear_btn.click(_reset_ui, None, [msg, chatbot, live_progress, live_guard, live_trace], queue=False)


if __name__ == "__main__":
    launch_kwargs = {"server_name": "127.0.0.1", "server_port": 7860, "share": False, "debug": True}
    if LAUNCH_SUPPORTS_CSS:
        launch_kwargs["css"] = CSS
    demo.launch(**launch_kwargs)
