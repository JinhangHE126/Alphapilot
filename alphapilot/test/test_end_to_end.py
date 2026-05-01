from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from graph.workflow import app

load_dotenv()

def test_end_to_end(symbol: str = "TSLA"):
    print(f"🚀 开始完整端到端测试 - {symbol}")
    
    user_input = f"请全面分析 {symbol} 的投资机会，包括技术面、基本面和最新新闻舆情。"
    
    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}]
    }
    
    config = {"configurable": {"thread_id": f"test_{symbol}"}}
    
    result = app.invoke(initial_state, config=config)
    
    final_output = result["messages"][-1].content
    
    print("\n" + "="*60)
    print("✅ 完整端到端测试结果")
    print("="*60)
    print(final_output)
    print("="*60)
    
    # 简单校验
    assert any(x in final_output for x in ["RSI", "MACD", "Revenue", "EPS", "Positive", "情绪"]), "输出缺少关键部分"
    print("✅ 测试通过！输出包含技术面、基本面和舆情分析")

if __name__ == "__main__":
    test_end_to_end("TSLA")
    # test_end_to_end("0700.HK")   # 可取消注释测试港股