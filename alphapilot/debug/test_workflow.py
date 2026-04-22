from dotenv import load_dotenv

load_dotenv()

from graph.workflow import app


def main():
    user_input = "请分析 TSLA 的当前投资机会，包括技术面。"

    result = app.invoke({
        "messages": [
            {"role": "user", "content": user_input}
        ]
    })

    print("=== workflow input ===")
    print(user_input)
    print("=== workflow raw result ===")
    print(result)

    if "messages" in result and result["messages"]:
        print("=== final message ===")
        print(result["messages"][-1].content)


if __name__ == "__main__":
    main()