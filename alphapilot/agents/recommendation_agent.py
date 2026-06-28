import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from config.llm import get_llm
from graph.lang_labels import get_label

_LANG_INSTRUCTION: dict[str, str] = {
    "zh": "你必须全程使用简体中文回复。",
    "yue": "你必須全程使用粵語 (Cantonese) 回覆。所有分析內容、指標解讀、結論、建議都必須用粵語輸出。",
}


def _lang_instruction(language: str) -> str:
    return _LANG_INSTRUCTION.get(language, "")


_SUMMARY_AGENT_NAMES = (
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "bull_researcher",
    "bear_researcher",
    "strategy_expert",
    "risk_expert",
    "portfolio_agent",
    "backtesting_agent",
)


def _safe_content(message) -> str:
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content or "")


def _message_name(message) -> str:
    if isinstance(message, dict):
        return str(message.get("name") or message.get("additional_kwargs", {}).get("name") or "")
    return str(getattr(message, "name", "") or "")


def _clip(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _render_fact_summary(ep: dict) -> str:
    facts = ep.get("facts", []) if isinstance(ep, dict) else []
    priority = {
        "current_price",
        "price_change_pct",
        "market_cap",
        "pe_ratio",
        "pb_ratio",
        "rsi_14",
        "macd",
        "volatility_20d_annualized",
        "avg_volume_20d",
        "revenue",
        "eps",
    }
    ordered = sorted(
        facts,
        key=lambda f: 0 if isinstance(f, dict) and f.get("field") in priority else 1,
    )
    lines = [
        f"Evidence Score: {ep.get('evidence_score', 0)}/100",
        f"Output Level: {ep.get('allowed_output_level', 'unknown')}",
        "Verified facts:",
    ]
    for fact in ordered[:48]:
        if not isinstance(fact, dict):
            continue
        lines.append(
            f"- {fact.get('field')}: {fact.get('value')} {fact.get('unit', '')} "
            f"(source={fact.get('source', 'N/A')}, as_of={fact.get('as_of_date', 'N/A')})"
        )
    return "\n".join(lines)


def _render_document_evidence(ep: dict) -> str:
    """渲染 Document Evidence 为非结构化文本块，供推荐 Agent 使用。"""
    doc_evidence = ep.get("document_evidence", []) if isinstance(ep, dict) else []
    if not doc_evidence:
        return ""

    lines = ["### Document Evidence (non-structured, from reports & filings)"]
    lines.append("- Cite chunks as [doc:N] (N = chunk number below). Do NOT invent content not shown here.")
    for i, dc in enumerate(doc_evidence):
        if not isinstance(dc, dict):
            continue
        content = str(dc.get("content", ""))
        if not content.strip():
            continue
        source = dc.get("source", "unknown")
        doc_type = dc.get("doc_type", "")
        section = dc.get("section", "")
        publish_date = dc.get("publish_date", "")
        page = dc.get("page", "")
        report_period = dc.get("report_period", "")

        header_parts = [f"[source: {source}"]
        if doc_type:
            header_parts.append(f"type: {doc_type}")
        if section:
            header_parts.append(f"section: {section}")
        if page:
            header_parts.append(f"page: {page}")
        if publish_date:
            header_parts.append(f"date: {publish_date}")
        if report_period:
            header_parts.append(f"period: {report_period}")
        header_parts.append("]")

        lines.append(f"#### [doc:{i + 1}] {' '.join(header_parts)}")
        # 截断过长内容
        if len(content) > 2000:
            content = content[:2000] + "...[truncated]"
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


def _collect_agent_summaries(messages) -> str:
    latest: dict[str, str] = {}
    for message in messages or []:
        name = _message_name(message)
        if name in _SUMMARY_AGENT_NAMES:
            latest[name] = _clip(_safe_content(message), 3000)

    if not latest:
        fallback_chunks = []
        for message in reversed(messages or []):
            role = message.get("role", "") if isinstance(message, dict) else getattr(message, "type", "")
            if role in {"user", "human", "system"}:
                continue
            content = _clip(_safe_content(message), 1500)
            if content:
                fallback_chunks.append(content)
            if len(fallback_chunks) >= 6:
                break
        if fallback_chunks:
            return "\n\n".join(
                f"### recent_agent_output_{i + 1}\n{content}"
                for i, content in enumerate(reversed(fallback_chunks))
            )
        return "No prior agent outputs were found in the workflow messages."

    chunks = []
    for name in _SUMMARY_AGENT_NAMES:
        content = latest.get(name)
        if content:
            chunks.append(f"### {name}\n{content}")
    return "\n\n".join(chunks)


def _fallback_json(reason: str) -> str:
    return json.dumps({
        "valuation_low": None,
        "valuation_mid": None,
        "valuation_high": None,
        "upside_pct": None,
        "downside_pct": None,
        "consensus_summary": reason,
    }, ensure_ascii=False)


def _invoke_recommendation_model(system_prompt: str, compact_context: str) -> str:
    response = get_llm("recommendation").invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=compact_context),
    ])
    return _safe_content(response)


