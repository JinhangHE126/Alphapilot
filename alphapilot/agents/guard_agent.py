from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm
from schemas.evidence_packet import (
    EvidencePacket,
    determine_output_level,
    OutputLevel,
    DocumentChunk,
)
import re


def _strip_machine_json_blocks(text: str) -> str:
    """Ignore fenced JSON metadata blocks when checking user-visible report text."""
    if not text:
        return ""
    return re.sub(r"```(?:json)?\s*[\s\S]*?\s*```", "", text).strip()


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


# ── 文档 Grounding 辅助 ──

# Level 3 模式粗检用（检测 "是否有文档引用句式"）
_DOC_CITATION_PATTERNS_CN = [
    r"(?:根据|来自|参照|参考|引用|援引|依据).{0,10}(?:年报|年度报告|财报|电话会议|会议记录|研报|研究报告|季报|半年报)",
    r"(?:年报|年度报告|财报|电话会议|会议记录|研报|研究报告|季报|半年报).{0,10}(?:指出|显示|表明|披露|提到|提及|揭示|透露|说明)",
    r"(?:Document Evidence|文档证据|文档来源|文件证据).{0,15}(?:显示|指出|表明|披露|提到|揭示)",
]

_DOC_CITATION_PATTERNS_EN = [
    r"(?:according to|based on|per|as stated in|as disclosed in|as noted in).{0,20}(?:annual report|earnings call|10-K|10-Q|filing|research report|transcript)",
    r"(?:annual report|earnings call|10-K|10-Q|filing|research report|transcript).{0,20}(?:states?|discloses?|notes?|reveals?|indicates?|shows?)",
    r"(?:Document Evidence|document source).{0,20}(?:states?|shows?|indicates?|reveals?)",
    r"(?:management|CEO|CFO).{0,15}(?:stated|noted|mentioned|commented|said).{0,30}(?:earnings call|transcript|annual report|filing)",
]

_DOC_GROUNDING_MODEL = None


def _get_doc_grounding_model():
    """懒加载 embedding 模型，避免 Guard 每次检查都重新实例化。"""
    global _DOC_GROUNDING_MODEL
    if _DOC_GROUNDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _DOC_GROUNDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _DOC_GROUNDING_MODEL


_DOC_CITE_RE = re.compile(r"\[doc:(\d+)\]", re.IGNORECASE)

# 泛化/推测性表述 — 不算对具体 chunk 的引用，跳过 L2 语义拦截
_HEURISTIC_DOC_PHRASES = (
    "通常", "一般", "往往", "可能", "虽未直接提及", "虽未明确提及",
    "并未直接提及", "可能被解读", "可能被市场解读", "通常会在",
    "typically", "generally", "usually", "may be interpreted",
    "although not directly mentioned", "not directly mentioned",
)


def _extract_doc_citation_indices(text: str) -> set[int]:
    return {int(n) for n in _DOC_CITE_RE.findall(text)}


def _span_has_valid_doc_marker(
    snippet: str,
    valid_indices: set[int],
    output_text: str = "",
    span_start: int = 0,
    span_end: int = 0,
) -> bool:
    """段落内（含前后扩展窗口）含有合法 [doc:N] 时，跳过 L2 改写惩罚。"""
    if not valid_indices:
        return False
    window_start = max(0, span_start - 200)
    window_end = min(len(output_text), span_end + 80) if output_text else len(snippet)
    search_text = output_text[window_start:window_end] if output_text else snippet
    cited = _extract_doc_citation_indices(search_text)
    return bool(cited) and cited <= valid_indices


def _is_heuristic_doc_reference(snippet: str) -> bool:
    """推测性/模板化表述，非对具体文档内容的断言。"""
    lower = snippet.lower()
    return any(p in snippet or p in lower for p in _HEURISTIC_DOC_PHRASES)


