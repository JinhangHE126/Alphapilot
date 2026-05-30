from typing import Any

from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage

from graph.state import GraphState
from graph.checkpointer import get_checkpointer
from graph.user_profile import load_user_profile

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent
from agents.portfolio_agent import portfolio_agent
from agents.backtesting_agent import backtesting_agent
from agents.comparison_agent import comparison_agent
from agents.recommendation_agent import recommendation_agent
from agents.portfolio_optimization_agent import portfolio_optimization_agent
from agents.alert_agent import alert_agent
from agents.guard_agent import guard_agent

load_dotenv()
checkpointer = get_checkpointer()

GUARD_MAX_RETRIES = 2

def orchestrator_node(state: GraphState) -> dict:
    """智能 Orchestrator - 支持实时警报模式"""
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

    is_alert = any(
        keyword in lower_instruction
        for keyword in [
            "警报", "alert", "监控", "monitor", "通知", "提醒",
            "价格突破", "价格跌破", "rsi", "macd", "触发"
        ]
    )

    is_optimization = any(
        keyword in lower_instruction
        for keyword in [
            "优化", "optimization", "组合优化", "资产配置",
            "权重", "portfolio optimization", "sharpe ratio"
        ]
    )

    is_comprehensive = any(
        keyword in lower_instruction
        for keyword in [
            "全面", "完整", "complete", "comprehensive",
            "full analysis", "全方位", "全部", "所有"
        ]
    )

    is_personalized = any(
        keyword in lower_instruction
        for keyword in [
            "个性化", "personalized", "我的", "向我", "为我",
            "投资计划", "投资建议", "仓位建议", "风险偏好",
            "保守型", "中线持有", "我的偏好"
        ]
    )

    _alert_done = any(
        getattr(m, "name", None) == "alert_agent"
        for m in messages
        if not isinstance(m, dict)
    )
    _optimization_done = any(
        getattr(m, "name", None) == "portfolio_optimization_agent"
        for m in messages
        if not isinstance(m, dict)
    )
    _recommendation_done = any(
        getattr(m, "name", None) == "recommendation_agent"
        for m in messages
        if not isinstance(m, dict)
    )

    guard_check = state.get("guard_check", {})
    guard_retry = state.get("guard_retry_count", 0)
    guard_failed = bool(guard_check) and not guard_check.get("is_valid") and guard_retry < GUARD_MAX_RETRIES

    if guard_failed:
        corrections = guard_check.get("corrections", [])
        correction_msg = "\n".join(f"- {c}" for c in corrections) if corrections else "Address the identified issues."
        guard_msg = {"role": "user", "content": f"Guard Agent identified issues:\n{correction_msg}\nPlease fix these and regenerate your analysis."}
        messages.append(guard_msg)
        next_agents = ["strategy_expert"]
        executed = [a for a in executed if a not in ("strategy_expert", "risk_expert", "recommendation_agent", "guard_agent")]
        reasoning = f"Guard check failed (retry {guard_retry}/{GUARD_MAX_RETRIES}). Re-running strategy → risk → recommendation."
    elif is_alert:
        if _alert_done:
            next_agents = []
            reasoning = "Alert agent completed. Ending workflow."
        else:
            next_agents = ["alert_agent"]
            reasoning = "User requested real-time alert / monitoring → route to alert_agent"
    elif is_optimization:
        if _optimization_done:
            next_agents = []
            reasoning = "Portfolio optimization agent completed. Ending workflow."
        else:
            next_agents = ["portfolio_optimization_agent"]
            reasoning = "User requested portfolio optimization → route to portfolio_optimization_agent"
    elif is_personalized and not is_comprehensive:
        if _recommendation_done:
            next_agents = []
            reasoning = "Recommendation agent completed. Ending workflow."
        else:
            next_agents = ["recommendation_agent"]
            reasoning = "User requested personalized recommendation → route to recommendation_agent"
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

        if not next_agents and "recommendation_agent" not in executed_set:
            next_agents = ["recommendation_agent"]
            reasoning = "Full analysis done. Routing to recommendation for personalized advice."
        elif not next_agents and "recommendation_agent" in executed_set and "guard_agent" not in executed_set:
            next_agents = ["guard_agent"]
            reasoning = "Recommendation complete. Routing to Guard Agent for fact-check verification."
        elif not next_agents:
            reasoning = "Guard verification passed. Analysis pipeline complete."
        else:
            reasoning = "Deterministic full-analysis route."

    print("\n🎛️ Orchestrator Decision:")
    print(f"   User Instruction: {user_instruction[:80]}...")
    print(f"   Executed: {executed}")
    print(f"   Next: {next_agents}")
    print(f"   Reasoning: {reasoning}\n")

    if not next_agents:
        return {"next": "__end__", "orchestrator_reasoning": reasoning}

    result = {
        "next": next_agents,
        "executed_agents": executed + next_agents,
        "orchestrator_reasoning": reasoning,
    }
    if guard_failed:
        result["guard_check"] = {}
    return result
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
workflow.add_node("alert_agent", alert_agent)
workflow.add_node("recommendation_agent", recommendation_agent)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("portfolio_optimization_agent", portfolio_optimization_agent)
workflow.add_node("guard_agent", guard_agent)

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
        "alert_agent": "alert_agent",
        "recommendation_agent": "recommendation_agent",
        "portfolio_optimization_agent": "portfolio_optimization_agent",
        "guard_agent": "guard_agent",
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
    "alert_agent",
    "comparison_agent",
    "portfolio_optimization_agent",
    "recommendation_agent",
]:
    workflow.add_edge(agent, "orchestrator")

workflow.add_conditional_edges(
    "guard_agent",
    lambda state: (
        "__end__"
        if state.get("guard_check", {}).get("is_valid")
        or state.get("guard_retry_count", 0) >= GUARD_MAX_RETRIES
        else "orchestrator"
    ),
    {
        "orchestrator": "orchestrator",
        "__end__": END,
    },
)

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]