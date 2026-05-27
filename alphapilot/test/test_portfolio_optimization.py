from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    print("🚀 开始 Portfolio Optimization Agent（投资组合优化）集成测试...\n")

    test_cases = [
        "优化我的 TSLA + NVDA + AAPL 组合，风险偏好中等",
        "给我一个风险较低、Sharpe Ratio 最高的 4 只股票组合",
        "基于当前分析结果，优化我的持仓配置，我是保守型投资者",
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

        config = {"configurable": {"thread_id": f"optimization_test_{i}"}}

        for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name == "portfolio_optimization_agent":
                    print("\n✅ Portfolio Optimization Agent 执行完成！")
                    messages = update.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                        print(content[:1200] + "..." if len(content) > 1200 else content)
                elif "next" in update:
                    print(f" → Orchestrator 决定下一步: {update.get('next')}")

    print("\n🎉 7.2 Portfolio Optimization Agent 集成测试完成！")