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
    pdf_path = Path("data/reports/TSLA-Q4-2024-Update.pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}. "
            "Download the report and place it under alphapilot/data/reports/ first."
        )
    user_input = (
        f"Please provide a full analysis of {symbol}, including technicals, "
        "fundamentals, and the latest news and sentiment. "
        f"For fundamentals, use this PDF path: {pdf_path} "
        "and call parse_financial_pdf with the provided pdf_path and symbol."
    )

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}]
    }

    print("🚀 Starting 3-agent parallel test...")
    result = app.invoke(
        initial_state,
        config={"configurable": {"thread_id": "test_parallel_tsla"}}
    )

    print("\n=== ✅ 3-agent parallel test result ===")
    print(result["messages"][-1].content)