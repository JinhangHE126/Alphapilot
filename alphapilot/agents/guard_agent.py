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


_KEYWORD_FIELD_MAP: dict[str, str] = {
    "current price": "current_price",
    "股价": "current_price",
    "价格": "current_price",
    "price": "current_price",
    "rsi": "rsi_14",
    "macd": "macd",
    "volatility": "volatility_20d_annualized",
    "波动率": "volatility_20d_annualized",
    "pe ratio": "pe_ratio",
    "p/e": "pe_ratio",
    "市盈率": "pe_ratio",
    "pb ratio": "pb_ratio",
    "p/b": "pb_ratio",
    "市净率": "pb_ratio",
    "market cap": "market_cap",
    "市值": "market_cap",
    "revenue growth": "revenue_growth_yoy",
    "营收增长": "revenue_growth_yoy",
    "eps growth": "eps_growth_yoy",
    "eps增长": "eps_growth_yoy",
}


def _number_variants(value) -> set[str]:
    variants = set()
    try:
        num = float(value)
    except (TypeError, ValueError):
        return variants
    variants.add(str(int(num)) if num.is_integer() else str(num))
    variants.add(f"{num:.1f}")
    variants.add(f"{num:.2f}")
    variants.add(f"{num:.3f}")
    if abs(num) <= 1000:
        variants.add(f"{num:,.2f}".replace(",", ""))
    return {v.rstrip("0").rstrip(".") if "." in v else v for v in variants}


def _find_ungrounded_claims(ep: EvidencePacket, output_text: str) -> list[str]:
    """
    规则型 grounding 检查：
    1) 报告提到某类关键字段，但 packet 中没有该字段 -> ungrounded
    2) 报告含 target price/目标价等高风险结论 -> ungrounded
    """
    issues = []
    text = output_text or ""
    lower = text.lower()
    available_fields = {f.field for f in ep.facts}

    for keyword, required_field in _KEYWORD_FIELD_MAP.items():
        if keyword in lower and required_field not in available_fields:
            issues.append(
                f"Ungrounded claim: mentions '{keyword}' but Evidence Packet has no field '{required_field}'"
            )

    target_price_patterns = [
        r"\btarget\s*price\b",
        r"目标价",
        r"\bprice\s*target\b",
    ]
    if any(re.search(pat, lower) for pat in target_price_patterns):
        issues.append(
            "Ungrounded claim: target price statement is not allowed unless explicitly grounded in Evidence Packet"
        )

    # Optional value-level check for frequently abused numeric fields.
    numeric_fields = {"current_price", "pe_ratio", "pb_ratio", "revenue_growth_yoy", "eps_growth_yoy"}
    numeric_fact_map = {
        f.field: _number_variants(f.value)
        for f in ep.facts
        if f.field in numeric_fields
    }
    for field_name, variants in numeric_fact_map.items():
        if not variants:
            continue
        keyword_hits = [kw for kw, fld in _KEYWORD_FIELD_MAP.items() if fld == field_name and kw in lower]
        if keyword_hits and not any(v and v in lower for v in variants):
            issues.append(
                f"Potential ungrounded numeric claim: '{field_name}' is mentioned but numeric value not traceable to packet fact"
            )

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

    issues = []

    if guard_result.allowed_output_level in (OutputLevel.DATA_SUMMARY_ONLY, OutputLevel.LIMITED_ANALYSIS, OutputLevel.LIMITED_ANALYSIS_PARTIAL):
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

        import json as _json
        for pattern in [r'"recommendation"\s*:\s*"(Buy|Hold|Sell)"',
                        r'"recommendation"\s*:\s*"(买入|持有|卖出)"']:
            m = re.search(pattern, final_output_text, re.IGNORECASE)
            if m:
                issues.append(
                    f"Strategy agent returned recommendation='{m.group(1)}' "
                    f"but output_level={guard_result.allowed_output_level.value} "
                    f"(investment recommendations not allowed at this level)"
                )

    if guard_result.allowed_output_level == OutputLevel.LIMITED_ANALYSIS_PARTIAL:
        if '"data_quality"' not in final_output_text:
            issues.append(
                "LIMITED_ANALYSIS_PARTIAL: Strategy/Risk output missing 'data_quality' field"
            )

    issues.extend(_find_ungrounded_claims(ep, final_output_text))

    is_valid = len(issues) == 0

    confidence = ep.evidence_score
    if guard_result.allowed_output_level == OutputLevel.LIMITED_ANALYSIS_PARTIAL:
        confidence = max(0, confidence - 5)

    return {
        "is_valid": is_valid,
        "confidence_score": confidence,
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
        "output_level": evidence_packet.get("allowed_output_level", "") if evidence_packet else "",
    }
