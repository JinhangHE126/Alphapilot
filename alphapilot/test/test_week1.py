from dotenv import load_dotenv
load_dotenv()

from graph.workflow import app, GraphState
from graph.workflow import extract_text_content


if __name__ == "__main__":
    # symbol = "TSLA"   # 你也可以改成 "0700.HK" 测试港股
    # user_input = f"请详细分析 {symbol} 的技术面，包括 RSI、MACD、波动率和当前市场状态。"
    symbol = "0700.HK"
    user_input = f"Analyze the current investment opportunity for {symbol}, including technical analysis,RSI, MACD, volatility and investment risk."  


    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}]
    }
    
    result = app.invoke(
        initial_state,
        # config={"configurable": {"thread_id": "alphapilot-tsla"}}
        config={"configurable": {"thread_id": "alphapilot-0700.HK"}}
    )


    final_text = result.get("market_data") or extract_text_content(result["messages"][-1])


    print("🚀 开始测试 AlphaPilot Week 1 Graph...")
    # result = app.invoke(final_text)

    print("\n=== ✅ Week 1 完整测试结果 ===")
    print(result["messages"][-1].content)

    print("\n=== GraphState 摘要 ===")
    print(f"股票代码: {result.get('stock_symbol')}")
    print(f"Messages 数量: {len(result.get('messages', []))}")
    print("✅ 测试通过！")