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

- Fundamental Agent + RAG
- News & Sentiment Agent + RAG
- 3 个 Agent 并行执行
- Memory 持久化机制（SQLite）

## 收获:

- 成功实现了 Multi-Agent 并行 + RAG 结合
- GraphState + Supervisor 路由机制已成熟
- 使用多模型并行配置，不再只依赖单一 Gemini 模型
- 完成多 Agent 并行调用的网络与模型路由架构,基于 `sing-box` 增加多个本地 mixed inbound 端口，用于按 Agent 类型拆分入口流量
- Memory 机制让系统具备“记忆”能力

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
  - 运行`test_rag.py`时候报错: `AttributeError: 'GoogleGenerativeAIEmbeddings' object has no attribute 'name'`
  - 原因: `rag/vectorstore.py`里直接把LangChain的`GoogleGeneraetiveAIEmbeddings`传给了 CharmaDB:`embedding_function=self.embedding_function`, 但是ChromaDB原声 client 需要的是带 `name()`和`_call()_`的embedding function. 
  - 解决方法:在`rag/vectorstore.py`里面加了一层适配器:
    ```python
    class ChromaGoogleEmbeddingFunction:
    def name(self) -> str:
        return "google_generative_ai_embeddings"

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.embedding_model.embed_documents(input)
    ```
- PDF URL 被当成本地路径打开
  - RAG 文档成功添加后, 报错: `no such file: 'https://digitalassets.tesla.com/...pdf'`
  - 原因: `parse_financial_pdf`只支持本地pdf路径: `fits.open(pdf_path)`, 但agent传进来一个PDF URL. `fitz.open()`是不能打开URL PDF
  - 解决方法: 在`fundamental_tool.py`里新增功能可以打开URL. 现在同时支持本地PDF和远程PDF URL.
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

    | 项目                        | 状态  | 说明                                                                           |
    | ------------------------- | --- | ---------------------------------------------------------------------------- |
    | `market-agent` inbound    | 已完成 | `127.0.0.1:7896`，用于 Yahoo Finance、股票价格、技术指标等市场数据请求                           |
    | `news-agent` inbound      | 已完成 | `127.0.0.1:7898`，用于新闻、资讯、情绪数据请求                                              |
    | `llm-agent` inbound       | 已完成 | `127.0.0.1:7899`，用于 Google Gemini、Grok、DeepSeek/OpenAI-compatible 等 LLM 请求   |
    | `agent-proxy` selector    | 已完成 | 当前包含 `sakuracat-http` 和 `direct` 两个出口，默认走 `sakuracat-http`                   |
    | `sakuracat-http` outbound | 已完成 | 将 sing-box 流量转发到 SakuraCat 本地端口 `127.0.0.1:7897`                             |
    | route rules               | 已完成 | 根据 inbound tag 将 `market-agent`、`news-agent`、`llm-agent` 分别路由到 `agent-proxy` |

  - 当前设计实现了本地入口隔离：代码层可以分别使用 `7896`、`7898`、`7899`，避免所有工具和 LLM 请求直接共用同一个本地入口。
  - 当前出口层仍然统一经过 `agent-proxy`，默认转发到 SakuraCat 的 `7897`。如果后续需要真正的多出口节点隔离，可以继续把 `agent-proxy` 拆成 `market-proxy`、`news-proxy`、`llm-proxy` 三个 selector，并分别绑定不同远程节点。
  - 使用多模型并行配置，不再只依赖单一 Gemini 模型。LLM 路由配置位于：`alphapilot/config/llm.py`

## 测试结果:

