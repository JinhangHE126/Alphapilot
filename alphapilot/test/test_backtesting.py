from pathlib import Path
import sys
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    print("🚀 开始 Backtesting Agent 集成测试...")

    initial_state = {
        "stock_symbol": "TSLA",
        "messages": [{"role": "user", "content": "请全面分析 TSLA 并进行历史回测"}],
    }

    config = {"configurable": {"thread_id": f"backtesting_test_6.2_{uuid4().hex}"}}
    backtesting_executed = False

    for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if node_name == "backtesting_agent":
                backtesting_executed = True
                print("\n✅ Backtesting Agent 执行完成！")
                print(update.get("messages", [])[-1].content if update.get("messages") else update)
            elif "next" in update:
                print(f" → Orchestrator 决定下一步: {update.get('next')}")

    if not backtesting_executed:
        raise AssertionError("Backtesting Agent was not executed.")

    print("\n🎉 6.2 Backtesting Agent 集成测试完成！")