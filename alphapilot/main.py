from dotenv import load_dotenv
load_dotenv()

from graph.workflow import app, GraphState
from graph.workflow import extract_text_content


if __name__ == "__main__":
    symbol = "TSLA"
    user_input = f"Analyze the current investment opportunity for {symbol}, including technical analysis,RSI, MACD, volatility and investment risk."  
    # user_input = f"请分析 {symbol} 的技术面，包括 RSI、MACD、波动率和投资风险提示。"

    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}]
    }
    
    result = app.invoke(
        initial_state,
        config={"configurable": {"thread_id": "alphapilot-tsla"}}
    )


    final_text = result.get("market_data") or extract_text_content(result["messages"][-1])

    
    print("=== AlphaPilot Supervisor Output ===")
    print(final_text)
    
    print("\n=== GraphState Summary ===")
    print(f"Stock Symbol: {result.get('stock_symbol')}")
    print(f"Market Data Exists: {'market_data' in result}")
    print(f"Number of Messages: {len(result.get('messages', []))}")