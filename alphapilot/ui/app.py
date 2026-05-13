import gradio as gr
from pathlib import Path
import sys
import os
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()
os.environ["NO_PROXY"] = "127.0.0.1,localhost"


def analyze_stock(message: str, chat_history: list):
    """聊天式股票分析 - 强制使用 Gradio 4.x 兼容的 messages 格式"""
    # 自动识别股票代码
    symbol = "TSLA"
    upper_msg = message.upper()
    for code in ["AAPL", "NVDA", "GOOGL", "MSFT", "TSLA", "AMZN", "META"]:
        if code in upper_msg:
            symbol = code
            break

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": message}],
    }

    # 每次请求使用独立 thread_id，避免同一句话复用旧运行状态
    config = {"configurable": {"thread_id": f"chat_{symbol}_{uuid4().hex}"}}

    full_report = ""
    for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if node_name in ["guard", "guard_agent"] and isinstance(update, dict):
                guard_check = update.get("guard_check", {})
                if guard_check:
                    conf = guard_check.get("confidence_score", 0)
                    full_report += f"\n\n🛡️ **Guard 检查完成** | 置信度: **{conf}/100**\n"

            if "final_report" in update and update.get("final_report"):
                full_report += "\n\n" + update["final_report"]

    if not full_report.strip():
        full_report = "✅ 分析完成！完整报告已生成（请查看控制台输出）。"

    # === 关键修复：始终返回 dict 格式（Gradio 4.x 强制要求）===
    new_response = {"role": "assistant", "content": full_report.strip()}

    # 兼容旧历史记录（如果历史是 tuple 格式，自动转换）
    if chat_history and isinstance(chat_history[0], (list, tuple)):
        chat_history = [
            {"role": "user", "content": item[0]} if isinstance(item, (list, tuple)) else item
            for item in chat_history
        ]

    chat_history = chat_history + [new_response]

    return "", chat_history


# ==================== Gradio 界面 ====================
with gr.Blocks(title="AlphaPilot - AI 智能投资分析") as demo:
    gr.Markdown("# 🚀 AlphaPilot\n### 多智能体股票投资研究平台")

    chatbot = gr.Chatbot(
        label="分析对话历史",
        height=680,
        show_label=True,
        # 不要传 type 参数（你的 Gradio 版本不支持）
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
        symbol_input = gr.Textbox(label="当前股票代码", value="TSLA", scale=1)

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