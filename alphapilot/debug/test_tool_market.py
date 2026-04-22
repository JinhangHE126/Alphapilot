from tools.market_tools import fetch_market_data


def main():
    symbol = "TSLA"
    result = fetch_market_data(symbol)

    print("=== tool input ===")
    print(symbol)
    print("=== tool output ===")
    print(result)


if __name__ == "__main__":
    main()