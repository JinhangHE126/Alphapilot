import json
import re
from typing import Any

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
from agents.backtesting_agent import backtesting_agent

load_dotenv()
checkpointer = get_checkpointer()

FULL_CHAIN_KEYWORDS = (
    "comprehensive analysis",
    "full analysis",
    "complete analysis",
    "全面分析",
    "完整分析",
    "历史回测",
    "回测",
    "backtest",
    "backtesting",
)

FULL_ANALYSIS_STAGES = [
    ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
    ["strategy_expert"],
    ["risk_expert"],
    ["portfolio_agent"],
    ["backtesting_agent"],
]


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def _message_role(message: Any) -> str | None:
    if isinstance(message, dict):
        return message.get("role")
    return getattr(message, "role", None)


def _is_full_analysis_request(user_instruction: str) -> bool:
    normalized_instruction = user_instruction.lower()
    return any(keyword in normalized_instruction for keyword in FULL_CHAIN_KEYWORDS)


def _next_full_analysis_agents(executed: list[str]) -> list[str]:
    """Return the next mandatory stage for full analysis/backtesting requests."""
    executed_set = set(executed)
    for stage in FULL_ANALYSIS_STAGES:
        missing_agents = [agent for agent in stage if agent not in executed_set]
        if missing_agents:
            return missing_agents
    return []


def orchestrator_node(state: GraphState) -> dict:
    """智能 Orchestrator - 对完整链路使用确定性路由，避免 LLM 提前结束。"""
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    stock_symbol = state.get("stock_symbol", "TSLA")

    user_instruction = next(
        (
            _message_content(m)
            for m in messages
            if _message_role(m) == "user"
        ),
        "Please perform comprehensive analysis",
    )

    if _is_full_analysis_request(user_instruction):
        next_agents = _next_full_analysis_agents(executed)
        reasoning = "Deterministic full-analysis route; enforce dependencies until backtesting_agent."

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

    prompt = f"""
You are AlphaPilot Investment Research Orchestrator.
Current Stock: {stock_symbol}
User Instruction: {user_instruction}
Executed Agents: {executed or "None"}

=== YOU MUST FOLLOW THIS EXACT SEQUENCE FOR "COMPREHENSIVE ANALYSIS" ===
1. FIRST: market_data_expert + fundamental_expert + news_sentiment_expert (parallel)
2. THEN: strategy_expert (ONLY after the above 3)
3. THEN: risk_expert (ONLY after strategy_expert)
4. THEN: portfolio_agent (ONLY after risk_expert)
5. FINALLY: backtesting_agent (ONLY after portfolio_agent - THIS IS THE LAST STEP)

=== STRICT RULES (DO NOT BREAK) ===
- If the user says "comprehensive analysis", "full analysis", "全面分析", "完整分析", "历史回测", "backtest" or any similar phrase → YOU MUST execute the FULL chain and end with backtesting_agent.
- NEVER stop early. NEVER skip any agent.
- NEVER repeat already executed agents.
- Default behavior for comprehensive requests is the complete sequence above.

Return ONLY valid JSON, no other text:
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
]:
    workflow.add_edge(agent, "orchestrator")

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]