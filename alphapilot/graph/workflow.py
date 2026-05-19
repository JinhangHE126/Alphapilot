import json
import re

from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph

from config.llm import get_llm
from graph.state import GraphState
from graph.checkpointer import get_checkpointer

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent
from agents.portfolio_agent import portfolio_agent

load_dotenv()
checkpointer = get_checkpointer()


def orchestrator_node(state: GraphState) -> dict:
    """智能 Orchestrator - 动态路由 + Portfolio 支持"""
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
            or getattr(m, "role", None) == "user"
        ),
        "Please perform comprehensive analysis",
    )

    prompt = f"""
You are AlphaPilot Investment Research Orchestrator.
Current Stock: {stock_symbol}
User Instruction: {user_instruction}
Executed Agents: {executed or "None"}

Available Agents and Dependencies:
- market_data_expert: Technical analysis (No dependencies)
- fundamental_expert: Fundamental analysis (No dependencies)
- news_sentiment_expert: News sentiment (No dependencies)
- strategy_expert: Buy/Hold/Sell (Must wait for market + fundamental + news)
- risk_expert: Risk assessment (Must wait for strategy)
- portfolio_agent: Position sizing & portfolio suggestion (Must wait for risk_expert)

Rules:
1. Never repeat executed agents.
2. Strictly respect dependencies.
3. Call portfolio_agent at the end for full analysis or when user asks about position/holding.

Return ONLY valid JSON:
{{
  "next": ["agent1", "agent2"] or "__end__",
  "reasoning": "Short explanation"
}}
"""

    model = get_llm("orchestrator")
    response = model.invoke(prompt)
    response_text = response.content.strip()

    json_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    clean_json = json_match.group(1).strip() if json_match else response_text

    try:
        decision = json.loads(clean_json)
        next_agents = decision.get("next", "__end__")
        reasoning = decision.get("reasoning", "No reasoning")
    except Exception:
        next_agents = "__end__"
        reasoning = "JSON parsing failed"

    if isinstance(next_agents, str):
        next_agents = [next_agents] if next_agents != "__end__" else []
    next_agents = [a for a in next_agents if a not in executed]

    print("\nOrchestrator Decision:")
    print(f"   User Instruction: {user_instruction[:80]}...")
    print(f"   Executed: {executed}")
    print(f"   Next: {next_agents}")
    print(f"   Reasoning: {reasoning}\n")

    if not next_agents:
        return {"next": "__end__"}

    return {
        "next": next_agents,
        "executed_agents": executed + next_agents,
    }


# ====================== StateGraph ======================
workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("strategy_expert", strategy_agent)
workflow.add_node("risk_expert", risk_agent)
workflow.add_node("portfolio_agent", portfolio_agent)
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
]:
    workflow.add_edge(agent, "orchestrator")

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]