def recommendation_agent(state):
    """
    Recommendation Agent - v4 证据感知版（已加强 Document Evidence 使用）
    """
    user_profile = state.get("user_profile", {})
    risk_preference = user_profile.get("risk_preference", "medium")
    horizon = user_profile.get("horizon", "medium")
    language = state.get("language", "")

    ep = state.get("evidence_packet", {})
    ep_score = int(ep.get("evidence_score", 0)) if isinstance(ep, dict) else (int(ep.evidence_score) if ep else 0)
    output_level = ep.get("allowed_output_level", "limited_analysis") if ep else "limited_analysis"

    if output_level not in ("full_analysis", "limited_analysis_partial"):
        reason = (
            f"当前分析等级为 {output_level}，尚未达到 full_analysis 或 limited_analysis_partial，暂不生成个性化推荐。"
            if language in ("zh", "yue", "")
            else f'Output level is "{output_level}" (not full_analysis or limited_analysis_partial); personalized recommendation is withheld.'
        )
        fallback_json = _fallback_json(reason)
        content = (
            f"{get_label('reco_na_title', language)}\n"
            f"- {reason}\n"
            f"- {get_label('reco_na_action', language)}\n\n"
            "```json\n"
            f"{fallback_json}\n"
            "```"
        )
        return {"messages": [AIMessage(content=content, name="recommendation_agent")]}

    elif ep_score < 70:
        fallback_json = _fallback_json(f"Evidence score {ep_score}/100 too low for reliable recommendation.")
        content = (
            f"{get_label('reco_na_title', language)}\n"
            f"- {get_label('reco_na_reason', language).format(score=ep_score, level=output_level)}\n"
            f"- {get_label('reco_na_action', language)}\n\n"
            "```json\n"
            f"{fallback_json}\n"
            "```"
        )
        return {"messages": [AIMessage(content=content, name="recommendation_agent")]}

    else:
        partial_constraints = ""
        if output_level == "limited_analysis_partial":
            partial_constraints = """
LIMITED_ANALYSIS_PARTIAL constraints:
- Do NOT use strong actionable phrases: 建议买入, 建议卖出, 强烈推荐, 目标价, strong buy, strong sell, price target.
- Use cautious wording: 可考虑观望, 谨慎持有, 风险较高需控制仓位, etc.
- Document Evidence claims must include [doc:N] and match chunk content; omit doc section if chunks are insufficient.
"""

        system_prompt = f"""
You are Recommendation Agent - AlphaPilot personalized investment recommendation expert.

User Profile:
- Risk Preference: {risk_preference} (low / medium / high)
- Investment Horizon: {horizon} (short / medium / long)

### CRITICAL: Output Style — Executive Synthesis (NOT per-agent narration)
- Do NOT create a section titled 逐智能体详细拆解 or list each agent one-by-one.
- Do NOT repeat raw agent outputs verbatim. Synthesize across agents.
- Lead with 3–5 executive-level key findings that span multiple dimensions.
- The report must be concise and actionable — target ~60% fewer words than a full agent-by-agent breakdown.

### Document Evidence Usage
You have access to the "### Document Evidence" section below.
When it is non-empty, you MUST:
- Include a dedicated "## 文档证据" (Document Evidence) subsection.
- Cite at least 2 distinct [doc:N] markers in that subsection.
- Use document evidence to add qualitative depth (management outlook, risk disclosures, strategic positioning).
Only paraphrase facts explicitly present in the Document Evidence text — do NOT invent filings or metrics.
Prioritize official company documents (annual reports, earnings call transcripts) over third-party research reports.

### Core Responsibilities
- Synthesize analysis across all agents that produced output
- Incorporate qualitative insights from Document Evidence (especially in Fundamental, Risk, and Strategy sections)
- Provide personalized, actionable recommendations aligned with the user profile

### STRICT PROHIBITIONS
- Do NOT reference any agent whose output is NOT present in the conversation.
- Do NOT fabricate backtesting metrics if Backtesting output is "NOT AVAILABLE".
- Do NOT put target prices, price targets, 目标价, or expected-return percentages in the human-readable text.
- DO NOT use vague approximators: 约, 左右, 大概, approximately, roughly, about.
- Every numeric claim MUST copy the exact value from Verified Facts.
{partial_constraints}
- {_lang_instruction(language)}

### Required Output Structure (5 sections)

## 一、核心发现 (3-5 Key Findings)
- Synthesize the most important cross-dimensional signals into 3–5 concise bullet points.
- Each finding should integrate insights from multiple agents, not repeat a single agent.

## 二、多维度交叉验证
- Identify strongly consistent signals across agents.
- Surface contradictory views and explain your weighted judgment. **Cite Document Evidence [doc:N] where relevant.**

## 三、整体评估
- One-sentence summary + detailed analysis across valuation, trend, and quality dimensions.
- **Assess whether Document Evidence supports or challenges the quantitative conclusions.**

## 四、个性化投资建议
- Suggested position size (% of total assets) with rationale linked to risk preference and horizon.
- **Explain how qualitative Document Evidence (management outlook, risk disclosures) influenced your recommendation.**

## 五、风险警告
- List 3–5 specific risks, each linked to agent evidence.
- **If Document Evidence contains risk disclosures (e.g., annual report Risk Factors), cite them with [doc:N].**

## 六、行动计划
- Short-term (1-4 weeks) / Medium-term (1-3 months) / Long-term (6+ months) — with triggers, steps, and targets.

After your plain-text response, append ONE machine-readable JSON block (inside ```json ... ```):

```json
{{
  "valuation_low": <number or null>,
  "valuation_mid": <number or null>,
  "valuation_high": <number or null>,
  "upside_pct": <number or null>,
  "downside_pct": <number or null>,
  "consensus_summary": "<one-sentence multi-agent synthesis>"
}}
```
valuation_low/mid/high: scenario valuation range based only on verified current_price. Set all to null if insufficient.
upside_pct: (valuation_mid - current_price) / current_price * 100. Null if valuation_mid is null.
downside_pct: (current_price - valuation_low) / current_price * 100. Null if valuation_low is null.
consensus_summary: one-sentence synthesis of Market/Fundamental/News/Bull/Bear consensus.

You have NO tools. Respond with plain text first, then the JSON block.
Style: Professional, cautious, data-driven. Concise executive format.
"""

        compact_context = (
            "Use only this compact context. Do not infer from omitted text.\n\n"
            "## Evidence Packet Summary\n"
            f"{_render_fact_summary(ep if isinstance(ep, dict) else {})}\n\n"
            f"{_render_document_evidence(ep if isinstance(ep, dict) else {})}\n\n"
            "## Prior Agent Outputs\n"
            f"{_collect_agent_summaries(state.get('messages', []))}"
        )
        content = _invoke_recommendation_model(system_prompt, compact_context)
        return {"messages": [AIMessage(content=content, name="recommendation_agent")]}
