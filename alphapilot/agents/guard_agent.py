from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from schemas.evidence_packet import (
    EvidencePacket,
    determine_output_level,
    OutputLevel,
)
import re


def _detect_symbol_mismatch(packet_symbol: str, state_symbol: str, facts: list) -> list[str]:
    """检测标的错配：packet symbol 不一致 或 rag 内容引用其他股票。"""
    issues = []
    if packet_symbol.upper() != state_symbol.upper():
        issues.append(
            f"Symbol mismatch: evidence packet symbol={packet_symbol} "
            f"but state stock_symbol={state_symbol}"
        )

    ticker_pattern = re.compile(r'\b[A-Z]{1,5}\b')
    for f in facts:
        if f.field == "rag_context" and isinstance(f.value, str):
            found_tickers = set(ticker_pattern.findall(f.value))
            found_tickers.discard(packet_symbol.upper())
            common_tickers = {"TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META"}
            foreign = found_tickers & common_tickers
            if foreign:
                issues.append(
                    f"Symbol mismatch: rag_context contains references to {foreign} "
                    f"but requested symbol is {state_symbol}"
                )
                break
    return issues


def _hard_rule_guard(packet: dict | None, final_output_text: str, symbol: str = "") -> dict:
    """
    硬规则校验：不经过 LLM，确定性判定输出是否可以接受。
    基于 Evidence Packet 中的事实和输出等级做熔断。
    """
    if not packet:
        return {
            "is_valid": False,
            "confidence_score": 0,
            "issues": ["no evidence packet available for verification"],
            "corrections": ["rebuild evidence packet before analysis"],
            "sources": [],
            "final_reasoning": "No evidence packet in state.",
        }

    try:
        ep = EvidencePacket(**packet)
    except Exception:
        return {
            "is_valid": False,
            "confidence_score": 0,
            "issues": ["evidence packet corrupted"],
            "corrections": [],
            "sources": [],
            "final_reasoning": "Evidence packet failed schema validation.",
        }

    guard_result = determine_output_level(ep)

    symbol_issues = _detect_symbol_mismatch(
        ep.symbol, symbol, list(ep.facts)
    )

    if symbol_issues:
        return {
            "is_valid": False,
            "confidence_score": 0,
            "issues": symbol_issues,
            "corrections": ["rebuild evidence packet with correct symbol data"],
            "sources": [f.source for f in ep.facts],
            "final_reasoning": f"Symbol mismatch detected: {symbol_issues[0]}",
        }

    if guard_result.allowed_output_level == OutputLevel.INSUFFICIENT_EVIDENCE:
        return {
            "is_valid": False,
            "confidence_score": ep.evidence_score,
            "issues": [f"INSUFFICIENT_EVIDENCE: {guard_result.reason}"],
            "corrections": ["cannot produce analysis with current data"],
            "sources": [f.source for f in ep.facts],
            "final_reasoning": guard_result.reason,
        }

    facts_text = {f.field: str(f.value) for f in ep.facts}
    issues = []

    if guard_result.allowed_output_level in (OutputLevel.DATA_SUMMARY_ONLY, OutputLevel.LIMITED_ANALYSIS):
        prohibited_keywords = [
            "建议买入", "建议卖出", "强烈推荐", "目标价",
            "buy recommendation", "sell recommendation", "strong buy",
            "target price", "price target",
        ]
        output_lower = final_output_text.lower()
        for kw in prohibited_keywords:
            if kw.lower() in output_lower:
                issues.append(
                    f"Output contains '{kw}' but output_level={guard_result.allowed_output_level.value} "
                    f"(investment recommendations not allowed at this level)"
                )

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "confidence_score": ep.evidence_score,
        "issues": issues,
        "corrections": issues if not is_valid else [],
        "sources": [f.source for f in ep.facts],
        "final_reasoning": guard_result.reason,
    }


def guard_agent(state):
    """
    Guard Agent - v4 硬规则校验版。
    不再独立调用 RAG，改为基于 Evidence Packet 做确定性熔断。
    LLM 仅用于对校验结果做自然语言润色。
    """
    evidence_packet = state.get("evidence_packet")
    stock_symbol = state.get("stock_symbol", "")

    messages = state.get("messages", [])
    final_output_text = ""
    for m in reversed(messages):
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if content and not isinstance(content, list):
            final_output_text = str(content)
            break

    guard_result = _hard_rule_guard(evidence_packet, final_output_text, symbol=stock_symbol)

    retry_count = state.get("guard_retry_count", 0)
    next_retry_count = retry_count + 1 if not guard_result.get("is_valid", False) else retry_count

    print(f"\n🛡️ Guard Agent Check (v4 hard-rule, retry: {next_retry_count}):")
    print(f"   Valid: {guard_result.get('is_valid', 'N/A')}")
    print(f"   Confidence: {guard_result.get('confidence_score', 'N/A')}/100")
    print(f"   Issues: {guard_result.get('issues', [])}")
    print(f"   Corrections: {guard_result.get('corrections', [])}")
    print(f"   Reasoning: {guard_result.get('final_reasoning', 'N/A')}")

    return {
        "guard_check": guard_result,
        "confidence_score": guard_result.get("confidence_score", 0),
        "sources": guard_result.get("sources", []),
        "guard_retry_count": next_retry_count,
    }
