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
    
    # 第一次调用
    print("=== 第 1 次调用 ===")
    result1 = app.invoke({
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": f"请分析 {symbol} 的技术面和基本面"}]
    }, config={"configurable": {"thread_id": "test_session_1"}})
    print(result1["messages"][-1].content[:500] + "...")  # 截取部分
    
    # 第二次调用（同一个 thread_id，测试 Memory 是否记住上一次）
    print("\n=== 第 2 次调用（测试 Memory） ===")
    result2 = app.invoke({
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": "刚才你分析了什么？请结合上一次分析继续给出完整建议"}]
    }, config={"configurable": {"thread_id": "test_session_1"}})
    
    print(result2["messages"][-1].content)
    print("\n✅ Memory 测试完成！如果第二次调用能提到第一次的分析内容，则 Memory 生效。")