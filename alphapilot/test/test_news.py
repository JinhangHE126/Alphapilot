from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from agents.news_agent import news_agent

load_dotenv()

if __name__ == "__main__":
    symbol = "TSLA"
    result = news_agent.invoke({
        "messages": [{
            "role": "user", 
            "content": f"Please analyze {symbol}'s latest news and market sentiment."
        }]
    })
    
    print("=== News & Sentiment Agent Test Result ===")
    print(result["messages"][-1].content)