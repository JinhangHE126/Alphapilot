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
- 三个 Agent 并行执行时候出现错误：
  - 完成多 Agent 并行调用的网络与模型路由架构：基于 `sing-box` 增加 `market-agent`、`news-agent`、`llm-agent` 三个本地 mixed inbound 端口，并结合多模型路由配置，将市场数据、新闻数据和 LLM 请求进行入口隔离与模型分工，为后续扩展更多 Agent 提供稳定基础。
  ```text
  httpx.RemoteProtocolError: Server disconnected without sending a response.
  During task with name 'generate_structured_response'
  During task with name 'fundamental_expert'
  ```

  - 原因：多 Agent 并行执行时，market/news/fundamental 会同时访问 Yahoo Finance、新闻源、PDF、LLM API。原先所有流量都挤在 SakuraCat 单一本地端口 `7897` 上，并发时容易出现连接超时或 `Server disconnected without sending a response`。
  - 解决方案：基于 `sing-box` 增加多个本地 mixed inbound 端口，用于按 Agent 类型拆分入口流量；再通过统一 selector 出口转发到 SakuraCat 的 `7897` 或直连。

    配置文件：`alphapilot/config/sing-box.agent.example.json`

    | 项目 | 状态 | 说明 |
    | --- | --- | --- |
    | `market-agent` inbound | 已完成 | `127.0.0.1:7896`，用于 Yahoo Finance、股票价格、技术指标等市场数据请求 |
    | `news-agent` inbound | 已完成 | `127.0.0.1:7898`，用于新闻、资讯、情绪数据请求 |
    | `llm-agent` inbound | 已完成 | `127.0.0.1:7899`，用于 Google Gemini、Grok、DeepSeek/OpenAI-compatible 等 LLM 请求 |
    | `agent-proxy` selector | 已完成 | 当前包含 `sakuracat-http` 和 `direct` 两个出口，默认走 `sakuracat-http` |
    | `sakuracat-http` outbound | 已完成 | 将 sing-box 流量转发到 SakuraCat 本地端口 `127.0.0.1:7897` |
    | route rules | 已完成 | 根据 inbound tag 将 `market-agent`、`news-agent`、`llm-agent` 分别路由到 `agent-proxy` |

  - 当前设计实现了本地入口隔离：代码层可以分别使用 `7896`、`7898`、`7899`，避免所有工具和 LLM 请求直接共用同一个本地入口。
  - 当前出口层仍然统一经过 `agent-proxy`，默认转发到 SakuraCat 的 `7897`。如果后续需要真正的多出口节点隔离，可以继续把 `agent-proxy` 拆成 `market-proxy`、`news-proxy`、`llm-proxy` 三个 selector，并分别绑定不同远程节点。
  - 使用多模型并行配置，不再只依赖单一 Gemini 模型。LLM 路由配置位于：`alphapilot/config/llm.py`




## 测试结果:

```text
qqqqqqqqqqqqqqqqqqq
```


# 项目亮点:

- 多 Agent 并行架构：market、news、fundamental 可以并行运行，提高整体分析效率。
- 网络流量隔离：通过 sing-box mixed inbound，把不同 agent 类型的请求拆到不同本地入口，便于调试、限流和后续扩展。
- 多模型路由：不同 agent 可以使用不同模型供应商，不再依赖单一 Gemini。
- 工程稳定性增强：缓解并行请求时单一代理端口拥塞、连接断开、API 不稳定等问题。
- 可扩展性：后续新增 risk agent、strategy agent、portfolio agent 时，可以继续分配独立模型、代理入口和出口策略。
- RAG thchology.
- 