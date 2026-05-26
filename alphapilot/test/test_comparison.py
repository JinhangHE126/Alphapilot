from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    print("🚀 开始 Comparison Agent（多股票对比）集成测试...")

    # 测试用例：同时对比多只股票
    test_cases = [
        "对比 TSLA 和 NVDA 的投资机会",
        "TSLA vs AAPL 哪个更好？",
        "全面对比 TSLA, NVDA, AAPL",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}/3: {user_input}")
        print(f"{'='*60}")

        initial_state = {
            "stock_symbol": "TSLA",   # 默认值，实际由 comparison_agent 处理
            "messages": [{"role": "user", "content": user_input}],
        }

        config = {"configurable": {"thread_id": f"comparison_test_{i}"}}

        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name == "comparison_agent":
                    print("\n✅ Comparison Agent 执行完成！")
                    messages = update.get("messages", [])
                    if messages:
                        print(messages[-1].content if hasattr(messages[-1], "content") else messages[-1])
                elif "next" in update:
                    print(f" → Orchestrator 决定下一步: {update.get('next')}")

    print("\n🎉 6.3 多股票对比 Agent 集成测试完成！")