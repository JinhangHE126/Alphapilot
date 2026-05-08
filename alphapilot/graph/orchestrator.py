from typing import Dict, Any
import json
import re
from graph.state import GraphState
from config.llm import get_llm

model = get_llm("orchestrator")

def orchestrator_node(state: GraphState) -> Dict[str, Any]:
    """
    智能 Orchestrator：根据用户指令 + 已执行 Agent 动态决定下一步
    """
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    stock_symbol = state.get("stock_symbol", "Unknown Stock")
   
    # 提取用户原始指令（支持 dict 和 Message 对象）
    user_instruction = "Please perform comprehensive analysis"
    for m in messages:
        if getattr(m, "role", None) == "user" or (isinstance(m, dict) and m.get("role") == "user"):
            content = getattr(m, "content", m.get("content", "")) if isinstance(m, dict) else m.content
            user_instruction = str(content)
            break
   
    prompt = f"""
You are an AlphaPilot Investment Research Orchestrator.
Current Stock: {stock_symbol}
Original User Instruction: {user_instruction}
Executed Agents: {executed}

Available Agents and Dependencies:
- market_data_expert: Technical analysis (No dependencies)
- fundamental_expert: Fundamental analysis (No dependencies)
- news_sentiment_expert: News sentiment (No dependencies)
- strategy_expert: Buy/Hold/Sell advice (Must be after the first 3)
- risk_expert: Risk and position suggestions (Must be after strategy)

Rules:
1. Do not call agents that have already been executed.
2. Strictly follow dependency relationships.
3. If the user specified a scope (e.g., "only analyze fundamentals and risk"), only call relevant Agents.

Return ONLY JSON (no explanation):
{{
  "next": ["agent1", "agent2"] or "__end__",
  "reasoning": "One-sentence explanation of decision reason"
}}
"""

    response = model.invoke(prompt)
    response_text = response.content.strip()
   
    try:
        decision = json.loads(response_text)
        next_agents = decision.get("next", "__end__")
        reasoning = decision.get("reasoning", "No reasoning provided")
    except:
        next_agents = "__end__"
        reasoning = "JSON parsing failed, terminating process"
   
    if isinstance(next_agents, str):
        next_agents = [next_agents] if next_agents != "__end__" else []
   
    next_agents = [a for a in next_agents if a not in executed]
   
    # Clean English Logging
    if next_agents or not executed:
        print(f"\n🎛️ Orchestrator Decision:")
        print(f" User Instruction: {user_instruction[:60]}...")
        print(f" Executed: {executed}")
        print(f" Next step: {next_agents}")
        print(f" Reasoning: {reasoning}\n")
   
    if not next_agents:
        return {"next": "__end__"}
   
    return {
        "next": next_agents,
        "executed_agents": executed + next_agents,
        "orchestrator_reasoning": reasoning
    }