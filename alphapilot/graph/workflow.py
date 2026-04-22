import os
from dotenv import load_dotenv
load_dotenv()

from langgraph_supervisor import create_supervisor
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.market_agent import market_agent
from graph.state import GraphState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph


model = ChatGoogleGenerativeAI(
    model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1,
)
checkpoint = InMemorySaver()

# Extract text content from message
def extract_text_content(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part)
    return str(content)





# Supervisor Node
def supervisor_node(state: GraphState) -> dict:
    '''Supervisor 简单路由(后续升级为LLM)'''
    messages = state.get("messages", [])
    # last_content = messages[-1].content if messages else ""
    last_content = extract_text_content(messages[-1]).lower() if messages else ""

    # 当前阶段只支持 market_data_expert
    # if any(k in last_content.lower() for k in ["market", "stock", "price", "volume", "technical", "analysis"]):
    if any(k in last_content for k in ["technical analysis", "market data", "rsi", "macd", "price", "tsla"]):
        # technical analysis
        return {'next': 'market_node'}
    else:
        return {'next': END}



# Market Agent Node(use react agent)
def market_node(state: GraphState) -> dict:
    result = market_agent.invoke({
        "messages": state["messages"]
    })

    final_message = result["messages"][-1]
    content = final_message.content

    if isinstance(content, str):
        market_text = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        market_text = "\n".join(parts)
    else:
        market_text = str(content)

    return {
        "messages": [final_message],
        "market_data": market_text,
    }

workflow = StateGraph(GraphState)

workflow.add_node('supervisor', supervisor_node)
workflow.add_node('market_node', market_node)

#Add adge
workflow.add_edge(START, 'supervisor')
# automatically decide where to go 
workflow.add_conditional_edges(
    'supervisor', # From supervisor node
    lambda state: state['next'], # decide where to go
    {
        'market_node': 'market_node',
        END: END,
    }
)

# workflow.add_edge('market_node', 'supervisor') # go back to supervisor node to get next instruction
# 调试阶段先直接end节点. 后面有其他的agent时, 再添加edge.
workflow.add_edge('market_node', END)

app = workflow.compile(checkpointer=checkpoint)


__all__ = ["app"]