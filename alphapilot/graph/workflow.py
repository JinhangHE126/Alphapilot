from langgraph.graph import START, END, StateGraph

from graph.state import GraphState
from graph.checkpointer import get_checkpointer

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent

checkpointer = get_checkpointer()

# ====================== 智能 Supervisor (5.8 Explainability 版) ======================
def supervisor_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    last_content = messages[-1].content if messages else ""
    
    # Agent 执行可用性判断（严格依赖顺序 + 防重复）
    available_agents = {
        "market_data_expert": "market_data_expert" not in executed,
        "fundamental_expert": "fundamental_expert" not in executed,
        "news_sentiment_expert": "news_sentiment_expert" not in executed,
        "strategy_expert": "strategy_expert" not in executed 
                           and all(a in executed for a in ["market_data_expert", "fundamental_expert", "news_sentiment_expert"]),
        "risk_expert": "risk_expert" not in executed and "strategy_expert" in executed,
    }
    
    next_agents = [name for name, need in available_agents.items() if need]
    
    # === 新增：Explainability 日志（5.8 Step 1）===
    print(f"\n🔍 Supervisor 决策日志:")
    print(f"   用户输入: {last_content[:80]}...")
    print(f"   已执行 Agent: {executed}")
    print(f"   下一步执行: {next_agents}")
    print(f"   当前执行进度: {len(executed)}/5\n")
    
    if not next_agents:
        return {"next": "__end__"}
    
    return {
        "next": next_agents,
        "executed_agents": executed + next_agents   # 更新执行记录
    }


# ====================== StateGraph ======================
workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("strategy_expert", strategy_agent)
workflow.add_node("risk_expert", risk_agent)
workflow.add_node("supervisor", supervisor_node)

workflow.add_edge(START, "supervisor")

workflow.add_conditional_edges(
    "supervisor",
    lambda state: state.get("next", "__end__"),
    {
        "market_data_expert": "market_data_expert",
        "fundamental_expert": "fundamental_expert",
        "news_sentiment_expert": "news_sentiment_expert",
        "strategy_expert": "strategy_expert",
        "risk_expert": "risk_expert",
        "__end__": END,
    }
)

# 所有 Agent 执行完后回到 supervisor
for agent in [
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "strategy_expert",
    "risk_expert"
]:
    workflow.add_edge(agent, "supervisor")

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]