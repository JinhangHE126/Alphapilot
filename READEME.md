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