```text
(AIAgent) yuchuan@yvchuandeMacBook-Pro alphapilot % python test/test_parallel.py           
🚀 Starting 3-agent parallel test...

=== ✅ 3-agent parallel test result ===
## Market Analysis
Based on the provided technical data for TSLA:

**Current Price:** $381.63 (up 2.37%)
**RSI(14):** 65.3 (Neutral)
**MACD:** 0.0063 (Signal: -1.1309, Histogram: +1.1372)
**20-Day Volatility:** 2.77%

**Momentum:** The RSI of 65.3 is in the neutral zone, approaching overbought territory, suggesting increasing buying interest. The MACD shows a bullish crossover with a positive histogram, indicating upward momentum.

**Trend:** The MACD's bullish crossover and the summary indicating an "upward trend" suggest a positive short-term price direction. The 5-day change of +2.12% further supports this upward movement.

**Risk:** The 20-day volatility is 2.77%, which is a moderate level of price fluctuation.

**Risk Note:** Technical indicators can change rapidly and do not guarantee future performance.

## Fundamental Analysis
Here's a fundamental analysis of TSLA based on the latest financial report:

**TSLA Fundamental Analysis**

*   **Revenue Growth:** 1.0%
*   **EPS Growth:** -53.0%
*   **Gross Margin:** 17.9%
*   **Net Profit Margin:** 7.26%

**Key Highlights:**
*   Q4 was a record quarter for both vehicle deliveries and energy storage deployments.
*   Model Y is expected to be the best-selling vehicle globally for the full year 2024.
*   Significant investments were made in infrastructure for new models, AI training compute, and energy storage manufacturing capacity.
*   COGS per vehicle reached its lowest level ever in Q4 at <$35,000.
*   The Energy business achieved a record Q4 with its highest-ever gross profit generation, and Megafactory Shanghai construction was completed.
*   FSD (Supervised) continues to rapidly improve, with the Robotaxi business expected to begin launching later in 2025.
*   Full year 2024 GAAP EPS decreased by 53% and GAAP operating income decreased by 20% YoY.
*   Profitability was impacted by reduced S3XY vehicle average selling prices and increased operating expenses driven by AI and R&D projects.

**Summary:**
Tesla's 2024 saw a 1% revenue increase to $97.69 billion, but GAAP EPS declined 53% to $2.04 due to lower vehicle average selling prices and higher operating expenses, even as the company achieved record Q4 deliveries and made significant investments in AI and energy storage.

## News & Sentiment Analysis
**TSLA News and Sentiment Analysis**

- **Overall Sentiment**: Positive
- **Sentiment Score**: 0.6
- **Key Events**:
  - Tesla generated $573 million in revenue from sales to SpaceX and xAI last year.
  - Elon Musk reportedly labels most cryptocurrencies as 'scams', potentially impacting crypto-related perceptions.
  - Broader tech sector strength with Nasdaq up nearly 20% in April amid Magnificent 7 gains.
- **One-Sentence Summary**: Tesla benefits from substantial affiliate revenue and a surging tech market, tempered slightly by Elon Musk's critical comments on cryptocurrencies.
```

```python
(AIAgent) yuchuan@yvchuandeMacBook-Pro alphapilot % python test/test_end_to_end.py
🚀 开始完整端到端测试 - TSLA

============================================================
✅ 完整端到端测试结果
============================================================
## Market Analysis
TSLA 的技术分析报告如下：

*   **当前价格**: 394.38，当日上涨 3.34%。
*   **RSI(14)**: 68.1，处于中性区域，但接近超买水平，表明买盘力量较强。
*   **MACD**: MACD 柱状图为 +1.9323，MACD 线 (1.4208) 位于信号线 (-0.5115) 之上，形成看涨交叉，表明动能偏向多头，趋势向上。
*   **20 日波动率**: 2.55%，显示该股票在过去 20 个交易日内的价格波动幅度适中。

**动能、趋势与风险解读**:
RSI 接近超买区域，显示近期买盘活跃，但需留意潜在回调风险。MACD 的看涨交叉和正向柱状图强烈支持当前的上行趋势和多头动能。2.55% 的波动率表明该资产具有一定的价格波动性，但并非极端。

**风险提示**:
技术指标仅为市场分析工具，不构成投资建议。市场价格受多种因素影响，存在固有风险。

## Fundamental Analysis
Tesla (TSLA) 2024年全年基本面分析：

*   **营收增长：** 1.0%
*   **每股收益（EPS）增长：** -53.0%
*   **毛利率：** 17.9%
*   **净利率：** 7.26%

**关键亮点：**
*   第四季度在车辆交付和储能部署方面均创下历史新高。
*   Model Y 有望成为2024年全球最畅销车型。
*   公司在新车型、AI训练计算和储能制造能力方面进行了大量投资。
*   第四季度每辆车的销售成本（COGS）降至历史最低水平，低于35,000美元。
*   能源业务在第四季度实现了创纪录的毛利润，上海超级工厂建设完成。
*   FSD（监督版）持续快速改进，Robotaxi业务预计将于2025年下半年在美国部分地区推出。
*   2024年全年GAAP净利润下降53%，主要受车辆平均售价下降和运营费用增加的影响。

**一句话总结：**
特斯拉2024年全年营收增长1%，GAAP每股收益下降53%，尽管第四季度车辆和储能部署创纪录，并在AI和新车型方面进行了战略投资，但受车辆定价下降影响，盈利能力面临挑战，公司仍专注于FSD和Robotaxi业务发展。

## News & Sentiment Analysis
**Overall Sentiment:** Positive  
**Sentiment Score:** 0.8  
**Key Events:**  
- Elon Musk’s Tesla pay package valued at $158 billion for 2025 to incentivize growth  
- Tesla starts production of Semi truck  
- Tesla nets $573M in sales from SpaceX and xAI last year  
- Tesla sold $143M worth of cars to SpaceX  

**One-Sentence Summary:** Tesla news is predominantly positive, featuring a massive executive compensation package, Semi production start, and substantial inter-company sales boosting stock performance.
============================================================
✅ 测试通过！输出包含技术面、基本面和舆情分析
(AIAgent) yuchuan@yvchuandeMacBook-Pro alphapilot % 
```

# Week 3 Summary

