from langgraph.graph import START, END, StateGraph
from graph.state import GraphState
from graph.checkpointer import get_checkpointer
from graph.orchestrator import orchestrator_node
from graph.memory import memory_node

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent


checkpointer = get_checkpointer()

# ====================== StateGraph ======================
workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("strategy_expert", strategy_agent)
workflow.add_node("risk_expert", risk_agent)
workflow.add_node("orchestrator", orchestrator_node)   
workflow.add_node("memory", memory_node)

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
        "__end__": "memory",
    }
)
for agent in ["market_data_expert", "fundamental_expert", "news_sentiment_expert", "strategy_expert", "risk_expert"]:
    workflow.add_edge(agent, "orchestrator")

workflow.add_edge("memory", END)

app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]