from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from agents.fundamental_agent import fundamental_agent

load_dotenv()

if __name__ == "__main__":
    symbol = "TSLA"
    pdf_path = Path("data/reports/TSLA-Q4-2024-Update.pdf")

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}. "
            "Download the report and place it under alphapilot/data/reports/ first."
        )
    
    result = fundamental_agent.invoke({
        "messages": [{
            "role": "user", 
            "content": (
                f"Please analyze the fundamental data for {symbol}. "
                f"Use this PDF file path: {pdf_path}. "
                "Call the parse_financial_pdf tool with the provided pdf_path and symbol."
            )
        }]
    })
    
    print("=== Fundamental Agent Test Result ===")
    print(result["messages"][-1].content)