## 完成情况:

- Risk Agent + Strategy Agent
- 5个Agent 并行执行
- 
- 
- 

## 收获:

- 完成多 Agent 并行调用的网络与模型路由架构,基于 `sing-box` 增加多个本地 mixed inbound 端口，用于按 Agent 类型拆分入口流量
- 

## 遇到的问题 & 解决:

- `ConnectTimeout` 问题
  - 原因:  `Gemini` 对本地代理(7896,7901)不稳定, 新加坡地区网络+代理容易导致连接超时.
  - 解决方法: 
    - 把`market` 改为`deepseek_fast` 直连
    - 把`fundamental` 改成`deepseek_reasoner` 直连

## 测试结果:

```text
(AIAgent) ➜ alphapilot git:(dev) ✗ python test/test_end_to_end.py
🚀 [LLM] MARKET → deepseek-chat | proxy: 直连 | temp=0.1 | timeout=180s
🚀 [LLM] FUNDAMENTAL → deepseek-reasoner | proxy: 直连 | temp=0.1 | timeout=300s
🚀 [LLM] NEWS → grok-4-1-fast-reasoning | proxy: http://127.0.0.1:7898 | temp=0.1 | timeout=60s
🚀 [LLM] STRATEGY → deepseek-reasoner | proxy: http://127.0.0.1:7900 | temp=0.2 | timeout=120s
🚀 [LLM] RISK → deepseek-reasoner | proxy: http://127.0.0.1:7900 | temp=0.15 | timeout=120s
🚀 [LLM] STRATEGY → deepseek-reasoner | proxy: http://127.0.0.1:7900 | temp=0.2 | timeout=120s
🚀 开始 5 Agent 完整协作测试（流式：app.stream，stream_mode=updates）...
thread_id = full_test_5agents
说明：Supervisor 若一次派发多个 agent，会并行跑。「第 N 步」= 某个节点刚结束；长时间无新步骤时，多半在等尚未返回的并行分支（常见最慢：market_data_expert、fundamental_expert）。
============================================================
⏱ [16:57:21] 第 1 步
>>> 节点完成: supervisor
    next: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']
⏳ 尚未结束的节点: fundamental_expert, market_data_expert, news_sentiment_expert
📥 [Attempt 1/4] Downloading TSLA (proxy: 直连)...
🚀 [LLM] FUNDAMENTAL → deepseek-reasoner | proxy: 直连 | temp=0.1 | timeout=300s
1 Failed download:
['TSLA']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')
📥 [Attempt 2/4] Downloading TSLA (proxy: 直连)...
1 Failed download:
['TSLA']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')
📥 [Attempt 3/4] Downloading TSLA (proxy: 直连)...
… [16:57:33] 仍在等待并行分支返回: fundamental_expert, market_data_expert, news_sentiment_expert
🚀 [LLM] NEWS → grok-4-1-fast-reasoning | proxy: http://127.0.0.1:7898 | temp=0.1 | timeout=60s
✅ 下载成功！共 60 条记录
… [16:57:53] 仍在等待并行分支返回: fundamental_expert, market_data_expert, news_sentiment_expert
============================================================
⏱ [16:57:58] 第 2 步
>>> 节点完成: market_data_expert
    messages: 新增/合并 4 条
      [ai:market_data_expert] 我来获取 TSLA 的市场数据进行分析。
      [tool:fetch_market_data] [TSLA Technical Analysis Report]
        Current Price: 398.73 (Change: +2.40%)
        Latest Volume: 53,304,000
        RSI(14): 55.9 (Neutral)
        MACD: 3.3546 (Signal: 0.7325, Histogram: +2.6220)
        20-Day Volatility: 2.39%
        5-Day Change: +6.96%
        Summary: MACD bullish crossover, upward trend
      [ai:market_data_expert] ## 📊 TSLA 技术面分析报告
### 一、核心数据一览
| 指标 | 数值 | 解读 |
|------|------|------|
| **当前价格** | **$398.73** | 日内涨幅 +2.40% |
| **RSI(14)** | **55.9** | 中性偏强，未进入超买区 |
| **MACD** | **3.3546** | 信号线 0.7325，柱状图 +2.6220 |
| **20日波动率** | **2.39%** | 中等偏高波动 |
| **5日涨幅** | **+6.96%** | 短期强势上攻 |
---
### 二、技术指标解读
#### 🔹 动量指标 — RSI = 55.9
- 处于 **中性区间（30–70）**，既未超买也未超卖。
- 数值略高于50，表明 **短期多头动能占优**，但尚未过热。
- 若后续RSI突破60，则确认动量进一步走强。
#### 🔹 趋势指标 — MACD
- **MACD主线（3.35）> 信号线（0.73）**，形成 **看涨金叉**。
- 柱状图 **+2.62** 且为正值，显示 **...
⏳ 尚未结束的节点: fundamental_expert, news_sentiment_expert
============================================================
⏱ [16:57:58] 第 3 步
>>> 节点完成: news_sentiment_expert
    messages: 新增/合并 4 条
      [ai:news_sentiment_expert]
      [tool:fetch_recent_news_and_sentiment] {"symbol":"TSLA","overall_sentiment":"Negative","sentiment_score":-0.4,"key_events":["Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.","Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA."],"summary":"Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative."}
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.
- Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA.
**One-Sentence Summary:** Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative.
⏳ 尚未结束的节点: fundamental_expert
============================================================
⏱ [16:58:00] 第 4 步
>>> 节点完成: fundamental_expert
    messages: 新增/合并 4 条
      [ai:fundamental_expert] 好的，我来为 TSLA 进行基本面分析。请注意，根据我的职责，我仅能对最新的财务报告进行专业的结构化基本面分析，**不提供买入/持有/卖出建议或投资建议**。
让我先解析 Tesla 的最新财务报告。
      [tool:analyze_fundamental_request_tool] symbol='TSLA' revenue_growth=2.0 eps_growth=-71.0 gross_margin=16.3 net_margin=9.0 key_points=['Q4 was a record quarter for both vehicle deliveries and energy storage deployments.', 'COGS per vehicle reached its lowest level ever at <$35,000.', 'Energy business achieved another record in Q4 with highest-ever gross profit.', 'Construction of Megafactory Shanghai completed in December, ramping in Q1 2025.', 'FSD (Supervised) continues to improve, aiming to exceed human safety levels and launch uns...
      [ai:fundamental_expert] ## 📊 Tesla (TSLA) — 基本面分析报告
> **数据来源：** 最新财报（Q4 2024）
---
### 📈 核心财务指标
| 指标 | 数值 | 同比变化 |
|------|:----:|:--------:|
| **营收增长** | **+2%** | $257亿 → 小幅增长 |
| **EPS（每股收益）增长** | **-71%** | 大幅下滑 |
| **毛利率** | **16.3%** | 承压 |
| **净利润率** | **9.0%** | 盈利空间收窄 |
---
### 🔑 关键亮点
1. ✅ **Q4 创纪录** — 车辆交付量和储能部署量均创历史新高
2. ✅ **单车成本新低** — 每辆车 COGS 降至 **<$35,000**（历史最低）
3. ✅ **储能业务爆发** — Q4 储能业务实现创纪录的毛利润
4. ✅ **上海 Megafactory** — 2024年12月建设完成，2025年Q1开始爬坡
5. 🚗 **FSD 持续迭代** — 目标2025年推出无监督 FSD 和 Robotaxi
---...
============================================================
⏱ [16:58:07] 第 5 步
>>> 节点完成: supervisor
    next: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']
⏳ 尚未结束的节点: fundamental_expert, market_data_expert, news_sentiment_expert
… [16:58:13] 仍在等待并行分支返回: fundamental_expert, market_data_expert, news_sentiment_expert
============================================================
⏱ [16:58:15] 第 6 步
>>> 节点完成: news_sentiment_expert
    messages: 新增/合并 11 条
      [tool:fetch_recent_news_and_sentiment] {"symbol":"TSLA","overall_sentiment":"Negative","sentiment_score":-0.4,"key_events":["Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.","Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA."],"summary":"Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative."}
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.
- Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA.
**One-Sentence Summary:** Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative.
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising
⏳ 尚未结束的节点: fundamental_expert, market_data_expert
============================================================
⏱ [16:58:15] 第 7 步
>>> 节点完成: market_data_expert
    messages: 新增/合并 11 条
      [tool:fetch_recent_news_and_sentiment] {"symbol":"TSLA","overall_sentiment":"Negative","sentiment_score":-0.4,"key_events":["Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.","Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA."],"summary":"Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative."}
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.
- Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA.
**One-Sentence Summary:** Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative.
      [ai:market_data_expert] ## 📰 TSLA 新闻情绪分析报告
### 一、整体情绪：🔴 偏负面
| 维度 | 结果 |
|------|------|
| **整体情绪** | **负面（Negative）** |
| **情绪评分** | **-0.4** |
| **关键事件数** | 2 条 |
---
### 二、关键事件解读
#### 事件 1：大规模召回
> **Tesla 因软件问题召回 218,868 辆美国车辆**（NHTSA 确认）
- **影响评估：** 大规模召回对品牌声誉和短期运营构成压力
- 虽然 OTA 软件修复成本相对较低，但 **监管审查力度加大** 值得关注
#### 事件 2：估值争议
> **TSLA 过去一年上涨 40%，但年初至今下跌 9%**
- 市场对当前估值是否合理存在 **明显分歧**
- 年初至今的回调表明 **获利了结压力** 和 **估值修正预期**
---
### 三、情绪面综合判断
```
负面情绪 (-0.4)
     │
     ├── 召回事件 → 短期负面冲击
     │
     └── 估值争议 → 中长期不...
