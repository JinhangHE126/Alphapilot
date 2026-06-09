from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class GraphState(TypedDict, total=False):
    """AlphaPilot 全局共享状态（所有 Agent 都能读写）。"""

    # 基础输入
    stock_symbol: str
    language: str
    messages: Annotated[list[BaseMessage], add_messages]

    # Evidence Packet（v4 防幻觉核心）
    evidence_packet: Optional[dict]
    cold_start: bool
    ingestion_result: dict

    # Orchestrator / 工作流控制
    next: str
    executed_agents: list[str]
    orchestrator_reasoning: str

    # 各 Agent 输出
    market_data: str
    fundamental_data: str
    news_sentiment: str
    strategy_recommendation: str
    risk_assessment: str
    final_recommendation: str
    final_report: str
    portfolio_suggestion: str
    backtest_report: str
    backtest_metrics: dict
    comparison_report: str
    portfolio_optimization_report: str
    optimized_weights: dict
    alert_report: str
    active_alerts: list

    # 记忆 / 用户画像
    user_profile: dict
    memory: dict
    long_term_memory: dict
    conversation_history: list[dict]
    memory_summary: str

    # Guard / 质量控制
    guard_check: dict
    sources: list[str]
    confidence_score: int
    guard_retry_count: int

    # Bull vs Bear 多空辩论
    bull_argument: str
    bear_argument: str
    debate_rounds: int
    max_debate_rounds: int

    # 其他扩展
    rag_context: str
    final_score: float
    current_portfolio: dict
    errors: list[str]
