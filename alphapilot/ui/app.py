import gradio as gr
from pathlib import Path
import sys
import os
import re
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

SUPPORTED_SYMBOLS = ["AAPL", "NVDA", "GOOGL", "MSFT", "TSLA", "AMZN", "META"]


def _extract_stock_symbol(message: str) -> str:
    """Extract target symbol from user message with sensible fallback."""
    upper_msg = (message or "").upper()
    for code in SUPPORTED_SYMBOLS:
        if code in upper_msg:
            return code

    # Fallback: capture token like TSLA / 0700.HK / BRK.B
    token_match = re.search(r"\b[A-Z0-9]{1,6}(?:\.[A-Z]{1,4})?\b", upper_msg)
    if token_match:
        return token_match.group(0)

    return "TSLA"


def _normalize_chat_history(chat_history: list) -> list:
    """
    Normalize Gradio history into messages format:
    [{"role": "user"|"assistant", "content": "..."}]
    """
    normalized = []
    for item in chat_history or []:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                normalized.append({"role": role, "content": content})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            user_text = str(item[0]) if item[0] is not None else ""
            assistant_text = str(item[1]) if item[1] is not None else ""
            normalized.append({"role": "user", "content": user_text})
            normalized.append({"role": "assistant", "content": assistant_text})
    return normalized


