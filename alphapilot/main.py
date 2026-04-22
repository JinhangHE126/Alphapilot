from dotenv import load_dotenv
load_dotenv()
from graph.workflow import app



if __name__ == "__main__":
    user_input = "请分析 TSLA 的当前投资机会，包括技术面。"
    result = app.invoke({
        "messages": [{"role": "user", "content": user_input}]
    })
    print("=== AlphaPilot 输出 ===")
    print(result["messages"][-1].content)