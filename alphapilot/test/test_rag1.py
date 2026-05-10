from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from graph.workflow import app

for _env in (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"):
    if _env.exists():
        load_dotenv(_env)

if __name__ == "__main__":
    symbol = "TSLA"
    user_input = (
        "Please perform comprehensive analysis of TSLA using the latest knowledge from RAG"
    )

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}],
    }

    config = {"configurable": {"thread_id": "rag_test_6.3"}}

    print(
        "🚀 Starting RAG Knowledge Enhancement Test (with real documents)...\n",
        flush=True,
    )

    for chunk in app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if node_name == "orchestrator":
                print(f" → Orchestrator decided next: {update.get('next')}")
            elif node_name in [
                "market_data_expert",
                "fundamental_expert",
                "news_sentiment_expert",
            ]:
                print(f"   ✅ {node_name} completed (RAG tool available)")

    print("\n✅ 6.3 RAG Knowledge Enhancement Test Completed!")
