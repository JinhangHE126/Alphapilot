from typing import Any

from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage

from graph.state import GraphState
from graph.checkpointer import get_checkpointer

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent
from agents.portfolio_agent import portfolio_agent
from agents.backtesting_agent import backtesting_agent
from agents.comparison_agent import comparison_agent

load_dotenv()
checkpointer = get_checkpointer()

def orchestrator_node(state: GraphState) -> dict:
    """智能 Orchestrator - 支持多股票对比"""
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    stock_symbol = state.get("stock_symbol", "TSLA")

    user_instruction = next(
        (
            m.get("content", "")
            if isinstance(m, dict)
            else getattr(m, "content", "")
            for m in messages
            if (isinstance(m, dict) and m.get("role") == "user")
            or isinstance(m, HumanMessage)
        ),
        "Please perform comprehensive analysis",
    )

    lower_instruction = user_instruction.lower()
    is_comparison = any(
        keyword in lower_instruction
        for keyword in ["对比", "compare", "vs", "versus", "comparison", "多股票", "多个股票", "which is better", "哪个更好"]
    )

    if is_comparison:
        if "comparison_agent" in executed:
            next_agents = []
            reasoning = "Comparison agent completed. Ending workflow."
        else:
            next_agents = ["comparison_agent"]
            reasoning = "User requested multi-stock comparison → directly route to comparison_agent"
    else:
        FULL_STAGES = [
            ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
            ["strategy_expert"],
            ["risk_expert"],
            ["portfolio_agent"],
            ["backtesting_agent"],
        ]
        executed_set = set(executed)
        next_agents = []
        for stage in FULL_STAGES:
            missing = [agent for agent in stage if agent not in executed_set]
            if missing:
                next_agents = missing
                break
        reasoning = "Deterministic full-analysis route."

    print("\n🎛️ Orchestrator Decision:")
    print(f"   User Instruction: {user_instruction[:80]}...")
    print(f"   Executed: {executed}")
    print(f"   Next: {next_agents}")
    print(f"   Reasoning: {reasoning}\n")

    if not next_agents:
        return {"next": "__end__", "orchestrator_reasoning": reasoning}

    return {
        "next": next_agents,
        "executed_agents": executed + next_agents,
        "orchestrator_reasoning": reasoning,
    }
# ====================== StateGraph ======================
workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("strategy_expert", strategy_agent)
workflow.add_node("risk_expert", risk_agent)
workflow.add_node("portfolio_agent", portfolio_agent)
workflow.add_node("backtesting_agent", backtesting_agent)
workflow.add_node("comparison_agent", comparison_agent)
workflow.add_node("orchestrator", orchestrator_node)

workflow.add_edge(START, "orchestrator")

workflow.add_conditional_edges(
    "orchestrator",
    lambda state: state.get("next", "__end__"),
    {
        "market_data_expert": "market_data_expert",
        "fundamental_expert": "fundamental_expert",
        "news_sentiment_expert": "news_sentiment_expert",
        "strategy_expert": "strategy_expert",
        "risk_expert": "risk_expert",
        "portfolio_agent": "portfolio_agent",
        "backtesting_agent": "backtesting_agent",
        "comparison_agent": "comparison_agent",
        "__end__": END,
    },
)

for agent in [
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "strategy_expert",
    "risk_expert",
    "portfolio_agent",
    "backtesting_agent",
    "comparison_agent",
]:
    workflow.add_edge(agent, "orchestrator")

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]