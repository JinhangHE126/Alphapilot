import os
from dotenv import load_dotenv
load_dotenv()

from langgraph_supervisor import create_supervisor
from agents.market_agent import market_agent
from agents.fundamental_agent import fundamental_agent
from agents.news_agent import news_agent
from graph.state import GraphState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, END, StateGraph
from config.llm import get_llm
from langchain_core.messages import AIMessage
from graph.checkpointer import get_checkpointer



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


# checkpointer = InMemorySaver()
# 使用SQLite作为持久化存储
checkpointer = get_checkpointer()



# Supervisor Node
def supervisor_node(state: GraphState) -> dict:
    """Decide which agents to run based on user input."""
    messages = state.get("messages", [])
    # last_content = messages[-1].content if messages else ""
    last_content = extract_text_content(messages[-1]).lower() if messages else ""

    needs = {
        "market_data_expert": any(
            k in last_content
            for k in ["technical", "price", "rsi", "macd", "volatility"]
        ),
        "fundamental_expert": any(
            k in last_content
            for k in ["earnings", "fundamental", "revenue", "eps"]
        ),
        "news_sentiment_expert": any(
            k in last_content for k in ["news", "sentiment"]
        ),
    }

    # 如果用户要全面分析，默认调用全部三个
    if not any(needs.values()):
        return {
            "next": [
                "market_data_expert",
                "fundamental_expert",
                "news_sentiment_expert",
            ]
        }

    # 返回需要并行执行的 Agent 列表
    next_agents = [k for k, v in needs.items() if v]
    return {"next": next_agents if next_agents else ["market_data_expert"]}


def synthesis_node(state: GraphState) -> dict:
    """Merge all expert outputs into one final response."""
    ai_messages = [m for m in state.get("messages", []) if isinstance(m, AIMessage)]

    market_text = ""
    fundamental_text = ""
    news_text = ""
    for msg in ai_messages:
        text = extract_text_content(msg).strip()
        if not text:
            continue
        name = getattr(msg, "name", "") or ""
        if name == "market_data_expert":
            market_text = text
        elif name == "fundamental_expert":
            fundamental_text = text
        elif name == "news_sentiment_expert":
            news_text = text

    def _trim_capability_disclaimer(text: str) -> str:
        markers = [
            "\n\nI cannot provide technical analysis",
            "\n\nI cannot provide technical or fundamental analysis",
            "\n\nI can only provide a fundamental analysis",
        ]
        cleaned = text
        for marker in markers:
            idx = cleaned.find(marker)
            if idx != -1:
                cleaned = cleaned[:idx].strip()
        return cleaned

    market_text = _trim_capability_disclaimer(market_text)
    fundamental_text = _trim_capability_disclaimer(fundamental_text)
    news_text = _trim_capability_disclaimer(news_text)

    sections = []
    if market_text:
        sections.append(f"## Market Analysis\n{market_text}")
    if fundamental_text:
        sections.append(f"## Fundamental Analysis\n{fundamental_text}")
    if news_text:
        sections.append(f"## News & Sentiment Analysis\n{news_text}")

    final_text = "\n\n".join(sections) if sections else "No expert output generated."
    return {"messages": [{"role": "assistant", "content": final_text}]}


workflow = StateGraph(GraphState)

workflow.add_node("market_data_expert", market_agent)
workflow.add_node("fundamental_expert", fundamental_agent)
workflow.add_node("news_sentiment_expert", news_agent)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("synthesis", synthesis_node)

workflow.add_edge(START, "supervisor")

# 并行路由
workflow.add_conditional_edges(
    "supervisor",
    lambda state: state.get("next", []),
    {
        "market_data_expert": "market_data_expert",
        "fundamental_expert": "fundamental_expert",
        "news_sentiment_expert": "news_sentiment_expert",
        END: END,
    }
)

# Wait for all expert branches, then synthesize once.
workflow.add_edge(
    ["market_data_expert", "fundamental_expert", "news_sentiment_expert"],
    "synthesis",
)
workflow.add_edge("synthesis", END)

# 编译workflow, 使用SQLite作为持久化存储
app = workflow.compile(checkpointer=checkpointer)

__all__ = ["app"]