def _extract_doc_citation_spans(output_text: str) -> list[tuple[str, str, int, int]]:
    """
    从 Agent 输出中提取所有文档引用段落。
    返回 [(matched_text, doc_type_hint, start_pos, end_pos), ...]
    """
    spans: list[tuple[str, str, int, int]] = []
    patterns: list[tuple[str, str]] = [
        # 中文 — 年报/报告
        (r"(?:根据|来自|参照|参考|引用|援引|依据).{0,30}?(?:\d{4}\s*年\s*(?:年|财年|年度)?\s*(?:报|报告)|年报|年度报告|年報)", "annual_report"),
        (r"(?:\d{4}\s*年\s*(?:年|财年|年度)?\s*(?:报|报告)|年报|年度报告|年報).{0,50}?(?:指出|显示|表明|披露|提到|提及|揭示|透露|说明|显示)", "annual_report"),
        # 中文 — 电话会议
        (r"(?:Q[1-4]\s*(?:季度|财报|业绩)?\s*(?:电话会议|业绩会)|财报电话会|业绩说明会).{0,50}?(?:指出|显示|表明|披露|提到|透露|表示|称)", "earnings_call"),
        # 中文 — 研报
        (r"(?:券商研报|研究报告|券商报告|投行报告)", "research_report"),
        # 中文 — Document Evidence 通用
        (r"(?:Document Evidence|文档证据|文档来源|文件证据|RAG文档).{0,50}?(?:显示|指出|表明|披露|提到|揭示)", "document"),
        # 英文 — 年报/文件
        (r"(?:according to|based on|per|as stated in|as disclosed in|as noted in|pursuant to).{0,40}?(?:annual report|10-K|10-Q|filing|annual filing)", "annual_report"),
        (r"(?:annual report|10-K|10-Q|filing).{0,40}?(?:states?|discloses?|notes?|reveals?|indicates?|shows?|highlights?)", "annual_report"),
        # 英文 — 电话会议
        (r"(?:according to|during|in|per).{0,30}?(?:Q[1-4]\s*(?:20\d{2})?\s*(?:earnings call|transcript|call))", "earnings_call"),
        (r"(?:earnings call|transcript).{0,40}?(?:states?|discloses?|notes?|reveals?|indicates?|shows?|highlighted)", "earnings_call"),
        # 英文 — 管理层引用
        (r"(?:management|CEO|CFO|executive).{0,30}?(?:stated|noted|mentioned|commented|said|indicated|highlighted).{0,40}?(?:earnings call|transcript|annual report|filing|call)", "earnings_call"),
        # 英文 — Document Evidence 通用
        (r"(?:Document Evidence|document source).{0,40}?(?:states?|shows?|indicates?|reveals?|notes?)", "document"),
        # 英文 — 研报
        (r"(?:research report|analyst report|broker report|equity research)", "research_report"),
    ]
    for pat, doc_type in patterns:
        for m in re.finditer(pat, output_text, re.IGNORECASE):
            start = max(0, m.start())
            end = min(len(output_text), m.end() + 120)
            snippet = output_text[start:end]
            spans.append((snippet, doc_type, start, end))
    return spans


