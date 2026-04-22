import yfinance as yf

def fetch_market_data(symbol: str) -> str:
    """获取股票最新市场数据 + 技术指标"""
    data = yf.Ticker(symbol).history(period="5d")
    if data.empty:
        return f"无法获取 {symbol} 数据"
    latest = data.iloc[-1]
    prev = data.iloc[0]
    return f"""
股票 {symbol} 最新市场数据（5日）：
收盘价: {latest['Close']:.2f}
成交量: {latest['Volume']:,.0f}
5日涨跌幅: {(latest['Close']/prev['Close']-1)*100:.2f}%
    """