def _extract_first(patterns: list[str], text: str, default: str = "--") -> str:
    """Extract first regex group from multiple candidate patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.group(1):
            return match.group(1).strip()
    return default


def _normalize_recommendation(raw: str) -> str:
    """Normalize recommendation wording for a consistent Chinese UI."""
    value = (raw or "").strip().lower()
    if value in {"buy", "买入"}:
        return "买入"
    if value in {"hold", "持有"}:
        return "持有"
    if value in {"sell", "卖出"}:
        return "卖出"
    return "待确认"


def _infer_horizon(message: str) -> str:
    """Infer investment horizon from user query."""
    text = (message or "").lower()
    if any(k in text for k in ["短线", "短期", "day trade", "intraday", "swing"]):
        return "短线（1-10个交易日）"
    if any(k in text for k in ["长线", "长期", "long-term", "value"]):
        return "长线（6个月以上）"
    return "中线（1-3个月）"


def _guard_level(conf: int) -> str:
    if conf >= 80:
        return "高可信"
    if conf >= 60:
        return "中可信"
    return "低可信"


def _guard_status_label(conf: int) -> str:
    if conf >= 80:
        return "✅ 通过"
    if conf >= 60:
        return "⚠️ 需关注"
    return "❌ 高风险"


def _rsi_status(rsi_text: str) -> str:
    try:
        rsi = float(rsi_text)
    except Exception:
        return "--"
    if rsi >= 70:
        return "超买"
    if rsi <= 30:
        return "超卖"
    return "中性"


def _macd_status(macd_text: str) -> str:
    try:
        macd = float(macd_text)
    except Exception:
        return "--"
    return "多头" if macd >= 0 else "空头"


def _render_guard_block(guard_check: dict) -> str:
    """Render guard summary with collapsible details."""
    if not guard_check:
        return (
            "### 🛡️ Guard 质量门控\n"
            "- **状态**：⚠️ 未返回结构化结果\n"
            "- **建议**：请检查 Guard Agent 的 JSON 输出"
        )

    conf = int(guard_check.get("confidence_score", 0) or 0)
    issues = guard_check.get("issues") or []
    corrections = guard_check.get("corrections") or []
    sources = guard_check.get("sources") or []

    issues_text = "\n".join(f"- {item}" for item in issues) if issues else "- 未发现关键问题"
    corrections_text = (
        "\n".join(f"- {item}" for item in corrections) if corrections else "- 暂无修正建议"
    )
    sources_text = "\n".join(f"- {item}" for item in sources) if sources else "- 未提供来源列表"

    return (
        "### 🛡️ Guard 质量门控\n"
        f"- **状态**：{_guard_status_label(conf)}\n"
        f"- **置信度**：`{conf}/100`（{_guard_level(conf)}）\n"
        f"- **注意事项数量**：`{len(issues)}`\n\n"
        "<details>\n"
        "<summary>点击展开 Guard 详情</summary>\n\n"
        "**问题列表**\n"
        f"{issues_text}\n\n"
        "**修正建议**\n"
        f"{corrections_text}\n\n"
        "**引用来源**\n"
        f"{sources_text}\n"
        "</details>"
    )


def _render_metric_cards(
    symbol: str,
    raw_report: str,
    guard_check: dict,
    user_message: str,
) -> tuple[str, str]:
    """Render summary and concise key metrics block."""
    price = _extract_first(
        [r"(?:\$\s*|现价[:：]?\s*)(\d+(?:\.\d+)?)", r"price[:：]?\s*\$?(\d+(?:\.\d+)?)"],
        raw_report,
    )
    rsi = _extract_first([r"RSI[^0-9]*(\d+(?:\.\d+)?)"], raw_report)
    macd = _extract_first([r"MACD[^0-9\-]*(\-?\d+(?:\.\d+)?)"], raw_report)
    recommendation = _extract_first(
        [r"(Buy|Hold|Sell)", r"(买入|持有|卖出)", r"建议[:：]?\s*([^\n，。]{2,20})"],
        raw_report,
        default="待确认",
    )
    recommendation = _normalize_recommendation(recommendation)
    horizon = _infer_horizon(user_message)
    conf = str(int(guard_check.get("confidence_score", 0) or 0)) if guard_check else "--"

    summary = (
        "### ✅ 执行摘要\n"
        f"- **投资建议**：`{recommendation}`\n"
        f"- **目标周期**：`{horizon}`\n"
        f"- **置信度**：`{conf}/100`"
    )
    metrics = (
        "### 📊 关键指标卡片\n"
        f"- **标的**：`{symbol}`\n"
        f"- **现价**：`${price}`\n"
        f"- **RSI(14)**：`{rsi}`（{_rsi_status(rsi)}）\n"
        f"- **MACD**：`{macd}`（{_macd_status(macd)}）\n"
        f"- **止损位**：`--`（可在风险模块补充）"
    )
    return summary, metrics


def _render_visual_report(
    symbol: str,
    raw_report: str,
    guard_check: dict,
    user_message: str,
) -> str:
    """Build structured markdown report with clear hierarchy."""
    summary_block, metric_cards = _render_metric_cards(
        symbol=symbol,
        raw_report=raw_report,
        guard_check=guard_check,
        user_message=user_message,
    )
    guard_block = _render_guard_block(guard_check)

    body = raw_report.strip() if raw_report.strip() else "暂无可展示正文。"
    return (
        f"## 🚀 AlphaPilot 分析报告 · `{symbol}`\n\n"
        f"{summary_block}\n\n"
        f"{metric_cards}\n\n"
        f"{guard_block}\n\n"
        "### 1) 执行摘要\n"
        "- 结论与建议已在上方给出。\n\n"
        "### 2) 市场 / 基本面 / 新闻\n"
        "- 详见下方原始分析正文。\n\n"
        "### 3) 策略与仓位\n"
        "- 如正文包含仓位建议，请优先按风险承受能力执行。\n\n"
        "### 4) 风险与反例\n"
        "- 重点关注 Guard 的问题列表与修正建议。\n\n"
        "### 5) 操作建议（含触发条件）\n"
        "- 建议结合价格触发位、仓位上限与止损线执行。\n\n"
        "### 📝 详细分析正文\n"
        f"{body}"
    )


def analyze_stock(message: str, chat_history: list):
    """聊天式股票分析（带 Guard 摘要 + 历史格式兼容）"""
    if not message or not message.strip():
        return "", _normalize_chat_history(chat_history)

    history_messages = _normalize_chat_history(chat_history)
    symbol = _extract_stock_symbol(message)

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": message}],
    }

    # 每次请求使用独立 thread_id，避免同一句话复用旧运行状态
    config = {"configurable": {"thread_id": f"chat_{symbol}_{uuid4().hex}"}}

    report_parts = []
    latest_guard_check = {}
    try:
        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name in ["guard", "guard_agent"] and isinstance(update, dict):
                    guard_check = update.get("guard_check", {})
                    if guard_check:
                        latest_guard_check = guard_check

                final_report = update.get("final_report") if isinstance(update, dict) else None
                if final_report:
                    report_parts.append(final_report)
    except Exception as exc:
        report_parts.append(f"❌ 分析过程中出现异常：{exc}")

    raw_report = "\n\n".join(part.strip() for part in report_parts if str(part).strip())
    if not raw_report:
        raw_report = "✅ 分析完成！报告已生成（请查看控制台日志）。"
    full_report = _render_visual_report(
        symbol=symbol,
        raw_report=raw_report,
        guard_check=latest_guard_check,
        user_message=message,
    )

    updated_history = history_messages + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": full_report},
    ]
    return "", updated_history


# ==================== Gradio 界面 ====================
with gr.Blocks(title="AlphaPilot - AI 智能投资分析", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 AlphaPilot\n### 多智能体股票投资研究平台")

    chatbot = gr.Chatbot(
        label="分析对话历史",
        height=680,
        show_label=True,
    )

    with gr.Row():
        msg = gr.Textbox(
            label="输入分析需求",
            placeholder="例如：请全面分析 TSLA 并给出投资建议",
            scale=8
        )
        submit_btn = gr.Button("发送", variant="primary", scale=2)

    with gr.Row():
        clear_btn = gr.Button("🗑️ 清空对话")

    # 事件绑定
    submit_btn.click(
        fn=analyze_stock,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot]
    )
    msg.submit(
        fn=analyze_stock,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot]
    )

    clear_btn.click(lambda: [], None, chatbot, queue=False)


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        debug=True
    )