⏳ 尚未结束的节点: fundamental_expert
============================================================
⏱ [16:58:26] 第 8 步
>>> 节点完成: fundamental_expert
    messages: 新增/合并 11 条
      [tool:fetch_recent_news_and_sentiment] {"symbol":"TSLA","overall_sentiment":"Negative","sentiment_score":-0.4,"key_events":["Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.","Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA."],"summary":"Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative."}
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising questions about whether its current valuation is justified.
- Tesla is recalling 218,868 U.S. vehicles due to a rare software mistake confirmed by NHTSA.
**One-Sentence Summary:** Tesla news features a major vehicle recall for a software issue alongside debates on stock valuation after a 40% one-year gain, tilting sentiment negative.
      [ai:fundamental_expert] ## 🚗 Tesla (TSLA) 综合投资分析报告
> 📅 **报告日期：** 2025年
> **分析维度：** 基本面 + 技术面 + 新闻情绪
---
## 一、📊 基本面分析（核心财报数据）
| 关键指标 | 数据 | 同比变化 |
|---------|:---:|:--------:|
| **营收** | **$257亿** | **+2%** 📈 |
| **EPS（每股收益）** | — | **-71%** 📉 大幅下滑 |
| **毛利率** | **16.3%** | 承压 |
| **净利润率** | **9.0%** | 盈利收窄 |
### ✅ 基本面亮点
1. **Q4交付量 & 储能部署双创历史纪录**
2. **单车成本（COGS）降至历史新低** < $35,000
3. **储能业务毛利润创历史新高**
4. **上海Megafactory已完工**，2025 Q1爬坡
5. **FSD持续推进**，目标2025年推出**无监督FSD + Robotaxi**
### ⚠️ 基本面风险
- **净利润同比暴跌71%**，盈利能力...
… [16:58:33] 仍在等待（图内部调度 / 下一轮 supervisor）…
============================================================
⏱ [16:58:34] 第 9 步
>>> 节点完成: supervisor
    next: ['market_data_expert', 'fundamental_expert']
