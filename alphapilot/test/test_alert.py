from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    print("🚀 开始 Alert Agent（实时警报与监控）集成测试...\n")

    test_cases = [
        "监控 TSLA，当价格突破 450 美元或跌破 380 美元时给我警报",
        "设置 TSLA 的 RSI 警报：RSI > 75 超买 或 RSI < 30 超卖 时通知我",
        "为我监控 NVDA 的重大新闻和 MACD 金叉/死叉信号",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"{'='*70}")
        print(f"测试 {i}/3: {user_input}")
        print(f"{'='*70}")

        initial_state = {
            "stock_symbol": "TSLA",
            "messages": [{"role": "user", "content": user_input}],
            "user_profile": {"risk_preference": "medium", "horizon": "medium"}
        }

        config = {"configurable": {"thread_id": f"alert_test_{i}"}}

        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name == "alert_agent":
                    print("\n✅ Alert Agent 执行完成！")
                    messages = update.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                        print(content[:1000] + "..." if len(content) > 1000 else content)
                elif "next" in update:
                    print(f" → Orchestrator 决定下一步: {update.get('next')}")

    print("\n🎉 7.3 Alert Agent 集成测试完成！")