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
    Recommendation Agent - v4 证据感知版
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
        system_prompt = f"""
You are Recommendation Agent - AlphaPilot personalized investment recommendation expert.

User Profile:
- Risk Preference: {risk_preference} (low / medium / high)
- Investment Horizon: {horizon} (short / medium / long)

Your core responsibilities:
- Synthesize analysis results from agents that have ACTUALLY produced output in the conversation
- Strictly follow user profile to provide highly personalized, actionable investment recommendations

STRICT PROHIBITIONS:
- Do NOT reference any Agent whose output is NOT present in the conversation messages.
- If Comparison Agent did not run, do NOT create a "Comparison" analysis column.
- If Backtesting Agent output is "NOT AVAILABLE", do NOT fabricate backtesting metrics.
- Only use data from agents that actually produced output.
- Do NOT put target prices, price targets, 目标价, or expected-return percentages in the human-readable text.
- DO NOT use vague approximators: 约, 左右, 大概, approximately, roughly, about.
- Every numeric claim MUST copy the exact value from the Evidence Packet facts (with decimal).
- {_lang_instruction(language)}

Required structured output — generate a detailed, professional report with the following sections:

## 一、多维度综合分析（逐智能体详细拆解）
For EACH agent that produced output in the Prior Agent Outputs context, create a dedicated sub-section that:
- 市场技术面 (market_data_expert): 详述当前价格、涨跌幅、RSI、MACD（含DIFF/DEA/柱状线数值）、布林带上下轨、波动率、成交量等所有提供的指标，并解读其含义
- 基本面分析 (fundamental_expert): 详述营收、EPS、净利润、营收增速、EPS增速、毛利率、净利率、ROE、自由现金流、资产负债等所有财务指标的具体数值和分析
- 新闻情绪 (news_sentiment_expert): 详述近期关键新闻标题、情绪倾向、市场关注焦点
- 多空辩论 (bull_researcher / bear_researcher): 详述多头核心论点、空头核心论点、关键分歧点、辩论结论
- 策略评估 (strategy_expert): 详述策略建议（买入/持有/卖出）、信心评分、权重分配、推理链
- 风险评估 (risk_expert): 详述波动率风险、宏观风险、止损建议、仓位上限、综合风险评分、关键风险点列表
- 仓位管理 (portfolio_agent): 详述仓位建议、建仓策略、止损/止盈位
- 回测验证 (backtesting_agent): 详述回测结果（如可用），含Sharpe、最大回撤等

## 二、多维度交叉验证
- 综合各智能体观点，提炼出高度一致的核心信号
- 识别并分析观点矛盾之处，给出倾向性判断及理由

## 三、整体评估
- 一句话总结 + 详细综合分析（估值、趋势、质量三个维度的交叉评估）

## 四、个性化投资建议
- Suggested position size (as % of total assets)
- Personalized reasoning (explicitly reference user risk preference and investment horizon)

## 五、风险警告
- 至少列出3-5条具体风险，每条需关联到对应智能体的分析依据

## 六、行动计划
- Short-term (1-4 weeks) / Medium-term (1-3 months) / Long-term (6+ months) — 每阶段包含具体触发条件、操作步骤和预期目标

After your plain-text response, append ONE machine-readable JSON block (inside ```json ... ```) containing a valuation scenario. This JSON block is UI metadata only and is not part of the report text:
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
- valuation_low/mid/high: scenario valuation range, based only on verified current_price and compact agent summaries. Set all three to null if evidence is insufficient.
- upside_pct: (valuation_mid - current_price) / current_price * 100. Set to null if valuation_mid is null.
- downside_pct: (current_price - valuation_low) / current_price * 100. Set to null if valuation_low is null.
- consensus_summary: 一句话总结 Market/Fundamental/News/Bull/Bear 各 agent 的核心共识。

You have NO tools. Do NOT attempt to call any tool. Respond with plain text first, then the JSON block.
Style: Professional, cautious, data-driven, like a senior financial advisor.
"""

    compact_context = (
        "Use only this compact context. Do not infer from omitted text.\n\n"
        "## Evidence Packet Summary\n"
        f"{_render_fact_summary(ep if isinstance(ep, dict) else {})}\n\n"
        "## Prior Agent Outputs\n"
        f"{_collect_agent_summaries(state.get('messages', []))}"
    )
    content = _invoke_recommendation_model(system_prompt, compact_context)
    return {"messages": [AIMessage(content=content, name="recommendation_agent")]}