from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    print("🚀 开始 Recommendation Agent（个性化推荐）集成测试...\n")

    test_cases = [
        "请给我 TSLA 的个性化投资建议，考虑我偏好中线持有、风险中等",
        "基于我之前的分析结果，给出 NVDA 的仓位和推荐",
        "为我制定 AAPL 的个性化投资计划，我是保守型投资者",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"{'='*70}")
        print(f"测试 {i}/3: {user_input}")
        print(f"{'='*70}")

        initial_state = {
            "stock_symbol": "TSLA",
            "messages": [{"role": "user", "content": user_input}],
        }

        config = {"configurable": {"thread_id": f"recommendation_test_{i}"}}

        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name == "recommendation_agent":
                    print("\n✅ Recommendation Agent 执行完成！")
                    messages = update.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                        print(content[:800] + "..." if len(content) > 800 else content)
                elif "next" in update:
                    print(f" → Orchestrator 决定下一步: {update.get('next')}")

    print("\n🎉 6.4 Recommendation Agent 集成测试完成！")