def _find_ungrounded_doc_claims(
    output_text: str,
    ep: EvidencePacket,
) -> tuple[list[str], list[str]]:
    """
    文档 Grounding 检查 (v2)。返回 (issues, warnings)。

    Level 1 — chunk_id 精确匹配（issues，阻断）:
    - 检查 [doc:N] 引用标记是否在 document_evidence 中存在

    Level 2 — 内容级语义匹配（issues，阻断）:
    - 提取 Agent 输出中疑似文档引用的段落
    - 与 document_evidence 各 chunk 做 embedding 相似度匹配
    - 所有 chunk 相似度均低于阈值 → ungrounded

    Level 3 — 模式粗检（warnings，不阻断）:
    - 检测输出中是否有文档引用句式
    - document_evidence 为空时降级为 issues（因完全无法追溯）
    """
    if not output_text:
        return [], []

    doc_evidence = list(ep.document_evidence) if ep.document_evidence else []
    issues: list[str] = []
    warnings: list[str] = []

    # ═══ Level 1: [doc:N] citation marker exact matching ═══
    citation_matches = _DOC_CITE_RE.findall(output_text)
    valid_indices = set(range(1, len(doc_evidence) + 1))
    if citation_matches:
        cited_indices = {int(n) for n in citation_matches}
        invalid = cited_indices - valid_indices
        if invalid:
            issues.append(
                f"Ungrounded doc citation: reference markers {sorted(invalid)} "
                f"are out of range (document_evidence has {len(doc_evidence)} chunks)"
            )

    # ═══ Level 2: content-level semantic matching ═══
    citation_spans = _extract_doc_citation_spans(output_text)
    if citation_spans and doc_evidence:
        chunk_contents = [dc.content for dc in doc_evidence if dc.content]
        if chunk_contents:
            try:
                model = _get_doc_grounding_model()
                chunk_embeddings = model.encode(chunk_contents, convert_to_numpy=True)
                span_texts = [s[0] for s in citation_spans]
                span_embeddings = model.encode(span_texts, convert_to_numpy=True)
                from numpy import dot
                from numpy.linalg import norm as np_norm
                SIMILARITY_THRESHOLD = 0.45
                for i, (snippet, doc_type_hint, span_start, span_end) in enumerate(citation_spans):
                    if _is_heuristic_doc_reference(snippet):
                        continue
                    if _span_has_valid_doc_marker(
                        snippet, valid_indices, output_text, span_start, span_end
                    ):
                        continue
                    scores = [
                        float(dot(span_embeddings[i], ce) / (np_norm(span_embeddings[i]) * np_norm(ce) + 1e-10))
                        for ce in chunk_embeddings
                    ]
                    max_score = max(scores) if scores else 0.0
                    best_idx = int(scores.index(max_score)) + 1 if scores else 0
                    if max_score < SIMILARITY_THRESHOLD:
                        issues.append(
                            f"Ungrounded doc claim: agent references '{doc_type_hint}' type content "
                            f"(similarity={max_score:.2f}, best chunk={best_idx}, "
                            f"threshold={SIMILARITY_THRESHOLD}). "
                            f"Snippet: \"{snippet[:80]}...\""
                        )
            except ImportError:
                # 降级：semantic matching 不可用，跳过 Level 2
                pass

    # ═══ Level 3: pattern-based coarse check (warnings) ═══
    has_doc_pattern = False
    for pat in _DOC_CITATION_PATTERNS_CN + _DOC_CITATION_PATTERNS_EN:
        if re.search(pat, output_text, re.IGNORECASE):
            has_doc_pattern = True
            break

    if has_doc_pattern:
        if not doc_evidence:
            # 升级为 issue：有引用模式但完全无可追溯的 chunk
            issues.append(
                "Ungrounded doc claim: agent output references document evidence "
                "(e.g. annual report, earnings call, filing) but Evidence Packet "
                "contains no document_evidence chunks"
            )
        else:
            # warnings 级别：有引用模式且有 chunk，但没有被 Level 1/2 捕获时做兜底
            matched_types = set()
            for dc in doc_evidence:
                dt = (dc.doc_type or "") if hasattr(dc, 'doc_type') else ""
                if dt:
                    matched_types.add(dt)
            if not issues:  # Level 1/2 都没触发 issue
                warnings.append(
                    f"Doc grounding (coarse): output contains document citation patterns; "
                    f"available doc types: {sorted(matched_types)}. "
                    f"No issues detected at Level 1/2."
                )

    return issues, warnings


