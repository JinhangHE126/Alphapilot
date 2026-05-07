from langgraph.graph import START, END, StateGraph

from graph.state import GraphState
from graph.checkpointer import get_checkpointer

from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent

checkpointer = get_checkpointer()

# ====================== 智能 Supervisor (5.8 最终报告修复版) ======================
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
    
    # === Explainability 日志 ===
    print(f"\n🔍 Supervisor 决策日志:")
    print(f"   用户输入: {last_content[:80]}...")
    print(f"   已执行 Agent: {executed}")
    print(f"   下一步执行: {next_agents}")
    print(f"   当前执行进度: {len(executed)}/5\n")
    
    if not next_agents:
        # === 修复版最终报告：从 messages 中智能提取真实内容 ===
        def get_last_agent_content(agent_name: str, max_len: int = 800) -> str:
            for msg in reversed(messages):
                if getattr(msg, "name", None) == agent_name:
                    content = getattr(msg, "content", str(msg))
                    return str(content)[:max_len] + "..." if len(str(content)) > max_len else str(content)
            return "未生成"
        
        final_report = f"""
# AlphaPilot 完整投资分析报告 - {state.get('stock_symbol', 'TSLA')}

## 📊 执行路径
已执行 Agent: {executed}

## 🎯 最终投资建议（Strategy Agent）
{get_last_agent_content('strategy_expert', 1200)}

## ⚠️ 风险评估（Risk Agent）
{get_last_agent_content('risk_expert', 1000)}

## 📋 详细分析
**技术面（Market Agent）**  
{get_last_agent_content('market_data_expert', 400)}

**基本面（Fundamental Agent）**  
{get_last_agent_content('fundamental_expert', 400)}

**舆情分析（News Agent）**  
{get_last_agent_content('news_sentiment_expert', 400)}
"""
        return {"next": "__end__", "final_report": final_report}
    
    return {
        "next": next_agents,
        "executed_agents": executed + next_agents
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