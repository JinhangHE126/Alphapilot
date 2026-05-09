import json
from pathlib import Path
from typing import Dict, Any
from graph.state import GraphState

MEMORY_FILE = Path("data/memory.json")
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_persistent_memory() -> Dict:
    """加载持久化记忆"""
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_persistent_memory(memory: Dict):
    """保存记忆到文件"""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def memory_node(state: GraphState) -> Dict[str, Any]:
    """
    Memory Agent - 持久化版本
    """
    stock_symbol = state.get("stock_symbol", "Unknown")
    final_report = state.get("final_report", "")
    executed = state.get("executed_agents", [])

    # 加载历史
    persistent_memory = load_persistent_memory()

    # 更新当前股票记忆
    persistent_memory[stock_symbol] = {
        "last_analysis": final_report[:800] + "..." if final_report else "No report yet",
        "executed_agents": executed,
        "last_updated": "2026-05-09"
    }

    # 更新用户画像
    user_profile = state.get("user_profile", {})
    analyzed = user_profile.setdefault("analyzed_stocks", [])
    if stock_symbol not in analyzed:
        analyzed.append(stock_symbol)

    # 保存
    save_persistent_memory(persistent_memory)

    print(f"💾 [Memory] Saved analysis for {stock_symbol}")
    print(f"   Total analyzed stocks: {len(analyzed)}")
    print(f"   History size: {len(persistent_memory)} stocks")
    if len(persistent_memory) > 1:
        print(f"   📌 Previous stocks: {list(persistent_memory.keys())[:-1]}")

    return {
        "memory": persistent_memory,
        "user_profile": user_profile,
        "conversation_history": state.get("conversation_history", []) + [{
            "stock": stock_symbol,
            "summary": final_report[:400] + "..." if final_report else ""
        }]
    }