⏳ 尚未结束的节点: fundamental_expert, market_data_expert
… [16:58:53] 仍在等待并行分支返回: fundamental_expert, market_data_expert
============================================================
⏱ [16:58:57] 第 10 步
>>> 节点完成: market_data_expert
    messages: 新增/合并 14 条
      [ai:market_data_expert] ## 📰 TSLA 新闻情绪分析报告
### 一、整体情绪：🔴 偏负面
| 维度 | 结果 |
|------|------|
| **整体情绪** | **负面（Negative）** |
| **情绪评分** | **-0.4** |
| **关键事件数** | 2 条 |
---
### 二、关键事件解读
#### 事件 1：大规模召回
> **Tesla 因软件问题召回 218,868 辆美国车辆**（NHTSA 确认）
- **影响评估：** 大规模召回对品牌声誉和短期运营构成压力
- 虽然 OTA 软件修复成本相对较低，但 **监管审查力度加大** 值得关注
#### 事件 2：估值争议
> **TSLA 过去一年上涨 40%，但年初至今下跌 9%**
- 市场对当前估值是否合理存在 **明显分歧**
- 年初至今的回调表明 **获利了结压力** 和 **估值修正预期**
---
### 三、情绪面综合判断
```
负面情绪 (-0.4)
     │
     ├── 召回事件 → 短期负面冲击
     │
     └── 估值争议 → 中长期不...
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising
      [ai:market_data_expert] ## 📊 TSLA 技术面分析报告
### 一、核心数据一览
| 指标 | 数值 | 解读 |
|------|:----:|:----:|
| **当前价格** | **$398.73** | 日内涨幅 **+2.40%** |
| **RSI(14)** | **55.9** | 🟢 **中性偏强**，未进入超买区 |
| **MACD** | **3.3546** | 信号线 0.7325 |
| **MACD柱状图** | **+2.6220** | 🔵 正值，多头动能加速 |
| **20日波动率** | **2.39%** | 🟡 中等偏高 |
| **5日涨幅** | **+6.96%** | 🔵 短期强势上攻 |
---
### 二、技术指标详细解读
#### 🔹 动量指标 — RSI = 55.9
- 处于 **中性区间（30–70）**，既未超买（>70）也未超卖（<30）
- 数值略高于50中轴线，表明 **短期多头动能占优**
- 若后续RSI突破60，则确认动量进一步走强；若跌破50，则转弱
#### 🔹 趋势指标 — MACD
| 项目 | 数值...
⏳ 尚未结束的节点: fundamental_expert
============================================================
⏱ [16:58:57] 第 11 步
>>> 节点完成: fundamental_expert
    messages: 新增/合并 14 条
      [ai:market_data_expert] ## 📰 TSLA 新闻情绪分析报告
### 一、整体情绪：🔴 偏负面
| 维度 | 结果 |
|------|------|
| **整体情绪** | **负面（Negative）** |
| **情绪评分** | **-0.4** |
| **关键事件数** | 2 条 |
---
### 二、关键事件解读
#### 事件 1：大规模召回
> **Tesla 因软件问题召回 218,868 辆美国车辆**（NHTSA 确认）
- **影响评估：** 大规模召回对品牌声誉和短期运营构成压力
- 虽然 OTA 软件修复成本相对较低，但 **监管审查力度加大** 值得关注
#### 事件 2：估值争议
> **TSLA 过去一年上涨 40%，但年初至今下跌 9%**
- 市场对当前估值是否合理存在 **明显分歧**
- 年初至今的回调表明 **获利了结压力** 和 **估值修正预期**
---
### 三、情绪面综合判断
```
负面情绪 (-0.4)
     │
     ├── 召回事件 → 短期负面冲击
     │
     └── 估值争议 → 中长期不...
      [ai:news_sentiment_expert] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising
      [ai:fundamental_expert] ---
