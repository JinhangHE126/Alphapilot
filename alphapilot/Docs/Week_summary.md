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

- Strategy Agent（Chain-of-Thought + 权重评分）
- Risk Agent（波动/宏观风险 + 止损/仓位建议）
- Supervisor 完整 LLM 动态路由 + executed_agents 防重复
- 5 Agent 完整协作流程（Market → Fundamental → News → Strategy → Risk）
- Explainability 日志（Supervisor 决策过程可视化）
- 

## 收获:

- 真正实现了提案中的 Multi-Agent 协作架构
- 可解释性大幅提升（每个步骤都有日志）

## 遇到的问题 & 解决:

- `ConnectTimeout` 问题
  - 原因:  `Gemini` 对本地代理(7896,7901)不稳定, 新加坡地区网络+代理容易导致连接超时.
  - 解决方法: 
    - 把`market` 改为`deepseek_fast` 直连
    - 把`fundamental` 改成`deepseek_reasoner` 直连

## 测试结果:

```text
(AIAgent) ➜  alphapilot git:(dev) ✗ python test/test_end_to_end.py
🚀 [LLM] MARKET       → deepseek-chat             | proxy: 直连 | temp=0.1 | timeout=180s
🚀 [LLM] FUNDAMENTAL  → deepseek-reasoner         | proxy: 直连 | temp=0.1 | timeout=300s
🚀 [LLM] NEWS         → grok-4-1-fast-reasoning   | proxy: http://127.0.0.1:7898 | temp=0.1 | timeout=60s
🚀 [LLM] STRATEGY     → deepseek-reasoner         | proxy: http://127.0.0.1:7900 | temp=0.2 | timeout=120s
🚀 [LLM] RISK         → deepseek-reasoner         | proxy: http://127.0.0.1:7900 | temp=0.15 | timeout=120s
🚀 开始 5 Agent 完整协作测试（流式：app.stream，stream_mode=updates）...
thread_id = full_test_5agents

说明：Supervisor 若一次派发多个 agent，会并行跑。「第 N 步」= 某个节点刚结束；
长时间无新步骤时，多半在等尚未返回的并行分支。

🔍 Supervisor 决策日志:
   用户输入: 请全面分析 TSLA 的投资机会，给出 Buy/Hold/Sell 建议和风险控制措施。...
   已执行 Agent: []
   下一步执行: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']
   当前执行进度: 0/5

>>> 节点完成: supervisor
 next: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']
 executed_agents: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']

⏳ 尚未结束的节点: fundamental_expert, market_data_expert, news_sentiment_expert
📥 [Attempt 1/4] Downloading TSLA (proxy: 直连)...
1 Failed download:
['TSLA']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')
📥 [Attempt 2/4] Downloading TSLA (proxy: 直连)...
✅ 下载成功！共 60 条记录

>>> 节点完成: market_data_expert
[tool:fetch_market_data] [TSLA Technical Analysis Report]
       Current Price: 410.59 (Change: +2.97%)
       Latest Volume: 12,472,605
       RSI(14): 55.9 (Neutral)
       MACD: 5.0916 (Signal: 1.5664, Histogram: +3.5252)
       20-Day Volatility: 2.44%
       5-Day Change: +7.59%
       Summary: MACD bullish crossover, upward trend

>>> 节点完成: news_sentiment_expert
[tool:fetch_recent_news_and_sentiment]
{"symbol":"TSLA","overall_sentiment":"Positive","sentiment_score":0.85,
"key_events":["Tesla China sales spiked 36% in April, marking the sixth straight monthly gain.",
"Tesla stock passed an aggressive buy point and the 200-day line.",
"Tesla stock rose above $400, driven by strong China sales of 79,478 vehicles including exports."],
"summary":"Tesla's impressive 36% year-over-year surge in China sales has propelled the stock past key technical levels like $400 and the 200-day line, signaling strong positive momentum."}

>>> 节点完成: fundamental_expert
[tool:analyze_fundamental_request_tool]
symbol='TSLA' revenue_growth=2.0 eps_growth=3.0 gross_margin=16.3 net_margin=9.0
key_points=[
  'Q4 2024 was a record quarter for vehicle deliveries and energy storage deployments.',
  'COGS per vehicle reached its lowest level ever at <$35,000.',
  'Energy business achieved record gross profit in Q4.',
  '2025 expected to be seminal year with FSD improvements and potential unsupervised FSD launch.'
]

🔍 Supervisor 决策日志:
   已执行 Agent: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert']
   下一步执行: ['strategy_expert']
   当前执行进度: 3/5

>>> 节点完成: strategy_expert
{
  "recommendation": "Buy",
  "confidence_score": 65,
  "reasoning": "综合技术面、基本面和舆情信号后，整体为中等偏多。技术面 MACD 看涨交叉、RSI 55.9；基本面营收和 EPS 温和增长，但利润率仍受 ASP 与 AI 投入影响；舆情分数 0.85，China sales 与突破 $400 提供正向催化。"
}

🔍 Supervisor 决策日志:
   已执行 Agent: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert', 'strategy_expert']
   下一步执行: ['risk_expert']
   当前执行进度: 4/5

>>> 节点完成: risk_expert
{
  "volatility_risk": 78,
  "macro_risk": 68,
  "stop_loss_suggestion": "$380（约低于当前价格 $410.59 的 7.5%，位于 $400 突破位和 200 日均线下方）；保守方案可考虑 $395。",
  "position_suggestion": "建议仓位 8-12%；保守投资者控制在 5-8%；可采用分批建仓降低入场风险。",
  "overall_risk_score": 70
}

🔍 Supervisor 决策日志:
   已执行 Agent: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert', 'strategy_expert', 'risk_expert']
   下一步执行: []
   当前执行进度: 5/5

>>> 节点完成: supervisor
 next: '__end__'
 final_report:
# AlphaPilot 完整投资分析报告 - TSLA

## 📊 执行路径
已执行 Agent: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert', 'strategy_expert', 'risk_expert']

## 🎯 最终投资建议（Strategy Agent）
recommendation: Buy
confidence_score: 65

## ⚠️ 风险评估（Risk Agent）
volatility_risk: 78
macro_risk: 68
overall_risk_score: 70
stop_loss_suggestion: $380；保守止损可考虑 $395
position_suggestion: 8-12%，保守投资者 5-8%

🔄 读取 checkpoint 最终状态（get_state，避免二次 invoke）...

=== ✅ 5 Agent 完整测试结果（最终 state） ===
messages 共 12 条
其它字段:
 stock_symbol: TSLA
 next: __end__
 executed_agents: ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert', 'strategy_expert', 'risk_expert']

📊 执行路径： ['market_data_expert', 'fundamental_expert', 'news_sentiment_expert', 'strategy_expert', 'risk_expert']
✅ 5 Agent 完整协作测试通过！
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

```

