import json

# from alphapilot.test.test_end_to_end import config
from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph

from graph.state import GraphState
from graph.checkpointer import get_checkpointer
from config.llm import get_llm
from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from agents.strategy_agent import strategy_agent
from agents.risk_agent import risk_agent

load_dotenv()

checkpointer = get_checkpointer()
model = get_llm("strategy")


def extract_text_content(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


# ====================== 智能 Supervisor (优化版 - 规则驱动) ======================
def supervisor_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    last_content = messages[-1].content if messages else ""
    
    # 已经执行过的 Agent 不再重复调用
    available_agents = {
        "market_data_expert": "market_data_expert" not in executed,
        "fundamental_expert": "fundamental_expert" not in executed,
        "news_sentiment_expert": "news_sentiment_expert" not in executed,
        "strategy_expert": "strategy_expert" not in executed 
                           and all(a in executed for a in ["market_data_expert", "fundamental_expert", "news_sentiment_expert"]),
        "risk_expert": "risk_expert" not in executed and "strategy_expert" in executed,
    }
    
    # 如果没有任何 Agent 需要执行，直接结束
    if not any(available_agents.values()):
        return {"next": "__end__"}
    
    # 优先调用基础3个 Agent
    next_agents = [name for name, need in available_agents.items() if need]
    
    # 如果基础3个已完成，则调用 Strategy + Risk（可并行）
    if len(next_agents) == 0:
        next_agents = ["strategy_expert", "risk_expert"]
    
    return {
        "next": next_agents,
        "executed_agents": executed + next_agents   # 记录已执行，防止重复
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

# 所有 Agent 执行完后回到 supervisor 继续决策
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


# def supervisor_node(state: GraphState) -> dict:
#     """Use LLM to decide next agent(s)."""
#     messages = state.get("messages", [])
#     last_message = extract_text_content(messages[-1]) if messages else ""

#     prompt = f"""
# 你是一位 AlphaPilot 投资研究主管。
# 当前可用 Agent 及其职责：
# - market_data_expert：技术面（价格、RSI、MACD、波动率）
# - fundamental_expert：基本面（财报、营收、EPS、毛利率）
# - news_sentiment_expert：新闻舆情和事件分析
# - strategy_expert：综合判断并给出 Buy/Hold/Sell 建议
# - risk_expert：风险评估、止损建议、仓位控制

# 用户最新需求：{last_message}

# 请判断需要调用哪些 Agent（可并行调用多个）。
# 只返回 JSON：
# {{"next": ["agent_name1", "agent_name2"]}}
# 或
# {{"next": "__end__"}}
# """

#     response = model.invoke(prompt)
#     response_text = extract_text_content(response).strip()

#     try:
#         decision = json.loads(response_text)
#         next_step = decision.get("next", "__end__")
#     except json.JSONDecodeError:
#         next_step = "__end__"

#     if isinstance(next_step, str):
#         if next_step != "__end__":
#             next_step = [next_step]
#     elif not isinstance(next_step, list):
#         next_step = "__end__"

#     return {"next": next_step}


# workflow = StateGraph(GraphState)

# workflow.add_node("market_data_expert", market_agent)
# workflow.add_node("fundamental_expert", fundamental_agent)
# workflow.add_node("news_sentiment_expert", news_agent)
# workflow.add_node("strategy_expert", strategy_agent)
# workflow.add_node("risk_expert", risk_agent)
# workflow.add_node("supervisor", supervisor_node)

# workflow.add_edge(START, "supervisor")

# workflow.add_conditional_edges(
#     "supervisor",
#     lambda state: state.get("next", "__end__"),
#     {
#         "market_data_expert": "market_data_expert",
#         "fundamental_expert": "fundamental_expert",
#         "news_sentiment_expert": "news_sentiment_expert",
#         "strategy_expert": "strategy_expert",
#         "risk_expert": "risk_expert",
#         "__end__": END,
#     },
# )

# for agent in [
#     "market_data_expert",
#     "fundamental_expert",
#     "news_sentiment_expert",
#     "strategy_expert",
#     "risk_expert",
# ]:
#     workflow.add_edge(agent, "supervisor")
#     # workflow.add_edge(agent, END)

# app = workflow.compile(
#     checkpointer=checkpointer,
#     # config={"configurable": {"max_concurrency": 2}}
#     )

# __all__ = ["app"]