## 📋 TSLA 综合投资分析报告 — 完整版
> **报告日期：** 2025年
> **分析覆盖：** ✅ 基本面 ✅ 技术面 ✅ 新闻情绪
> **免责声明：** ⚠️ *以下为客观数据呈现，不构成投资建议*
---
## 一、📊 基本面分析
### 核心财务指标
| 指标 | 最新数据 | 同比变化 | 趋势 |
|:----|:--------:|:--------:|:----:|
| **营收** | **$257亿** | **+2%** | 🟢 小幅增长 |
| **GAAP净利润** | **$23亿** | **-71%** | 🔴 大幅恶化 |
| **毛利率** | **16.3%** | 下降 | 🟡 承压 |
| **净利润率** | **9.0%** | 收窄 | 🟡 盈利空间缩小 |
| **单车成本** | **< $35,000** | 历史新低 | 🟢 成本优化 |
### 🔑 基本面五大要点
| # | 要点 | 方向 |
|:-|:----|:----:|
| 1️⃣ | **Q4交付量创历史纪录** | ✅...
… [16:59:13] 仍在等待（图内部调度 / 下一轮 supervisor）…
============================================================
⏱ [16:59:14] 第 12 步
>>> 节点完成: supervisor
    next: ['strategy_expert', 'risk_expert']
⏳ 尚未结束的节点: risk_expert, strategy_expert
… [16:59:33] 仍在等待并行分支返回: risk_expert, strategy_expert
============================================================
⏱ [16:59:35] 第 13 步
>>> 节点完成: risk_expert
    messages: 新增/合并 16 条
      [ai:fundamental_expert] ---
## 📋 TSLA 综合投资分析报告 — 完整版
> **报告日期：** 2025年
> **分析覆盖：** ✅ 基本面 ✅ 技术面 ✅ 新闻情绪
> **免责声明：** ⚠️ *以下为客观数据呈现，不构成投资建议*
---
## 一、📊 基本面分析
### 核心财务指标
| 指标 | 最新数据 | 同比变化 | 趋势 |
|:----|:--------:|:--------:|:----:|
| **营收** | **$257亿** | **+2%** | 🟢 小幅增长 |
| **GAAP净利润** | **$23亿** | **-71%** | 🔴 大幅恶化 |
| **毛利率** | **16.3%** | 下降 | 🟡 承压 |
| **净利润率** | **9.0%** | 收窄 | 🟡 盈利空间缩小 |
| **单车成本** | **< $35,000** | 历史新低 | 🟢 成本优化 |
### 🔑 基本面五大要点
| # | 要点 | 方向 |
|:-|:----|:----:|
| 1️⃣ | **Q4交付量创历史纪录** | ✅...
      [ai:market_data_expert] ## 📊 TSLA 技术面分析报告
