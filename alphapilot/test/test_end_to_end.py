from pathlib import Path
import sys
import threading
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

def _preview_message(msg, max_len: int = 500) -> str:
    if hasattr(msg, "content"):
        c = msg.content
    elif isinstance(msg, dict):
        c = msg.get("content", str(msg))
    else:
        c = str(msg)
    if isinstance(c, list):
        parts = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        c = "\n".join(parts)
    c = str(c).strip()
    if len(c) > max_len:
        return c[:max_len] + "..."
    return c

def _register_supervisor_next(track: dict, update) -> None:
    """根据 supervisor 的 next 字段记录尚未返回的并行节点。"""
    if not isinstance(update, dict):
        return
    nxt = update.get("next")
    pending = track["pending"]
    if isinstance(nxt, list):
        pending.clear()
        for x in nxt:
            if isinstance(x, str) and x != "__end__":
                pending.add(x)
    elif isinstance(nxt, str) and nxt != "__end__":
        pending.clear()
        pending.add(nxt)

def _print_node_update(node_name: str, update) -> None:
    print(f"\n>>> 节点完成: {node_name}", flush=True)
    if update is None:
        print(" (no update)", flush=True)
        return
    if not isinstance(update, dict):
        print(f" 类型: {repr(type(update).__name__)}", flush=True)
        return
    for key, val in update.items():
        if key == "messages" and isinstance(val, list):
            print(f" messages: 新增/合并 {len(val)} 条", flush=True)
            for m in val[-3:]:
                role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else None)
                name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else "")
                prefix = f" [{role or 'msg'}{(':' + name) if name else ''}] "
                print(prefix + _preview_message(m), flush=True)
        elif key == "next":
            print(f" next: {val!r}", flush=True)
        else:
            s = str(val)
            if len(s) > 400:
                s = s[:400] + "..."
            print(f" {key}: {s}", flush=True)

if __name__ == "__main__":
    symbol = "TSLA"
    user_input = f"请全面分析 {symbol} 的投资机会，给出 Buy/Hold/Sell 建议和风险控制措施。"
    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}],
    }
    config = {"configurable": {"thread_id": "full_test_5agents", "max_concurrency": 1}}

    print("🚀 开始 5 Agent 完整协作测试（流式：app.stream，stream_mode=updates）...", flush=True)
    print(f"thread_id = {config['configurable']['thread_id']}", flush=True)
    print(
        "\n说明：Supervisor 若一次派发多个 agent，会并行跑。「第 N 步」= 某个节点刚结束；"
        "长时间无新步骤时，多半在等尚未返回的并行分支（常见最慢：market_data_expert、fundamental_expert）。\n",
        flush=True,
    )

    track = {"pending": set(), "stream_chunks": 0}
    stop_heartbeat = threading.Event()

    def _heartbeat():
        while not stop_heartbeat.wait(20.0):
            pending = track["pending"]
            ts = datetime.now().strftime("%H:%M:%S")
            chunks = track["stream_chunks"]
            pre_first = chunks == 0
            hint = ""
            if pre_first:
                hint = "（尚无第 1 个流式 chunk：多为 Supervisor `model.invoke` 卡在 DeepSeek/代理，可查 LLM_PROXY 与网络）"
            if pending:
                print(
                    f"\n… [{ts}] 仍在等待并行分支返回: {', '.join(sorted(pending))} {hint}",
                    flush=True,
                )
            else:
                print(
                    f"\n… [{ts}] 仍在等待（图内部调度 / 下一轮 supervisor）… {hint}",
                    flush=True,
                )

    threading.Thread(target=_heartbeat, daemon=True).start()

    step = 0
    try:
        for chunk in app.stream(
            initial_state,
            config=config,
            stream_mode="updates"
        ):
            step += 1
            track["stream_chunks"] = step
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'=' * 60}", flush=True)
            print(f"⏱ [{ts}] 第 {step} 步", flush=True)
            if not chunk:
                print(" (空 chunk)", flush=True)
                continue
            for node_name, node_update in chunk.items():
                if node_name == "supervisor":
                    _register_supervisor_next(track, node_update)
                elif node_name in track["pending"]:
                    track["pending"].discard(node_name)
                _print_node_update(node_name, node_update)
            if track["pending"]:
                print(
                    f"\n⏳ 尚未结束的节点: {', '.join(sorted(track['pending']))}",
                    flush=True,
                )
    finally:
        stop_heartbeat.set()

    print("\n🔄 读取 checkpoint 最终状态（get_state，避免二次 invoke）...", flush=True)
    snapshot = app.get_state(config)
    result = snapshot.values if snapshot else {}

    print("\n=== ✅ 5 Agent 完整测试结果（最终 state） ===", flush=True)
    if hasattr(result, "model_dump_json"):
        print(result.model_dump_json(indent=2, ensure_ascii=False), flush=True)
    elif isinstance(result, dict):
        msgs = result.get("messages") or []
        print(f"messages 共 {len(msgs)} 条", flush=True)
        for m in msgs[-5:]:
            role = getattr(m, "type", None) or (m.get("role") if isinstance(m, dict) else "?")
            print(f" [{role}] {_preview_message(m, max_len=800)}", flush=True)
        rest = {k: v for k, v in result.items() if k != "messages"}
        print("其它字段:", flush=True)
        for k, v in rest.items():
            s = str(v)
            if len(s) > 500:
                s = s[:500] + "..."
            print(f" {k}: {s}", flush=True)
    else:
        print(result, flush=True)

    # # ====================== 5.8 Step 2 新增：最终可解释性报告 ======================
    # print("\n" + "="*80)
    # print("🎯 AlphaPilot 最终可解释性报告")
    # print("="*80)
    # print(result.get("final_report") or result["messages"][-1].content)
    # print("\n📊 执行路径：", result.get("executed_agents", []))
    # print("✅ 5 Agent 完整协作测试通过！")

        # ====================== 5.8 Step 2：精简最终输出 ======================
    print("\n" + "="*80)
    print("🎯 AlphaPilot 最终完整报告")
    print("="*80)
    print(result.get("final_report") or result["messages"][-1].content)
    print("\n📊 执行路径：", result.get("executed_agents", []))
    print("✅ 5 Agent 完整协作测试通过！")