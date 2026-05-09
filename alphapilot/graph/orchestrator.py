from typing import Dict, Any
import json
import re
from graph.state import GraphState
from config.llm import get_llm
from graph.memory import load_persistent_memory

model = get_llm("orchestrator")

def orchestrator_node(state: GraphState) -> Dict[str, Any]:
    """
    Memory 最终智能版 Orchestrator - 支持智能部分更新
    """
    messages = state.get("messages", [])
    executed = state.get("executed_agents", [])
    stock_symbol = state.get("stock_symbol", "Unknown Stock")

    user_instruction = next(
        (getattr(m, "content", m.get("content", "")) 
         for m in messages 
         if getattr(m, "role", None) == "user" or (isinstance(m, dict) and m.get("role") == "user")),
        "Please perform comprehensive analysis"
    )

    # 加载历史记忆
    persistent_memory = load_persistent_memory()
    history = persistent_memory.get(stock_symbol, {})
    history_summary = (
        f"Previous analysis found (last updated: {history.get('last_updated', 'N/A')}): "
        f"{history.get('last_analysis', 'None')[:300]}..."
        if history else "No previous analysis for this stock."
    )

    print(f"📖 [Orchestrator] Historical Memory for {stock_symbol}: {'Found' if history else 'None'}")

    prompt = f"""
You are an AlphaPilot Investment Research Orchestrator.
Current Stock: {stock_symbol}
User Instruction: {user_instruction}
Executed Agents This Run: {executed or "None"}
Historical Memory: {history_summary}

Available Agents and Dependencies (STRICT):
- market_data_expert: Technical analysis (No dependencies)
- fundamental_expert: Fundamental analysis (No dependencies)
- news_sentiment_expert: News sentiment (No dependencies)
- strategy_expert: Buy/Hold/Sell (MUST wait for first 3)
- risk_expert: Risk & position (MUST wait for strategy)

Smart Decision Rules (VERY IMPORTANT):
1. If user says "comprehensive", "full analysis", "complete analysis" → ALWAYS run the FULL chain (market → fundamental → news → strategy → risk).
2. If user says "update", "refresh", "only update latest data", "update latest", "refresh news", "refresh risk", "update risk" → intelligently perform PARTIAL update: only call the necessary agents, skip completed parts using historical memory.
3. Never repeat agents already executed in this run.
4. Use historical memory to avoid redundant work whenever possible.

Return ONLY valid JSON:
{{
  "next": ["agent1", "agent2"] or "__end__",
  "reasoning": "Short explanation (mention if using history or doing partial update)"
}}
"""

    response = model.invoke(prompt)
    response_text = response.content.strip()

    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL | re.IGNORECASE)
    clean_json = json_match.group(1).strip() if json_match else response_text

    try:
        decision = json.loads(clean_json)
        next_agents = decision.get("next", "__end__")
        reasoning = decision.get("reasoning", "No reasoning provided")
    except Exception:
        next_agents = "__end__"
        reasoning = "JSON parsing failed"

    if isinstance(next_agents, str):
        next_agents = [next_agents] if next_agents != "__end__" else []

    next_agents = [a for a in next_agents if a not in executed]

    if next_agents or not executed:
        print(f"\n🎛️ Orchestrator Decision:")
        print(f"   User Instruction: {user_instruction[:70]}...")
        print(f"   Executed: {executed}")
        print(f"   Next: {next_agents}")
        print(f"   Reasoning: {reasoning}\n")

    if not next_agents:
        return {"next": "__end__"}

    return {
        "next": next_agents,
        "executed_agents": executed + next_agents,
        "orchestrator_reasoning": reasoning
    }