def _find_ungrounded_claims_v2(ep: EvidencePacket, output_text: str) -> tuple[list[str], list[str]]:
    """
    规则型 grounding 检查 (v2)。返回 (issues, warnings)。
    - issues: 报告提到某类字段但 packet 中没有该字段 → 影响 is_valid
    - warnings: 字段存在但数值未在报告中被逐字引用 → 仅提示，不阻止输出
    """
    issues: list[str] = []
    warnings: list[str] = []
    text = _strip_machine_json_blocks(output_text or "")
    lines = text.split("\n")
    _negation = re.compile(
        r"缺少|缺乏|缺失|无法|不提供|禁止|不允许|不得|没有|不可用|不可获取|不可计算|无意义|"
        r"missing|not available|no data|unavailable|do not|does not|not provide|n/?a\b",
        re.IGNORECASE,
    )
    clean_lines = [ln for ln in lines if not _negation.search(ln)]
    lower = "\n".join(clean_lines).lower()
    available_fields = {f.field for f in ep.facts}

    # Level 1: field-level check → issues (影响 is_valid)
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

    # Level 2: value-level check → warnings (不影响 is_valid)
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
            warnings.append(
                f"Value-check: '{field_name}' mentioned in report but specific numeric value not found — fact value exists, agent may be paraphrasing"
            )

    return issues, warnings


