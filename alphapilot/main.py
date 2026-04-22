from dotenv import load_dotenv
load_dotenv()

from graph.workflow import app, GraphState



if __name__ == "__main__":
    symbol = "TSLA"
    user_input = f"Analyze the current investment opportunity for {symbol}, including technical aspects."  
    
    initial_state = {
        "stock_symbol": symbol,
        "messages": [{"role": "user", "content": user_input}]
    }
    
    result = app.invoke(initial_state)
    
    print("=== AlphaPilot Supervisor Output ===")
    print(result["messages"][-1].content)
    
    print("\n=== GraphState Summary ===")
    print(f"Stock Symbol: {result.get('stock_symbol')}")
    print(f"Market Data Exists: {'market_data' in result}")
    print(f"Number of Messages: {len(result.get('messages', []))}")