### 一、核心数据一览
| 指标 | 数值 | 解读 |
|------|:----:|:----:|
| **当前价格** | **$398.73** | 日内涨幅 **+2.40%** |
| **RSI(14)** | **55.9** | 🟢 **中性偏强**，未进入超买区 |
| **MACD** | **3.3546** | 信号线 0.7325 |
| **MACD柱状图** | **+2.6220** | 🔵 正值，多头动能加速 |
| **20日波动率** | **2.39%** | 🟡 中等偏高 |
| **5日涨幅** | **+6.96%** | 🔵 短期强势上攻 |
---
### 二、技术指标详细解读
#### 🔹 动量指标 — RSI = 55.9
- 处于 **中性区间（30–70）**，既未超买（>70）也未超卖（<30）
- 数值略高于50中轴线，表明 **短期多头动能占优**
- 若后续RSI突破60，则确认动量进一步走强；若跌破50，则转弱
#### 🔹 趋势指标 — MACD
| 项目 | 数值...
      [ai:risk_expert] ```json
{
  "volatility_risk": "MODERATE-HIGH — 20-day volatility at 2.39% is elevated, and the stock has surged 6.96% in 5 days, increasing short-term reversal risk. RSI at 55.9 provides some buffer from overbought conditions but does not eliminate sharp drawdown potential.",
  "macro_risk": "MODERATE — Net profit plunged 71% YoY, gross margin compressed to 16.3%, and revenue growth slowed to just 2%, signaling fundamental deterioration. Negative sentiment (-0.4) from a 218k-vehicle recall and ...
⏳ 尚未结束的节点: strategy_expert
============================================================
⏱ [16:59:35] 第 14 步
>>> 节点完成: strategy_expert
    messages: 新增/合并 16 条
      [ai:fundamental_expert] ---
## 📋 TSLA 综合投资分析报告 — 完整版
> **报告日期：** 2025年
> **分析覆盖：** ✅ 基本面 ✅ 技术面 ✅ 新闻情绪
> **免责声明：** ⚠️ *以下为客观数据呈现，不构成投资建议*
---
## 一、📊 基本面分析
### 核心财务指标
| 指标 | 最新数据 | 同比变化 | 趋势 |
|:----|:--------:|:--------:|:----:|
| **营收** | **$257亿** | **+2%** | 🟢 小幅增长 |
| **GAAP净利润** | **$23亿** | **-71%** | 🔴 大幅恶化 |
| **毛利率** | **16.3%** | 下降 | 🟡 承压 |
| **净利润率** | **9.0%** | 收窄 | 🟡 盈利空间缩小 |
| **单车成本** | **< $35,000** | 历史新低 | 🟢 成本优化 |
### 🔑 基本面五大要点
| # | 要点 | 方向 |
|:-|:----|:----:|
| 1️⃣ | **Q4交付量创历史纪录** | ✅...
      [ai:market_data_expert] ## 📊 TSLA 技术面分析报告
### 一、核心数据一览
| 指标 | 数值 | 解读 |
|------|:----:|:----:|
| **当前价格** | **$398.73** | 日内涨幅 **+2.40%** |
| **RSI(14)** | **55.9** | 🟢 **中性偏强**，未进入超买区 |
| **MACD** | **3.3546** | 信号线 0.7325 |
| **MACD柱状图** | **+2.6220** | 🔵 正值，多头动能加速 |
| **20日波动率** | **2.39%** | 🟡 中等偏高 |
| **5日涨幅** | **+6.96%** | 🔵 短期强势上攻 |
---
### 二、技术指标详细解读
#### 🔹 动量指标 — RSI = 55.9
- 处于 **中性区间（30–70）**，既未超买（>70）也未超卖（<30）
- 数值略高于50中轴线，表明 **短期多头动能占优**
- 若后续RSI突破60，则确认动量进一步走强；若跌破50，则转弱
#### 🔹 趋势指标 — MACD
| 项目 | 数值...
      [ai:strategy_expert] {
  "recommendation": "Hold",
  "confidence_score": 65,
  "reasoning": "Chain-of-Thought Analysis: 1) Technical (30% weight) is Bullish: MACD bullish crossover confirmed at 3.35 vs signal 0.73, histogram at +2.62 showing accelerating momentum, RSI at 55.9 neutral with room to run higher, price at $398.73 up 6.96% in 5 days. Clear uptrend in place. 2) Fundamental (40% weight) is Bearish: Revenue growth slowed to just +2% YoY, GAAP net income collapsed 71% to $2.3B, gross margin compressed to 16.3...
============================================================
⏱ [16:59:41] 第 15 步
>>> 节点完成: supervisor
    next: '__end__'
🔄 读取 checkpoint 最终状态（get_state，避免二次 invoke）...
=== ✅ 5 Agent 完整测试结果（最终 state） ===
messages 共 17 条
  [ai] **Overall Sentiment:** Negative
**Sentiment Score:** -0.4
**Key Events:**
- Tesla stock has surged 40% over the past year but is down 9% YTD, raising
  [ai] ---
## 📋 TSLA 综合投资分析报告 — 完整版
> **报告日期：** 2025年
> **分析覆盖：** ✅ 基本面 ✅ 技术面 ✅ 新闻情绪
> **免责声明：** ⚠️ *以下为客观数据呈现，不构成投资建议*
---
## 一、📊 基本面分析
### 核心财务指标
| 指标 | 最新数据 | 同比变化 | 趋势 |
|:----|:--------:|:--------:|:----:|
| **营收** | **$257亿** | **+2%** | 🟢 小幅增长 |
| **GAAP净利润** | **$23亿** | **-71%** | 🔴 大幅恶化 |
| **毛利率** | **16.3%** | 下降 | 🟡 承压 |
| **净利润率** | **9.0%** | 收窄 | 🟡 盈利空间缩小 |
| **单车成本** | **< $35,000** | 历史新低 | 🟢 成本优化 |
### 🔑 基本面五大要点
| # | 要点 | 方向 |
|:-|:----|:----:|
| 1️⃣ | **Q4交付量创历史纪录** | ✅ 利好 |
| 2️⃣ | **储能部署量创历史新高，储能毛利率创纪录** | ✅ 利好 |
| 3️⃣ | **上海Megafactory完工，2025 Q1爬坡** | ✅ 中期利好 |
| 4️⃣ | **FSD目标2025年推出无监督版+Robotaxi** | ✅ 长期叙事 |
| 5️⃣ | **营收增速仅2%，净利润暴跌71%** | ❌ 严重利空 |
---
## 二、📈 技术面分析
### 当前行情数据
| 指标 | 数值 | 信号 |
|:----|:----:|:----:|
| **当前价格** | **$398.73** | 日内 +2.40% |
| **R...
  [ai] ## 📊 TSLA 技术面分析报告
### 一、核心数据一览
| 指标 | 数值 | 解读 |
|------|:----:|:----:|
| **当前价格** | **$398.73** | 日内涨幅 **+2.40%** |
| **RSI(14)** | **55.9** | 🟢 **中性偏强**，未进入超买区 |
| **MACD** | **3.3546** | 信号线 0.7325 |
| **MACD柱状图** | **+2.6220** | 🔵 正值，多头动能加速 |
| **20日波动率** | **2.39%** | 🟡 中等偏高 |
| **5日涨幅** | **+6.96%** | 🔵 短期强势上攻 |
---
### 二、技术指标详细解读
#### 🔹 动量指标 — RSI = 55.9
- 处于 **中性区间（30–70）**，既未超买（>70）也未超卖（<30）
- 数值略高于50中轴线，表明 **短期多头动能占优**
- 若后续RSI突破60，则确认动量进一步走强；若跌破50，则转弱
#### 🔹 趋势指标 — MACD
| 项目 | 数值 | 信号 |
|:----|:----:|:----:|
| MACD主线 | 3.3546 | — |
| 信号线 | 0.7325 | — |
| 柱状图 | **+2.6220** | ✅ **正值放大** |
| 交叉状态 | MACD > 信号线 | 🔵 **看涨金叉确认** |
> **MACD金叉 + 正柱放大** → 当前最明确的 **看涨趋势信号**，多头动能正在加速释放。
#### 🔹 风险指标 — 波动率 2.39%
- 20日波动率处于 **中等偏高水平**，意味着价格日内波动幅度较大
- 近5日涨幅接近7%，短期波动风险正在累积
---
### 三、综合技术...
  [ai] ```json
{
  "volatility_risk": "MODERATE-HIGH — 20-day volatility at 2.39% is elevated, and the stock has surged 6.96% in 5 days, increasing short-term reversal risk. RSI at 55.9 provides some buffer from overbought conditions but does not eliminate sharp drawdown potential.",
  "macro_risk": "MODERATE — Net profit plunged 71% YoY, gross margin compressed to 16.3%, and revenue growth slowed to just 2%, signaling fundamental deterioration. Negative sentiment (-0.4) from a 218k-vehicle recall and valuation debates adds macro headwinds. EV industry pricing pressure and macroeconomic uncertainty further weigh on the stock.",
  "stop_loss_suggestion": "Consider a stop loss near $370, approximately 7.2% below the current price of $398.73. This level provides sufficient buffer against the 2.39% d...
  [ai] {
  "recommendation": "Hold",
  "confidence_score": 65,
  "reasoning": "Chain-of-Thought Analysis: 1) Technical (30% weight) is Bullish: MACD bullish crossover confirmed at 3.35 vs signal 0.73, histogram at +2.62 showing accelerating momentum, RSI at 55.9 neutral with room to run higher, price at $398.73 up 6.96% in 5 days. Clear uptrend in place. 2) Fundamental (40% weight) is Bearish: Revenue growth slowed to just +2% YoY, GAAP net income collapsed 71% to $2.3B, gross margin compressed to 16.3%, net margin at 9.0%. Positives include record deliveries/energy storage, lowest-ever COGS at <$35K, and FSD/Robotaxi narrative for 2025 but these are offset by severe profit deterioration. 3) Sentiment (30% weight) is Bearish: Overall score -0.4 (Negative), driven by 218,868 vehicle recall due to ...
其它字段:
  stock_symbol: TSLA
  next: __end__
(AIAgent) ➜ alphapilot git:(dev) ✗
```



```

# 项目亮点:

- 多 Agent 并行架构：market、news、fundamental 可以并行运行，提高整体分析效率。
- 网络流量隔离：通过 sing-box mixed inbound，把不同 agent 类型的请求拆到不同本地入口，便于调试、限流和后续扩展。
- 多模型路由：不同 agent 可以使用不同模型供应商，不再依赖单一 Gemini。
- 工程稳定性增强：缓解并行请求时单一代理端口拥塞、连接断开、API 不稳定等问题。
- 可扩展性：后续新增 risk agent、strategy agent、portfolio agent 时，可以继续分配独立模型、代理入口和出口策略。
- RAG thchology.
- 

```

