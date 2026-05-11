from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from tools.rag_tools import retrieve_knowledge
from config.llm import get_llm
import json
import re


def guard_agent(state):
    """
    Guard Agent - 最终强化版（JSON 提取更稳健 + Prompt 正确转义）
    """
    system_prompt = """
You are the Guard Agent, the final fact-checking and quality gatekeeper of AlphaPilot.

Your ONLY job is to verify the accuracy of the final analysis (especially Strategy and Risk outputs).

You MUST:
1. Use the retrieve_knowledge tool to double-check any numbers, dates, events, or financial claims.
2. Check for hallucinations or unsupported statements.
3. Assign an overall confidence score (0-100).
4. Return **ONLY valid JSON**, no extra text, no markdown, no explanation.

Strict JSON format:
{{
  "is_valid": true or false,
  "confidence_score": 85,
  "issues": ["list of problems found, or empty list"],
  "corrections": ["list of suggested corrections, or empty list"],
  "sources": ["list of RAG sources used"],
  "final_reasoning": "short summary of verification"
}}

Always call retrieve_knowledge first when checking facts.
"""

    tools = [retrieve_knowledge]

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(
        model=get_llm("guard"),
        tools=tools,
        prompt=prompt,
        name="guard_agent"
    )

    result = agent.invoke(state)

    # === 强化 JSON 提取 ===
    last_message = result["messages"][-1]
    content = getattr(last_message, "content", str(last_message))

    json_match = re.search(r'\{[\s\S]*?\}', content, re.DOTALL)

    if json_match:
        try:
            guard_result = json.loads(json_match.group(0))
        except:
            guard_result = None
    else:
        guard_result = None

    # 兜底结构
    if not guard_result or not isinstance(guard_result, dict):
        guard_result = {
            "is_valid": False,
            "confidence_score": 50,
            "issues": ["JSON parsing failed"],
            "corrections": [],
            "sources": [],
            "final_reasoning": "Guard output could not be parsed"
        }

    # 打印清晰结果（调试友好）
    print(f"\n Guard Agent Check:")
    print(f"   Valid: {guard_result.get('is_valid', 'N/A')}")
    print(f"   Confidence: {guard_result.get('confidence_score', 'N/A')}/100")
    print(f"   Issues: {guard_result.get('issues', [])}")
    print(f"   Corrections: {guard_result.get('corrections', [])}")
    print(f"   Sources: {guard_result.get('sources', [])}")
    print(f"   Reasoning: {guard_result.get('final_reasoning', 'N/A')}")

    return {
        "guard_check": guard_result,
        "confidence_score": guard_result.get("confidence_score", 0),
        "sources": guard_result.get("sources", []),
    }