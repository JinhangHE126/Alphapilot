from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from tools.rag_tools import retrieve_knowledge
from config.llm import get_llm
import json
import re


def _extract_guard_json(content: str):
    """Extract JSON from raw LLM output with a couple of robust fallbacks."""
    if not content:
        return None

    # 1) Best case: model returns plain JSON directly
    try:
        parsed = json.loads(content.strip())
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 2) JSON fenced code block
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
    if fenced_match:
        try:
            parsed = json.loads(fenced_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # 3) First object-like substring
    json_match = re.search(r"\{[\s\S]*\}", content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0).strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def _normalize_guard_result(raw: dict) -> dict:
    """Normalize guard payload shape to a predictable schema."""
    normalized = {
        "is_valid": bool(raw.get("is_valid", False)),
        "confidence_score": int(raw.get("confidence_score", 0) or 0),
        "issues": raw.get("issues", []),
        "corrections": raw.get("corrections", []),
        "sources": raw.get("sources", []),
        "final_reasoning": raw.get("final_reasoning", "N/A"),
    }
    if not isinstance(normalized["issues"], list):
        normalized["issues"] = [str(normalized["issues"])]
    if not isinstance(normalized["corrections"], list):
        normalized["corrections"] = [str(normalized["corrections"])]
    if not isinstance(normalized["sources"], list):
        normalized["sources"] = [str(normalized["sources"])]
    return normalized


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

    guard_result = _extract_guard_json(content)

    # JSON 解析失败时，进行一次严格格式重试，避免直接进入兜底失败
    if not guard_result:
        retry_prompt = (
            "Return ONLY valid JSON following the required schema. "
            "No markdown, no prose, no tool trace."
        )
        retry_state = {
            **state,
            "messages": list(state.get("messages", [])) + [{"role": "user", "content": retry_prompt}],
        }
        retry_result = agent.invoke(retry_state)
        retry_message = retry_result["messages"][-1]
        retry_content = getattr(retry_message, "content", str(retry_message))
        guard_result = _extract_guard_json(retry_content)

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
    else:
        guard_result = _normalize_guard_result(guard_result)

    # 打印清晰结果（调试友好）
    retry_count = state.get("guard_retry_count", 0)
    next_retry_count = retry_count + 1 if not guard_result.get("is_valid", False) else retry_count

    print(f"\n Guard Agent Check (retry: {next_retry_count}):")
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
        "guard_retry_count": next_retry_count,
    }
