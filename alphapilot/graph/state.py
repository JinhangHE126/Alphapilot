from typing import TypedDict, Annotated, Any
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class GraphState(TypedDict):
    """AlphaPilot 全局共享状态（所有 Agent 都能读写）"""
    
    # 基础输入
    stock_symbol: str                      # 股票代码，例如 "TSLA" 或 "0700.HK"
    
    # 各 Agent 的输出结果（便于后续 Strategy Agent 汇总）
    market_data: Annotated[str, "market_data_expert output"]
    fundamental_data: Annotated[str, "fundamental_expert output"]
    news_sentiment: Annotated[str, "news_sentiment_expert output"]
    strategy_recommendation: Annotated[str, "strategy_expert output"]
    risk_assessment: Annotated[str, "risk_expert output"]
    
    # LangGraph 内置的消息列表（Supervisor 主要依赖这个）
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 未来会用到的扩展字段（现在先定义好）
    rag_context: Annotated[str, "RAG retrieved context"] = ""
    memory_summary: Annotated[str, "Memory summary"] = ""
    final_score: Annotated[float, "Final score 0-100"] = 0.0
    final_recommendation: Annotated[str, "Final Buy/Hold/Sell"] = ""
    
    # 可选：错误记录
    errors: list[str] = []