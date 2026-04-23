**已完成:**
* LangGraph Docs 掌握主要
* 项目规范结构搭建()
* GraphState定义: /graph
* Market Data Agent (yfinance + RSI + MACD + 波动率)
* Supervisor + StateGraph 跑通(单 Agent 模式)
* 按照逻辑: Supervisor 进行决策, 同时agent 通过对tools调用进行执行. 不过单个agent后直接就end了(开发阶段),没有后一步传回给Supervisor.
* Market Data Agent的输出已经根据GraphState定义传回给特定的Agent Data. 保证了每个agent的输出隔离化.



**TODO:**

  **Week2:**
    * 添加 Fundamental Agent + News Agent
    * 引入 Chroma RAG
    * 支持并行执行. 



















## Project Structure



```text
alphapilot/
├── agents/
│   ├── market_agent.py          # implemented
│   ├── fundamental_agent.py     # planned (Week 2+)
│   ├── news_agent.py            # planned (Week 2+)
│   ├── strategy_agent.py        # planned (Week 3+)
│   ├── risk_agent.py            # planned (Week 3+)
│   └── supervisor.py            # planned
├── tools/
│   ├── market_tools.py          # implemented
│   ├── pdf_parser.py            # planned
│   └── news_api.py              # planned
├── graph/
│   ├── state.py                 # implemented
│   ├── workflow.py              # implemented
│   └── checkpointer.py          # planned
├── rag/                         # planned: Chroma / FAISS
├── ui/                          # planned: Streamlit app
├── prompts/
│   ├── supervisor_prompt.py     # implemented
│   └── supervisor_prompt.txt    # implemented
├── debug/
│   ├── test_agent_market.py     # implemented
│   ├── test_tool_market.py      # implemented
│   └── test_workflow.py         # implemented
├── Docs/
│   ├── architecture.md          # implemented
│   └── Week_summary.md          # implemented
├── main.py
└── requirements.txt

```



# Log

1. 模型逻辑没问题, 但是执行 `main.py`出现卡住无输出问题.
  解决方案:
  1. 首先测试API KEY是否正常: 结果: 正常
  2. 测试 `langchain_google_genai`最小调用也是正常的.
  3. 然后怀疑是 `LangGraph supervisor`调用链问题, 此时因为只写了一个agent, 所以现在单独测试`market_agent`, `python -m debug.test_agent_market`查看输出, 得到报错信息: `unsupported format string passed to Series.__format_`_


