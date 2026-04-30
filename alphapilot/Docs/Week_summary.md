# Week 1 Summary

## 完成情况:

- Market Data Agent + StateGraph + Supervisor 已经完整跑通.
- Market Data Agent的输出已经根据GraphState定义传回给特定的Agent Data. 保证了每个agent的输出隔离化.
- 

## 收获:

- 熟悉 LangGraph supervisor + 自定义 StateGraph 的两种方式
- 理解了 GraphState 在Multi-Agent的重要性
- 同时把Agent 封装成Node

## 遇到的问题 & 解决:

- 首先就是LLM RateLimit问题, 尝试了很多方法, 最后选择充值..
- GraphState字段没有自动填充, 通过initiate_state传入解决.

## 测试结果:

```text
(AIAgent) yuchuan@yvchuandeMacBook-Pro alphapilot % python main.py      
=== AlphaPilot Supervisor Output ===
### Technical Analysis Report: 0700.HK

Based on the latest market data, here is the technical analysis for 0700.HK:

*   **Current Price:** 495.60 (-1.67%)
*   **RSI (14):** 54.5 (Neutral)
*   **MACD:** -4.3938 (Signal: -6.5254, Histogram: +2.1316)
*   **20-Day Volatility:** 2.16%

#### Technical Indicator Interpretation
*   **Momentum:** The RSI at 54.5 indicates a neutral momentum, suggesting that the asset is neither overbought nor oversold, reflecting a period of consolidation.
*   **Trend:** The MACD shows a bullish crossover (MACD line above the signal line) with a positive histogram, which typically suggests a potential shift toward upward momentum despite the recent price decline.
*   **Risk/Volatility:** The 20-day volatility of 2.16% indicates moderate price fluctuations, suggesting a standard level of risk associated with the asset's recent trading range.

***

**Risk Note:** Technical indicators are based on historical price and volume data and do not guarantee future performance. Market conditions can change rapidly, and indicators may provide conflicting signals during periods of high volatility.

=== GraphState Summary ===
Stock Symbol: 0700.HK
Market Data Exists: True
Number of Messages: 2
```

# Week 2 Summary

## 完成情况:

- Market
- 

## 收获:

- 熟悉 LangGraph supervisor + 自定义 StateGraph 的两种方式
- 

## 遇到的问题 & 解决:

- `yfinance` 请求 Yahoo Finance 超时/代理问题.
  - 原因: 在中国内地网络环境下访问 `Yahoo Finance` 不稳定.
  - 解决方法: 在终端给 Python 进程设置 HTTP/HTTPS 代理:

    ```bash
    unset ALL_PROXY
    unset all_proxy
    export HTTP_PROXY=http://127.0.0.1:7897
    export HTTPS_PROXY=http://127.0.0.1:7897
    export http_proxy=http://127.0.0.1:7897
    export https_proxy=http://127.0.0.1:7897
    ```
- ChromaDB embedding 接口不兼容
  - 运行```test_rag.py```时候报错: ```AttributeError: 'GoogleGenerativeAIEmbeddings' object has no attribute 'name'```
  - 原因: ```rag/vectorstore.py```里直接把LangChain的```GoogleGeneraetiveAIEmbeddings```传给了 CharmaDB:```embedding_function=self.embedding_function```, 但是ChromaDB原声 client 需要的是带 ```name()```和```_call()_```的embedding function. 
  - 解决方法:在```rag/vectorstore.py```里面加了一层适配器:
    ```python
    class ChromaGoogleEmbeddingFunction:
    def name(self) -> str:
        return "google_generative_ai_embeddings"

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.embedding_model.embed_documents(input)
    ```
- PDF URL 被当成本地路径打开
  - RAG 文档成功添加后, 报错: ```no such file: 'https://digitalassets.tesla.com/...pdf'```
  - 原因: ```parse_financial_pdf```只支持本地pdf路径: ```fits.open(pdf_path)```, 但agent传进来一个PDF URL. ```fitz.open()```是不能打开URL PDF
  - 解决方法: 在```fundamental_tool.py```里新增功能可以打开URL. 现在同时支持本地PDF和远程PDF URL.
    ```python
    def _open_pdf(pdf_path: str):
    if pdf_path.startswith(("http://", "https://")):
        response = requests.get(pdf_path, timeout=30)
        response.raise_for_status()
        return fitz.open(stream=response.content, filetype="pdf")

    return fitz.open(pdf_path)
    ```
## 测试结果:

```text
qqqqqqqqqqqqqqqqqqq
```