def _hard_rule_guard(packet: dict | None, final_output_text: str, symbol: str = "", all_output_text: str = "") -> dict:
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
            "checks": {
                "data_coverage": {"passed": False, "detail": "evidence packet 缺失"},
                "symbol_match": {"passed": False, "detail": "无法校验标的匹配"},
                "unsupported_claim": {"passed": True, "detail": ""},
            },
            "risk_warnings": [],
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
            "checks": {
                "data_coverage": {"passed": False, "detail": "evidence packet 损坏"},
                "symbol_match": {"passed": False, "detail": "无法校验标的匹配"},
                "unsupported_claim": {"passed": True, "detail": ""},
            },
            "risk_warnings": [],
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
            "checks": {
                "data_coverage": {"passed": True, "detail": ""},
                "symbol_match": {"passed": False, "detail": symbol_issues[0]},
                "unsupported_claim": {"passed": True, "detail": ""},
            },
            "risk_warnings": [],
        }

    if guard_result.allowed_output_level == OutputLevel.INSUFFICIENT_EVIDENCE:
        return {
            "is_valid": False,
            "confidence_score": int(ep.evidence_score),
            "issues": [f"INSUFFICIENT_EVIDENCE: {guard_result.reason}"],
            "corrections": ["cannot produce analysis with current data"],
            "sources": [f.source for f in ep.facts],
            "final_reasoning": guard_result.reason,
            "checks": {
                "data_coverage": {"passed": False, "detail": guard_result.reason},
                "symbol_match": {"passed": True, "detail": ""},
                "unsupported_claim": {"passed": True, "detail": ""},
            },
            "risk_warnings": ["INSUFFICIENT_EVIDENCE: 数据不足以支持风险评估"],
        }

    issues = []

    if guard_result.allowed_output_level == OutputLevel.FULL_ANALYSIS:
        pass
    elif guard_result.allowed_output_level in (OutputLevel.DATA_SUMMARY_ONLY, OutputLevel.LIMITED_ANALYSIS, OutputLevel.LIMITED_ANALYSIS_PARTIAL):
        prohibited_keywords = [
            "建议买入", "建议卖出", "强烈推荐", "目标价",
            "buy recommendation", "sell recommendation", "strong buy",
            "target price", "price target",
        ]
        output_lower = _strip_machine_json_blocks(final_output_text).lower()
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
        search_text = all_output_text or final_output_text
        if '"data_quality"' not in search_text:
            issues.append(
                "LIMITED_ANALYSIS_PARTIAL: Strategy/Risk output missing 'data_quality' field"
            )

    # grounding 检查分离：
    # - field-level issues (report 用到了 facts 里不存在的字段) → 影响 is_valid
    # - value-level warnings (字段存在但数值没被逐字引用) → 不影响 is_valid，仅作提示
    grounding_issues, grounding_warnings = _find_ungrounded_claims_v2(ep, final_output_text)

    # 文档 grounding 检查（非结构化 RAG）— 返回 (issues, warnings)
    doc_grounding_issues, doc_grounding_warnings = _find_ungrounded_doc_claims(
        final_output_text, ep
    )

    if guard_result.allowed_output_level != OutputLevel.FULL_ANALYSIS:
        issues.extend(grounding_issues)
        issues.extend(doc_grounding_issues)
    else:
        # FULL_ANALYSIS 下文档 grounding 不阻断，但 L1/L2 issues 降级并入 warnings
        # 以保留审计链（否则 FULL 模式下 doc grounding 问题会被静默丢弃）
        if doc_grounding_issues:
            grounding_warnings = list(grounding_warnings) + [
                f"[FULL_ANALYSIS-downgraded] {issue}" for issue in doc_grounding_issues
            ]

    # FULL_ANALYSIS 或非 FULL 下 L3 warnings 始终记录
    if doc_grounding_warnings:
        grounding_warnings = list(grounding_warnings) + doc_grounding_warnings

    is_valid = len(issues) == 0

    confidence = int(ep.evidence_score)
    if guard_result.allowed_output_level == OutputLevel.LIMITED_ANALYSIS_PARTIAL:
        confidence = max(0, confidence - 5)

    # 结构化检查项
    checks = {
        "data_coverage": {"passed": True, "detail": ""},
        "symbol_match": {"passed": True, "detail": ""},
        "unsupported_claim": {"passed": True, "detail": ""},
    }
    # data_coverage 不通过：分数不够 或 output_level 受限
    if guard_result.allowed_output_level != OutputLevel.FULL_ANALYSIS:
        checks["data_coverage"] = {
            "passed": False,
            "detail": f"Evidence score {ep.evidence_score}/100 → output level {guard_result.allowed_output_level.value}",
        }
    if ep.evidence_score < 70:
        checks["data_coverage"] = {
            "passed": False,
            "detail": f"Evidence score {ep.evidence_score}/100 (< 70)，数据覆盖不足",
        }
    # unsupported_claim 不通过：issue 中包含 UNVERIFIED_CLAIM
    unverified = [i for i in issues if "UNVERIFIED_CLAIM" in i.upper() or "UNSUPPORTED" in i.upper()]
    if unverified:
        checks["unsupported_claim"] = {
            "passed": False,
            "detail": "; ".join(unverified),
        }

    level = guard_result.allowed_output_level.value
    if is_valid and level != OutputLevel.FULL_ANALYSIS.value:
        reasoning = (
            f"Guard passed at {level} level. "
            f"Output constraints enforced; data note: {guard_result.reason}"
        )
    else:
        reasoning = guard_result.reason

    # 从 issues 中提取风险相关条目
    risk_keywords = ["risk", "volatil", "drawdown", "警告", "风险", "波动", "回撤", "止损", "仓位", "output level"]
    risk_warnings = [
        i for i in issues
        if any(kw in i.lower() for kw in risk_keywords)
    ]

    return {
        "is_valid": is_valid,
        "confidence_score": confidence,
        "issues": issues,
        "corrections": issues if not is_valid else [],
        "sources": [f.source for f in ep.facts],
        "final_reasoning": reasoning,
        "output_level": level,
        "checks": checks,
        "risk_warnings": risk_warnings,
        "grounding_warnings": grounding_warnings,
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
    all_output_text = ""
    for m in reversed(messages):
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if content and not isinstance(content, list):
            text = str(content)
            all_output_text = text + "\n" + all_output_text
            if not final_output_text:
                final_output_text = text

    guard_result = _hard_rule_guard(
        evidence_packet, final_output_text,
        symbol=stock_symbol, all_output_text=all_output_text,
    )

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
