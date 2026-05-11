from pathlib import Path
import sys
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from graph.workflow import app

load_dotenv()

if __name__ == "__main__":
    symbol = "TSLA"
    user_input = "Please perform comprehensive analysis of TSLA using the latest knowledge from RAG"

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}],
    }

    config = {"configurable": {"thread_id": "rag_test_6.4"}}

    print(" Starting 6.4 Hallucination Guard Test...\n")

    for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if node_name == "orchestrator":
                print(f" → Orchestrator decided next: {update.get('next')}")

            # ==================== 增强版 Guard 输出 ====================
            elif node_name in ["guard", "guard_agent"]:
                print(f"\n Guard Agent Check:")
                
                # 适配 create_react_agent 返回的不同结构
                guard_result = update
                if isinstance(update, dict):
                    # 常见情况：直接返回最终 dict
                    if "is_valid" in update:
                        guard_result = update
                    # 某些情况下返回在 messages 里
                    elif "messages" in update and len(update["messages"]) > 0:
                        last_msg = update["messages"][-1]
                        if hasattr(last_msg, "content"):
                            import json
                            try:
                                guard_result = json.loads(last_msg.content)
                            except:
                                guard_result = {}
                        else:
                            guard_result = last_msg

                print(f"    Valid: {guard_result.get('is_valid', 'N/A')}")
                print(f"    Confidence: {guard_result.get('confidence_score', 'N/A')}/100")
                print(f"     Issues: {guard_result.get('issues', [])}")
                print(f"    Corrections: {guard_result.get('corrections', [])}")
                print(f"    Sources: {guard_result.get('sources', [])}")
                print(f"    Reasoning: {guard_result.get('final_reasoning', 'N/A')}")

            # 其他 Agent 完成提示
            elif node_name in [
                "market_data_expert",
                "fundamental_expert",
                "news_sentiment_expert",
                "strategy_expert",
                "risk_expert"
            ]:
                print(f"  {node_name} completed")

    print("\n 5.11 Hallucination Guard Test Completed!")