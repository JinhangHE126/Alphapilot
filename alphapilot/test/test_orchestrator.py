from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    symbol = "TSLA"
    # 测试不同指令（可手动切换）
    user_input = "Please only update latest data for TSLA"   # ← 改成这行测试部分更新
    # user_input = "Please perform comprehensive analysis of TSLA"  # 完整分析

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}],
    }

    config = {"configurable": {"thread_id": "orchestrator_test_6.1"}}

    print("🚀 Starting Orchestrator Dynamic Routing Test...")
    for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if "next" in update:
                print(f" → Orchestrator decided next: {update.get('next')}")
            if node_name == "orchestrator":
                print(f" 🎛️ Orchestrator reasoning: {update.get('orchestrator_reasoning')}")
   
    print("\n✅ 6.1 Orchestrator Dynamic Routing Test Completed!")