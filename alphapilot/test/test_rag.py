from pathlib import Path
import sys
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.fundamental_agent import fundamental_agent
from rag.vectorstore import rag

load_dotenv()

if __name__ == "__main__":
    # 先添加一条模拟历史财报数据
    rag.add_document(
        text="TSLA revenue grew by 19% in 2023, EPS grew by 25%, and gross margin was 18.2%.",
        metadata={"symbol": "TSLA", "year": "2023"},
        doc_id="tsla_2023"
    )
    
    symbol = "TSLA"
    result = fundamental_agent.invoke({
        "messages": [{
            "role": "user", 
            "content": f"Please analyze {symbol}'s latest fundamentals with historical data."
        }]
    })
    
    print("=== RAG + Fundamental Agent Test Result ===")
    print(result["messages"][-1].content)