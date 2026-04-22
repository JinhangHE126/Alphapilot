from dotenv import load_dotenv

load_dotenv()

from agents.market_agent import market_agent


def main():
    user_input = "请给我 TSLA 最近 5 天的收盘价、成交量和涨跌幅。"

    result = market_agent.invoke({
        "messages": [
            {"role": "user", "content": user_input}
        ]
    })

    print("=== agent input ===")
    print(user_input)
    print("=== agent raw result ===")
    print(result)

    if "messages" in result and result["messages"]:
        print("=== final message ===")
        print(result["messages"][-1].content)


if __name__ == "__main__":
    main()