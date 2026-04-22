alphapilot/
├── agents/
│   ├── market_agent.py
│   ├── fundamental_agent.py
│   ├── news_agent.py
│   ├── strategy_agent.py
│   ├── risk_agent.py
│   └── supervisor.py
├── tools/                  # yfinance, pdf_parser, news_api 等
├── graph/
│   ├── state.py            # 定义 GraphState
│   ├── workflow.py         # 组装整个 Graph
│   └── checkpointer.py
├── rag/                    # Chroma / FAISS
├── ui/                     # Streamlit 主页面
├── prompts/                # 每个 Agent 的 prompt 模板
├── main.py
└── requirements.txt

# Log

1. 模型逻辑没问题, 但是执行 `main.py`出现卡住无输出问题.
  解决方案:
  1. 首先测试API KEY是否正常: 结果: 正常
  2. 测试 `langchain_google_genai`最小调用也是正常的.
  3. 然后怀疑是 `LangGraph supervisor`调用链问题, 此时因为只写了一个agent, 所以现在单独测试`market_agent`, `python -m debug.test_agent_market`查看输出, 得到报错信息: `unsupported format string passed to Series.__format_`_


