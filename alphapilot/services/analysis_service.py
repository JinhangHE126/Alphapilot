import json
import re
from typing import Any, Generator

from graph.workflow import app as langgraph_app
from graph.user_profile import load_user_profile

# Agents that output meaningful analysis (exclude infra / orchestrator nodes)
_CORE_CONCLUSION_AGENTS = {
    "market_data_expert",
    "fundamental_expert",
    "news_sentiment_expert",
    "strategy_expert",
    "risk_expert",
    "guard_agent",
    "recommendation_agent",
    "portfolio_agent",
    "backtesting_agent",
    "debate_stage",
    "bull_researcher",
    "bear_researcher",
}

# Sentiment label → English key for LLM extraction prompt
_SENTIMENT_OPTIONS = ["positive", "negative", "neutral"]


AGENT_LABELS: dict[str, dict[str, str]] = {
    "evidence_packet_builder": {"label": "Evidence Builder", "icon": "\U0001f4e6"},
    "orchestrator": {"label": "Orchestrator", "icon": "\U0001f9e0"},
    "market_data_expert": {"label": "Market", "icon": "\U0001f4c8"},
    "fundamental_expert": {"label": "Fundamental", "icon": "\U0001f4ca"},
    "news_expert": {"label": "News", "icon": "\U0001f4f0"},
    "news_sentiment_expert": {"label": "News & Sentiment", "icon": "\U0001f4f0"},
    "risk_expert": {"label": "Risk", "icon": "\u26a0\ufe0f"},
    "strategy_expert": {"label": "Strategy", "icon": "\U0001f3af"},
    "portfolio_agent": {"label": "Portfolio", "icon": "\U0001f4bc"},
    "recommendation_agent": {"label": "Recommendation", "icon": "\u2b50"},
    "comparison_agent": {"label": "Comparison", "icon": "\U0001f500"},
    "backtesting_agent": {"label": "Backtest", "icon": "\U0001f4c9"},
    "alert_agent": {"label": "Alert", "icon": "\U0001f514"},
    "portfolio_optimization_agent": {"label": "Portfolio Optimization", "icon": "\U0001f4a0"},
    "supervisor": {"label": "Supervisor", "icon": "\U0001f9e0"},
    "guard_agent": {"label": "Guard", "icon": "\U0001f6e1\ufe0f"},
    "debate_stage": {"label": "Debate", "icon": "\u2694\ufe0f"},
    "bull_researcher": {"label": "Bull Researcher", "icon": "\U0001f4c8"},
    "bear_researcher": {"label": "Bear Researcher", "icon": "\U0001f4c9"},
}

REPORT_EXCLUDE_NODES = frozenset({
    "evidence_packet_builder",
    "orchestrator",
    "guard_agent",
    "guard",
})


def _safe_text(message_obj: Any) -> str:
    if hasattr(message_obj, "content"):
        raw = message_obj.content
        if isinstance(raw, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in raw
            )
        return str(raw)
    if isinstance(message_obj, dict):
        content = message_obj.get("content", "")
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
    return str(message_obj)


def _format_agent_content(raw: str) -> str:
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return raw

        # 辩论 JSON (bull/bear researcher): 有 stance_strength + claims → Markdown
        if "stance_strength" in obj and "claims" in obj:
            return _format_debate_markdown(raw)

        lines = []
        for k, v in obj.items():
            label = k.replace("_", " ").title()
            if isinstance(v, (int, float)):
                lines.append(f"- **{label}**: {v}")
            elif isinstance(v, str) and v:
                lines.append(f"- **{label}**: {v}")
            elif isinstance(v, list):
                # 数组中元素是 dict 时逐条渲染，避免 str(dict) 原样 dump
                if all(isinstance(i, dict) for i in v):
                    for idx, item in enumerate(v, 1):
                        lines.append(f"  **{label} #{idx}**")
                        for ik, iv in item.items():
                            ikey = ik.replace("_", " ").title()
                            if isinstance(iv, list):
                                lines.append(f"    - {ikey}: {', '.join(str(s) for s in iv)}")
                            else:
                                lines.append(f"    - {ikey}: {iv}")
                else:
                    lines.append(f"- **{label}**: {', '.join(str(i) for i in v)}")
            else:
                lines.append(f"- **{label}**: {v}")
        return "\n".join(lines)
    except (json.JSONDecodeError, ValueError):
        return raw


def _extract_json_block(text: str) -> dict | None:
    """Extract the last JSON code block or raw JSON object from an agent's output text."""
    if not text:
        return None
    # Try fenced JSON blocks first, preferring the last metadata block.
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    for block in reversed(blocks):
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    # Try raw JSON object (find outermost braces on their own)
    start = text.rfind("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1].strip())
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _strip_json_blocks(text: str) -> str:
    """Remove machine-readable JSON blocks before showing agent text in the UI/report."""
    if not text:
        return ""
    without_blocks = re.sub(r"```(?:json)?\s*[\s\S]*?\s*```", "", text).strip()
    without_blocks = re.sub(r"\n?\s*\{[\s\S]*\}\s*$", "", without_blocks).strip()
    if without_blocks.startswith("{") and without_blocks.endswith("}"):
        return ""
    return without_blocks


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_risk_level_payload(payload: dict) -> dict | None:
    """Normalize risk agent JSON into a stable SSE payload."""
    if not isinstance(payload, dict):
        return None

    overall = payload.get("overall_risk_score")
    if overall is None:
        overall = payload.get("risk_score")
    if overall is None:
        return None

    try:
        score = max(0, min(100, int(round(float(overall)))))
    except (TypeError, ValueError):
        return None

    if score == 0 and str(payload.get("volatility_risk", "")).upper() == "N/A":
        return None

    key_risks = payload.get("key_risks", [])
    if not isinstance(key_risks, list):
        key_risks = []

    return {
        "overall_risk_score": score,
        "volatility_risk": str(payload.get("volatility_risk", "")).strip() or None,
        "macro_risk": str(payload.get("macro_risk", "")).strip() or None,
        "stop_loss_suggestion": payload.get("stop_loss_suggestion"),
        "position_suggestion": str(payload.get("position_suggestion", "")).strip() or None,
        "risk_reasoning": str(payload.get("risk_reasoning", "")).strip() or None,
        "key_risks": [str(r).strip() for r in key_risks if str(r).strip()],
    }


def _extract_risk_level(update: dict) -> dict | None:
    """Parse risk_expert output; prefer raw JSON over markdown conversion."""
    messages = update.get("messages")
    if not messages:
        return None
    text = _safe_text(messages[-1]).strip()
    if not text:
        return None

    if text.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                normalized = _normalize_risk_level_payload(payload)
                if normalized:
                    return normalized
        except (json.JSONDecodeError, ValueError):
            pass

    payload = _extract_json_block(text)
    if isinstance(payload, dict):
        return _normalize_risk_level_payload(payload)
    return None


def _format_risk_markdown(raw_json: str) -> str:
    """Convert risk agent JSON into a well-structured Markdown report."""
    import json as _json
    try:
        obj = _json.loads(raw_json)
    except (_json.JSONDecodeError, ValueError):
        return raw_json

    overall = obj.get("overall_risk_score", obj.get("overall_risk", ""))
    vol = obj.get("volatility_risk", "")
    macro = obj.get("macro_risk", "")
    stop = obj.get("stop_loss_suggestion", "")
    position = obj.get("position_suggestion", "")
    reasoning = obj.get("risk_reasoning", "")
    risks = obj.get("key_risks", [])

    # risk level badge
    if isinstance(overall, (int, float)):
        if overall >= 80:
            level = ("🔴", "极高")
        elif overall >= 60:
            level = ("🟠", "较高")
        elif overall >= 40:
            level = ("🟡", "中等")
        else:
            level = ("🟢", "较低")
        score_str = f"{overall}/100"
    else:
        level = ("⚪", "—")
        score_str = str(overall) if overall else "—"

    lines = [
        "---",
        "## 风险评估",
        "",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| **综合风险评分** | {level[0]} **{level[1]} ({score_str})** |",
    ]

    if isinstance(vol, (int, float)):
        lines.append(f"| **波动率风险** | **{vol}/100** |")
    if isinstance(macro, (int, float)):
        lines.append(f"| **宏观风险** | **{macro}/100** |")

    lines.append("")

    if stop:
        lines.append("### 止损建议")
        lines.append("")
        lines.append(stop.strip())
        lines.append("")

    if position:
        lines.append("### 仓位建议")
        lines.append("")
        lines.append(position.strip())
        lines.append("")

    if reasoning:
        lines.append("### 风险分析")
        lines.append("")
        lines.append(reasoning.strip())
        lines.append("")

    if risks:
        lines.append("### 关键风险点")
        lines.append("")
        for i, r in enumerate(risks, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _extract_risk_raw_content(update: dict) -> str:
    """Format risk agent JSON as Markdown for frontend display."""
    messages = update.get("messages")
    if not messages:
        return _extract_text(update)
    text = _safe_text(messages[-1]).strip()
    if text.startswith("{"):
        return _format_risk_markdown(text)
    return _extract_text(update)


def _coerce_valuation_scenario(raw: dict | None) -> dict | None:
    """Normalize valuation JSON from Recommendation Agent into a stable SSE payload."""
    if not isinstance(raw, dict):
        return None

    low = _to_float_or_none(raw.get("valuation_low", raw.get("target_price_low")))
    mid = _to_float_or_none(raw.get("valuation_mid", raw.get("target_price_mid")))
    high = _to_float_or_none(raw.get("valuation_high", raw.get("target_price_high")))
    if low is None and mid is None and high is None:
        return None

    return {
        "target_price_low": low,
        "target_price_mid": mid,
        "target_price_high": high,
        "valuation_low": low,
        "valuation_mid": mid,
        "valuation_high": high,
        "upside_pct": _to_float_or_none(raw.get("upside_pct")),
        "downside_pct": _to_float_or_none(raw.get("downside_pct")),
        "consensus_summary": str(raw.get("consensus_summary", "")).strip() or None,
        "source": "recommendation_agent_valuation_scenario",
    }


# ── Core Conclusion Extractor ──────────────────────────────────────────────
# 每个分析类智能体完成输出后，用轻量 LLM 提炼 1-2 句核心结论 + 情绪标签。
# 通过 agent_core_conclusion SSE 事件推送到前端。
# ────────────────────────────────────────────────────────────────────────────

_CORE_CONCLUSION_PROMPT = (
    "You are a financial analysis summarizer. "
    "Given an agent's analysis output, extract a 1-2 sentence core conclusion "
    "and classify the overall sentiment.\n\n"
    "Agent output:\n{content}\n\n"
    "Return ONLY a JSON object (no markdown, no commentary):\n"
    '{{"core_conclusion": "1-2 sentence summary in the SAME LANGUAGE as the input", '
    '"conclusion_sentiment": "positive"|"negative"|"neutral", '
    '"confidence_score": 0-100}}\n\n'
    "Rules:\n"
    "- core_conclusion: 1-2 sentences capturing the key judgment. "
    "Keep the same language as the input text.\n"
    "- conclusion_sentiment: positive (bullish/favorable/good), "
    "negative (bearish/unfavorable/risky), or neutral (balanced/uncertain).\n"
    "- confidence_score: how confident the agent seems in its conclusion (0-100)."
)


def _md_table_value(md: str, key: str) -> str | None:
    """从 Markdown 表格中提取 | **key** | value |."""
    m = re.search(rf"\|\s*\*\*{re.escape(key)}\*\*\s*\|\s*(.+?)\s*\|", md)
    if not m:
        return None
    # 去掉内嵌 ** 和 emoji
    return re.sub(r"\*\*|\u2600-\u27BF|\U0001F300-\U0001FAFF", "", m.group(1)).strip()


def _md_section_body(md: str, heading: str) -> str | None:
    """从中文 Markdown 标题后提取段落内容."""
    m = re.search(rf"###\s+{re.escape(heading)}\s*\n+([\s\S]*?)(?=\n###\s|\n---|$)", md)
    return m.group(1).strip() if m else None


def _cc_from_strategy_md(content: str) -> dict | None:
    """从策略 Markdown 表格提取核心结论."""
    rec_label = _md_table_value(content, "最终建议")
    score_raw = _md_table_value(content, "置信度评分")
    reasoning = _md_section_body(content, "决策推理") or ""

    if not rec_label:
        return None

    sentiment_map = {"买入": "positive", "卖出": "negative", "持有": "neutral", "暂无法评估": "neutral"}
    sentiment = sentiment_map.get(rec_label.strip(), "neutral")

    conf = 0
    if score_raw:
        conf_match = re.search(r"(\d+)", score_raw)
        if conf_match:
            conf = int(conf_match.group(1))

    # 用推理文本的前 80 字作为核心结论，或直接用建议 + 置信度
    if reasoning and len(reasoning) > 20:
        conclusion = reasoning[:90].rsplit("。", 1)[0] + "。"
    else:
        conclusion = f"策略建议：{rec_label}，置信度 {conf}/100"

    return {
        "core_conclusion": conclusion,
        "conclusion_sentiment": sentiment,
        "confidence_score": conf,
    }


def _cc_from_risk_md(content: str) -> dict | None:
    """从风险 Markdown 表格提取核心结论."""
    risk_label = _md_table_value(content, "综合风险评分")
    reasoning = _md_section_body(content, "风险分析") or ""

    if not risk_label:
        return None

    conf_match = re.search(r"(\d+)", risk_label)
    conf = int(conf_match.group(1)) if conf_match else 0

    if conf >= 80:
        sentiment = "negative"
    elif conf >= 50:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    if reasoning and len(reasoning) > 20:
        conclusion = reasoning[:90].rsplit("。", 1)[0] + "。"
    else:
        conclusion = f"综合风险评分 {conf}/100，风险等级较高"

    return {
        "core_conclusion": conclusion,
        "conclusion_sentiment": sentiment,
        "confidence_score": conf,
    }


def _cc_from_debate_json(content: str) -> dict | None:
    """从辩论 JSON 提取核心结论."""
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        # 尝试从文本中提取 JSON
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            return None

    stance = obj.get("stance_strength", 0)
    summary = obj.get("summary", "")

    if not summary:
        return None

    # 从 Markdown summary 中取第一个非标题段落作为结论
    # 跳过 ## 和 ### 标题行
    lines = [l.strip() for l in summary.split("\n") if l.strip() and not l.strip().startswith("#")]
    conclusion = ""
    for line in lines:
        if len(line) > 20 and not line.startswith("*") and not line.startswith("-"):
            conclusion = line[:90]
            if "。" in conclusion:
                conclusion = conclusion.rsplit("。", 1)[0] + "。"
            break

    if not conclusion:
        # 取全部 summary 的前 90 字符
        clean = re.sub(r"#+\s*", "", summary).strip()
        conclusion = clean[:90].rsplit("。", 1)[0] + "。" if "。" in clean[:90] else clean[:90]

    sentiment = "positive" if stance >= 65 else "negative" if stance <= 35 else "neutral"

    return {
        "core_conclusion": conclusion,
        "conclusion_sentiment": sentiment,
        "confidence_score": int(stance),
    }


def _cc_from_guard_text(content: str) -> dict | None:
    """从 Guard 验证文本提取核心结论."""
    valid = "true" in content.lower() or "通过" in content or "valid" in content.lower()

    # 提取置信度
    conf_match = re.search(r"Confidence Score.*?(\d+)", content)
    if not conf_match:
        conf_match = re.search(r"置信度.*?(\d+)", content)
    conf = int(conf_match.group(1)) if conf_match else 0

    issues_match = re.search(r"Issues.*?:(.+?)(?:\n|$)", content)
    issues_text = issues_match.group(1).strip() if issues_match else ""

    if valid and ("none" in issues_text.lower() or "无" in issues_text or not issues_text.strip()):
        sentiment = "positive"
        conclusion = "所有校验项通过，数据来源覆盖度较高，结论可信度良好。"
    elif valid:
        sentiment = "neutral"
        conclusion = f"校验通过但存在 {issues_text.strip()[:60]}，结论可信度受部分影响。"
    else:
        sentiment = "negative"
        conclusion = f"Guard 校验未通过：{issues_text.strip()[:80]}"

    return {
        "core_conclusion": conclusion,
        "conclusion_sentiment": sentiment,
        "confidence_score": conf,
    }


def _extract_core_conclusion(
    content: str,
    agent_name: str,
    language: str = "",
) -> dict | None:
    """Extract core conclusion + sentiment tag from agent output.
    Strategy/risk agents are parsed from their Markdown table;
    debate agents are parsed from JSON; others use LLM extraction."""
    if not content or len(content.strip()) < 60:
        return None
    if agent_name not in _CORE_CONCLUSION_AGENTS:
        return None

    # ── 策略智能体：从 Markdown 表格提取 ──
    if agent_name == "strategy_expert":
        return _cc_from_strategy_md(content)

    # ── 风险智能体：从 Markdown 表格提取 ──
    if agent_name == "risk_expert":
        return _cc_from_risk_md(content)

    # ── 辩论智能体：从 JSON 提取 summary ──
    if agent_name in ("bull_researcher", "bear_researcher", "debate_stage"):
        return _cc_from_debate_json(content)

    # ── Guard 智能体：从文本提取 ──
    if agent_name == "guard_agent":
        return _cc_from_guard_text(content)

    from config.llm import get_llm as _get_llm
    try:
        llm = _get_llm("recommendation")  # 复用 recommendation 的 fast 配置
    except Exception:
        return None

    # 截断超长内容以控制 token
    truncated = content[:2500]

    lang_hint = ""
    if language == "zh":
        lang_hint = "\nThe core_conclusion MUST be in Simplified Chinese (简体中文)."
    elif language == "yue":
        lang_hint = "\nThe core_conclusion MUST be in Cantonese (粤语)."

    prompt = _CORE_CONCLUSION_PROMPT.format(content=truncated) + lang_hint

    try:
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
    except Exception:
        return None

    # 提取 JSON
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not json_match:
        return None

    try:
        obj = json.loads(json_match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None

    conclusion = str(obj.get("core_conclusion", "")).strip()
    sentiment = str(obj.get("conclusion_sentiment", "")).strip().lower()
    confidence = obj.get("confidence_score")

    if not conclusion:
        return None
    if sentiment not in _SENTIMENT_OPTIONS:
        sentiment = "neutral"

    result = {
        "core_conclusion": conclusion,
        "conclusion_sentiment": sentiment,
    }
    if isinstance(confidence, (int, float)):
        result["confidence_score"] = int(confidence)
    return result


def _extract_text(update: dict, agent_name: str = "") -> str:
    if update.get("final_report"):
        return str(update["final_report"])
    messages = update.get("messages")
    if messages and isinstance(messages, list) and len(messages) > 0:
        # 按 agent name 过滤消息，避免跨智能体内容污染
        target_msg = None
        if agent_name:
            for m in reversed(messages):
                msg_name = ""
                if hasattr(m, "name"):
                    msg_name = (getattr(m, "name") or "").strip()
                elif isinstance(m, dict):
                    msg_name = str(m.get("name", "") or m.get("additional_kwargs", {}).get("name", "")).strip()
                if msg_name == agent_name:
                    target_msg = m
                    break
        if target_msg is None:
            target_msg = messages[-1]

        text = _safe_text(target_msg)
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return _format_agent_content(stripped)
        if stripped.startswith("{'role':") or stripped.startswith('{"role":'):
            return _format_agent_content(stripped)
        return text
    return ""


def _format_debate_markdown(raw_json: str) -> str:
    """Convert debate JSON (bull/bear) into a clean Markdown report."""
    import json as _json
    try:
        obj = _json.loads(raw_json)
    except (_json.JSONDecodeError, ValueError):
        return raw_json

    stance = obj.get("stance_strength", 0)
    summary = obj.get("summary", "")
    claims = obj.get("claims", [])

    stance_color = "#22c55e" if stance >= 65 else "#ef4444" if stance <= 35 else "#f59e0b"
    stance_label = "强看多" if stance >= 65 else "强看空" if stance <= 35 else "中性偏空"

    lines = [
        "---",
        f"## 论点强度：{stance_label} ({stance}/100)",
        "",
    ]

    if summary:
        lines.append(summary.strip())
        lines.append("")

    if claims:
        lines.append("### 核心论据")
        lines.append("")
        for i, c in enumerate(claims, 1):
            text = c.get("text", "") if isinstance(c, dict) else str(c)
            conf = c.get("confidence", 0) if isinstance(c, dict) else 0
            srcs = c.get("sources", []) if isinstance(c, dict) else []
            src_str = ", ".join(srcs) if srcs else ""
            lines.append(f"**论据 {i}** (置信度 {conf}%)")
            lines.append(f"{text}")
            if src_str:
                lines.append(f"*数据来源: {src_str}*")
            lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _try_parse_debate_text(text: str) -> dict | None:
    """从 deepseek 非 JSON 输出中提取 debate 结构化数据。
    格式: Stance Strength: N
          Summary: ...
          Claims: {'text': ..., ...}, {...}, ...
    """
    if not text:
        return None
    stance_match = re.search(r"Stance\s*Strength\s*:\s*(\d+)", text, re.IGNORECASE)
    if not stance_match:
        return None
    stance = max(0, min(100, int(stance_match.group(1))))

    summary = ""
    summary_match = re.search(r"Summary\s*:\s*(.+?)(?=\n+\s*Claims?\s*:)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()

    claims_raw = ""
    claims_match = re.search(r"Claims?\s*:\s*(.+)$", text, re.IGNORECASE)
    if claims_match:
        claims_raw = claims_match.group(1).strip()

    claims: list[dict] = []
    if claims_raw:
        depth = 0
        buf = ""
        for ch in claims_raw:
            buf += ch
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and buf.strip():
                    claims.append(buf.strip())
                    buf = ""
        if not claims:
            try:
                claims_list = json.loads(claims_raw.replace("'", '"'))
                if isinstance(claims_list, list):
                    claims = claims_list
            except (json.JSONDecodeError, ValueError):
                pass

    safe_claims: list[dict] = []
    for raw_claim in claims:
        try:
            claim_json = raw_claim.replace("'", '"')
            c = json.loads(claim_json)
            if isinstance(c, dict) and c.get("text"):
                conf = c.get("confidence", 50)
                if not isinstance(conf, (int, float)):
                    conf = 50
                srcs = c.get("sources", [])
                if isinstance(srcs, str):
                    srcs = [srcs]
                fields = c.get("supporting_fields", [])
                if isinstance(fields, str):
                    fields = [fields]
                safe_claims.append({
                    "text": str(c["text"]),
                    "confidence": int(conf),
                    "sources": [str(s) for s in srcs if s] if isinstance(srcs, list) else [],
                    "supporting_fields": [str(f) for f in fields if f] if isinstance(fields, list) else [],
                })
        except (json.JSONDecodeError, TypeError):
            continue

    return {
        "stance_strength": stance,
        "summary": summary,
        "claims": safe_claims,
    }


def _strip_claims_section(text: str) -> str:
    """移除 debate 文本末尾的 Claims: {...} 原始 JSON/Python dict 块。"""
    # 匹配 "Claims:" 后面跟 JSON 或 Python dict 格式内容
    cleaned = re.sub(
        r"\n*\s*Claims?\s*:\s*\{[\s\S]*",
        "",
        text,
    )
    # 也处理多行 Claims 格式（Claims 单独一行，下面跟 JSON）
    cleaned = re.sub(
        r"\n*\s*Claims?\s*\n+\{[\s\S]*",
        "",
        cleaned,
    )
    return cleaned.strip()


def _serialize_debate_side(update: dict, side: str) -> str:
    """Build SSE payload for bull/bear. Returns JSON + formatted Markdown."""
    data_key = f"{side}_debate_data"
    arg_key = f"{side}_argument"

    raw_json = ""

    debate_data = update.get(data_key)
    if isinstance(debate_data, dict):
        claims = debate_data.get("claims")
        if isinstance(claims, list) and claims:
            raw_json = json.dumps(debate_data, ensure_ascii=False)
        summary = debate_data.get("summary")
        if isinstance(summary, str) and summary.strip():
            raw_json = raw_json or json.dumps(debate_data, ensure_ascii=False)

    if not raw_json:
        # 结构化数据不可用时，从 argument 或 message 文本中提取
        text = ""
        argument = update.get(arg_key)
        if isinstance(argument, str) and argument.strip():
            text = argument.strip()
        else:
            messages = update.get("messages")
            if messages and isinstance(messages, list):
                raw_msg = _safe_text(messages[-1]).strip()
                if raw_msg:
                    text = raw_msg
        if not text:
            return ""

        # 尝试从原始文本中重新解析 debate 结构化数据（deepseek 非 JSON 输出格式）
        parsed = _try_parse_debate_text(text)
        if parsed:
            raw_json = json.dumps(parsed, ensure_ascii=False)
            md = _format_debate_markdown(raw_json)
            return raw_json + "\n\n---\n" + md

        # 实在无法解析，去掉 Claims 块返回纯文本
        text = _strip_claims_section(text)
        return text

    # JSON 放在前面供 DebatePanel 解析，Markdown 放在分隔线后供详情面板展示
    md = _format_debate_markdown(raw_json)
    return raw_json + "\n\n---\n" + md


def _format_strategy_markdown(raw_json: str) -> str:
    """Convert strategy JSON into a well-structured Markdown report for frontend display."""
    import json as _json
    try:
        obj = _json.loads(raw_json)
    except (_json.JSONDecodeError, ValueError):
        return raw_json  # not valid JSON, return as-is

    rec = obj.get("recommendation", "N/A")
    score = obj.get("confidence_score", 0)
    reasoning = obj.get("reasoning", "")
    weight = obj.get("weight_summary", "")
    missing = obj.get("missing_data", [])

    # recommendation badge
    badge_map = {
        "Buy": "买入",
        "Sell": "卖出",
        "Hold": "持有",
        "N/A": "暂无法评估",
    }
    rec_label = badge_map.get(rec, rec)
    rec_icon_map = {"Buy": "🟢", "Sell": "🔴", "Hold": "🟡", "N/A": "⚪"}
    rec_icon = rec_icon_map.get(rec, "⚪")

    lines = [
        "---",
        f"## 策略裁决",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| **最终建议** | {rec_icon} **{rec_label}** |",
        f"| **置信度评分** | **{score}/100** |",
    ]

    if missing:
        lines.append(f"| **缺失数据** | {', '.join(missing)} |")

    lines.append("")

    if reasoning:
        lines.append("### 决策推理")
        lines.append("")
        lines.append(reasoning.strip())
        lines.append("")

    if weight:
        lines.append("### 因子权重分配")
        lines.append("")
        lines.append(weight.strip())
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def _extract_strategy_content(update: dict) -> str:
    """Format strategy JSON as Markdown for frontend display."""
    messages = update.get("messages")
    if not messages:
        return _extract_text(update, agent_name="strategy_expert")
    raw = _safe_text(messages[-1]).strip()
    if raw.startswith("{"):
        return _format_strategy_markdown(raw)
    return _extract_text(update, agent_name="strategy_expert")


def _extract_agent_content(node_name: str, update: dict) -> str:
    """Extract agent output; preserve JSON for structured downstream parsers."""
    if node_name == "strategy_expert":
        return _extract_strategy_content(update)
    if node_name == "risk_expert":
        return _extract_risk_raw_content(update)
    if node_name in ("bull_researcher", "bear_researcher"):
        side = "bull" if node_name == "bull_researcher" else "bear"
        debate_content = _serialize_debate_side(update, side)
        if debate_content:
            return debate_content
    return _extract_text(update, agent_name=node_name)


def _iter_stream_chunks(chunk: Any):
    """Normalize LangGraph stream chunks (with or without subgraph namespaces)."""
    if isinstance(chunk, tuple) and len(chunk) == 2:
        _, payload = chunk
        if isinstance(payload, dict):
            yield from payload.items()
        return
    if isinstance(chunk, dict):
        yield from chunk.items()


def _normalize_symbol(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def _run_workflow_sync(user_message: str, stock_symbol: str, user_id: str, thread_id: str, language: str | None = None) -> dict[str, Any]:
    """Run LangGraph workflow synchronously and return final results (including citations)."""
    normalized_symbol = _normalize_symbol(stock_symbol)
    final_report = ""
    recommendation = None
    guard_check = None
    evidence_packet = None

    lang_instruction = _language_instruction(language)
    enriched_message = f"[股票代码: {normalized_symbol}] {user_message}{lang_instruction}"

    initial_state = {
        "stock_symbol": normalized_symbol,
        "language": language or "",
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
        "executed_agents": [],
        "guard_retry_count": 0,
        "evidence_packet": None,
        "user_session_id": user_id,
    }
    config = {"configurable": {"thread_id": thread_id}}

    for chunk in langgraph_app.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            if update.get("final_report"):
                final_report = str(update["final_report"])
            if node_name == "recommendation_agent" and update.get("messages"):
                recommendation = _strip_json_blocks(_safe_text(update["messages"][-1]))
            if node_name in ("guard_agent", "guard") and "guard_check" in update:
                guard_check = update["guard_check"]
                if isinstance(guard_check, dict):
                    evidence_packet = guard_check.get("evidence_packet")

    from services.citations import build_citations
    citations = build_citations(
        final_report=final_report,
        evidence_packet=evidence_packet if isinstance(evidence_packet, dict) else None,
    )

    return {
        "final_report": final_report or "\u5206\u6790\u5b8c\u6210",
        "recommendation": recommendation,
        "guard_check": guard_check,
        "citations": citations,
    }


def run_analysis_once(
    user_message: str,
    stock_symbol: str,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    return _run_workflow_sync(user_message, stock_symbol, user_id, thread_id)


def run_comparison_once(symbols: list[str], user_id: str) -> dict[str, Any]:
    symbols_str = ", ".join(symbols)
    message = f"\u8bf7\u5bf9\u6bd4\u5206\u6790\u4ee5\u4e0b\u80a1\u7968: {symbols_str}\uff0c\u5305\u62ec\u6280\u672f\u9762\u3001\u57fa\u672c\u9762\u3001\u65b0\u95fb\u60c5\u7eea\u548c\u6295\u8d44\u5efa\u8bae\u7684\u5168\u9762\u5bf9\u6bd4"
    return _run_workflow_sync(message, symbols[0], user_id, f"compare_{user_id}")


def run_backtest_once(symbol: str, strategy_desc: str, user_id: str) -> dict[str, Any]:
    desc = strategy_desc or f"\u5bf9 {symbol} \u7684\u7b56\u7565\u8fdb\u884c\u5386\u53f2\u56de\u6d4b"
    message = f"\u8bf7\u5bf9 {symbol} \u8fdb\u884c\u5386\u53f2\u56de\u6d4b\u5206\u6790\u3002\u7b56\u7565\u63cf\u8ff0: {desc}\u3002\u8bf7\u8f93\u51fa\u603b\u6536\u76ca\u3001\u5e74\u5316\u6536\u76ca\u3001\u590f\u666e\u6bd4\u7387\u3001\u6700\u5927\u56de\u64a4\u3001\u80dc\u7387\u7b49\u5173\u952e\u6307\u6807"
    return _run_workflow_sync(message, symbol, user_id, f"backtest_{user_id}")


def run_alert_once(symbol: str, condition: str, user_id: str) -> dict[str, Any]:
    cond = condition or f"\u76d1\u63a7 {symbol} \u7684\u4ef7\u683c\u3001RSI\u3001MACD \u7b49\u5173\u952e\u6280\u672f\u6307\u6807\uff0c\u5982\u6709\u5f02\u5e38\u8bf7\u89e6\u53d1\u8b66\u62a5"
    message = f"\u8bf7\u5bf9 {symbol} \u8fdb\u884c\u5b9e\u65f6\u76d1\u63a7\u3002\u89e6\u53d1\u6761\u4ef6: {cond}"
    return _run_workflow_sync(message, symbol, user_id, f"alert_{user_id}")


def run_optimize_once(symbols: list[str], risk_preference: str, user_id: str) -> dict[str, Any]:
    symbols_str = ", ".join(symbols)
    message = f"\u8bf7\u5bf9\u4ee5\u4e0b\u6295\u8d44\u7ec4\u5408\u8fdb\u884c\u4f18\u5316: {symbols_str}\u3002\u98ce\u9669\u504f\u597d: {risk_preference}"
    return _run_workflow_sync(message, symbols[0], user_id, f"optimize_{user_id}")


LANGUAGE_LABELS: dict[str, str] = {
    "zh": "简体中文",
    "yue": "粤语 (Cantonese)",
    "en": "English",
}


def _language_instruction(language: str | None) -> str:
    if not language or language == "en":
        return ""
    label = LANGUAGE_LABELS.get(language, language)
    return f"\n\n[语言要求] 请全程使用 {label} 回复。所有分析内容、指标解释、建议都必须用 {label} 输出。"


def stream_analysis_events(
    user_message: str,
    stock_symbol: str,
    user_id: str,
    thread_id: str,
    session_id: str,
    language: str | None = None,
) -> Generator[str, None, dict[str, Any]]:
    normalized_symbol = _normalize_symbol(stock_symbol)
    final_report = ""
    recommendation = None
    guard_check = None
    output_level = ""

    lang_instruction = _language_instruction(language)
    enriched_message = f"[股票代码: {normalized_symbol}] {user_message}{lang_instruction}"

    initial_state = {
        "stock_symbol": normalized_symbol,
        "language": language or "",
        "messages": [{"role": "user", "content": enriched_message}],
        "user_profile": load_user_profile(user_id),
        "executed_agents": [],
        "guard_retry_count": 0,
        "evidence_packet": None,
        "user_session_id": user_id,
    }
    config = {"configurable": {"thread_id": thread_id}}

    yield _sse("analysis_start", {
        "session_id": session_id,
        "thread_id": thread_id,
        "stock_symbol": normalized_symbol,
        "analysis_type": "analyze",
    })

    emitted_agents: set[str] = set()
    debate_sides_emitted: set[str] = set()
    agent_start_times: dict[str, float] = {}
    target_price: dict | None = None
    risk_level: dict | None = None

    import time as _time
    current_node_name: str | None = None
    try:
        for chunk in langgraph_app.stream(
            initial_state,
            config=config,
            stream_mode="updates",
            subgraphs=True,
        ):
            for node_name, update in _iter_stream_chunks(chunk):
                current_node_name = node_name
                agent_meta = AGENT_LABELS.get(node_name, {"label": node_name, "icon": "\U0001f916"})
                label = agent_meta["label"]
                icon = agent_meta["icon"]

                if node_name not in emitted_agents:
                    emitted_agents.add(node_name)
                    agent_start_times[node_name] = _time.time()
                    yield _sse("agent_start", {
                        "agent": node_name,
                        "label": label,
                        "icon": icon,
                    })

                # === evidence_packet ===
                if node_name == "evidence_packet_builder" and "evidence_packet" in update:
                    ep = update["evidence_packet"]
                    chart = update.get("chart_data", [])
                    doc_evidence = _serialize_document_evidence(ep.get("document_evidence", []))
                    yield _sse("evidence_packet", {
                        "symbol": ep.get("symbol", ""),
                        "facts": ep.get("facts", []),
                        "evidence_score": ep.get("evidence_score", 0),
                        "allowed_output_level": ep.get("allowed_output_level", ""),
                        "chart_data": chart,
                        "document_evidence": doc_evidence,
                    })

                # 当 orchestrator 决定好下一批要运行的 agent 时，立即发出 agent_start，
                # 让前端在 agent 执行期间（可能耗时 30-120s）就显示 "运行中" 状态
                if node_name == "orchestrator":
                    next_agents = update.get("next")
                    if isinstance(next_agents, list):
                        for agent_id in next_agents:
                            if agent_id not in emitted_agents:
                                emitted_agents.add(agent_id)
                                meta = AGENT_LABELS.get(agent_id, {"label": agent_id, "icon": "\U0001f916"})
                                yield _sse("agent_start", {
                                    "agent": agent_id,
                                    "label": meta["label"],
                                    "icon": meta["icon"],
                                })
                    # 发射被跳过的 agent
                    skipped_agents = update.get("skipped_agents")
                    if isinstance(skipped_agents, list):
                        for sid in skipped_agents:
                            if sid not in emitted_agents and sid != "__end__":
                                emitted_agents.add(sid)
                                meta = AGENT_LABELS.get(sid, {"label": sid, "icon": "\U0001f916"})
                                yield _sse("agent_skipped", {
                                    "agent": sid,
                                    "label": meta["label"],
                                    "icon": meta["icon"],
                                })

                content = _extract_agent_content(node_name, update)
                is_guard = node_name in ("guard_agent", "guard")
                has_guard = isinstance(update.get("guard_check"), dict) and update["guard_check"]
                debate_subagents_emitted = False

                # debate_stage 子图在 subgraphs=False 时只上报顶层节点，此处作兜底拆包
                if node_name == "debate_stage":
                    for sub_agent, side in (
                        ("bull_researcher", "bull"),
                        ("bear_researcher", "bear"),
                    ):
                        if sub_agent in debate_sides_emitted:
                            continue
                        sub_content = _serialize_debate_side(update, side)
                        if not sub_content:
                            continue
                        debate_subagents_emitted = True
                        sub_meta = AGENT_LABELS.get(
                            sub_agent,
                            {"label": sub_agent, "icon": "\U0001f916"},
                        )
                        if sub_agent not in emitted_agents:
                            emitted_agents.add(sub_agent)
                            agent_start_times[sub_agent] = _time.time()
                            yield _sse("agent_start", {
                                "agent": sub_agent,
                                "label": sub_meta["label"],
                                "icon": sub_meta["icon"],
                            })
                        yield _sse("agent_output", {
                            "agent": sub_agent,
                            "content": sub_content,
                        })
                        debate_sides_emitted.add(sub_agent)

                        # ── 辩论智能体核心结论提取 ──
                        cc = _extract_core_conclusion(sub_content, sub_agent)
                        if cc:
                            yield _sse("agent_core_conclusion", {
                                "agent": sub_agent,
                                **cc,
                            })

                        yield _sse("agent_done", {
                            "agent": sub_agent,
                            "duration_ms": round(
                                (_time.time() - agent_start_times.get(sub_agent, _time.time())) * 1000
                            ),
                        })

                if node_name == "recommendation_agent" and update.get("messages"):
                    raw_recommendation = _safe_text(update["messages"][-1])
                    rec_json = _extract_json_block(raw_recommendation)
                    valuation = _coerce_valuation_scenario(rec_json)
                    if valuation:
                        target_price = valuation
                        yield _sse("target_price", target_price)
                    recommendation = _strip_json_blocks(raw_recommendation) or raw_recommendation
                    content = recommendation

                if content and not is_guard and not (
                    node_name == "debate_stage" and debate_subagents_emitted
                ):
                    yield _sse("agent_output", {
                        "agent": node_name,
                        "content": content,
                    })
                    if node_name in ("bull_researcher", "bear_researcher"):
                        debate_sides_emitted.add(node_name)

                    # ── 提炼核心结论（LLM 轻量提取）──
                    lang = initial_state.get("language", "")
                    cc = _extract_core_conclusion(content, node_name, lang)
                    if cc:
                        yield _sse("agent_core_conclusion", {
                            "agent": node_name,
                            **cc,
                        })

                # ── debate_stage 子代理拆包后，补一个汇聚核心结论 ──
                if node_name == "debate_stage" and debate_subagents_emitted:
                    yield _sse("agent_core_conclusion", {
                        "agent": "debate_stage",
                        "core_conclusion": "多空双方已就估值、盈利能力、技术面等核心议题展开对抗性分析，详见多空博弈面板。",
                        "conclusion_sentiment": "neutral",
                        "confidence_score": 70,
                    })

                if update.get("final_report"):
                    final_report = str(update["final_report"])
                if node_name == "risk_expert":
                    coerced_risk = _extract_risk_level(update)
                    if coerced_risk:
                        risk_level = coerced_risk
                        yield _sse("risk_level", risk_level)
                if is_guard and has_guard:
                    guard_check = update["guard_check"]
                    output_level = update.get("output_level", "")
                    gc = guard_check
                    guard_text = (
                        f"- **Valid**: {gc.get('is_valid', 'N/A')}\n"
                        f"- **Confidence Score**: {gc.get('confidence_score', 'N/A')}/100\n"
                        f"- **Issues**: {', '.join(gc.get('issues', [])) if gc.get('issues') else 'none'}\n"
                        f"- **Reasoning**: {gc.get('final_reasoning', 'N/A')}"
                    )
                    yield _sse("agent_output", {
                        "agent": node_name,
                        "content": guard_text,
                    })

                    # ── Guard 核心结论提取 ──
                    cc = _extract_core_conclusion(guard_text, node_name)
                    if cc:
                        yield _sse("agent_core_conclusion", {
                            "agent": node_name,
                            **cc,
                        })

                yield _sse("agent_done", {
                    "agent": node_name,
                    "duration_ms": round((_time.time() - agent_start_times.get(node_name, _time.time())) * 1000),
                })

    except Exception as exc:
        import traceback
        print(f"[analysis_service] agent error for {current_node_name}: {exc}")
        traceback.print_exc()
        if current_node_name and current_node_name not in ("strategy_aggregator",):
            meta = AGENT_LABELS.get(current_node_name, {"label": current_node_name, "icon": "\U0001f916"})
            yield _sse("agent_error", {
                "agent": current_node_name,
                "label": meta["label"],
                "icon": meta["icon"],
                "message": str(exc)[:500],
                "duration_ms": round((_time.time() - agent_start_times.get(current_node_name, _time.time())) * 1000),
            })
        final_report = f"分析过程中发生错误: {str(exc)[:200]}"
        guard_check = {
            "is_valid": False,
            "confidence_score": 0,
            "issues": [f"Pipeline error: {str(exc)[:150]}"],
            "corrections": [],
            "final_reasoning": f"Agent {current_node_name} 执行失败",
        }

    if not final_report and recommendation:
        final_report = recommendation

    done_payload = {
        "final_report": final_report or "\u5206\u6790\u5b8c\u6210",
        "recommendation": recommendation,
        "guard_check": guard_check,
        "target_price": target_price,
        "risk_level": risk_level,
    }

    ep = guard_check.get("evidence_packet", {}) if guard_check else {}
    output_level = ep.get("allowed_output_level", "") if isinstance(ep, dict) else ""

    # 3.3.2 — 构建 citations
    from services.citations import build_citations
    done_payload["citations"] = build_citations(
        final_report=final_report,
        evidence_packet=ep if isinstance(ep, dict) else None,
    )

    if output_level == "limited_analysis_partial":
        done_payload["disclaimer"] = (
            "\u672c\u5206\u6790\u56e0\u90e8\u5206\u5173\u952e\u6570\u636e\u7f3a\u5931\uff0c"
            "\u7b56\u7565\u4e0e\u98ce\u9669\u8bc4\u4f30\u4e3a\u53c2\u8003\u6027\u8d28\u3002"
        )

    yield _sse("analysis_complete", done_payload)
    return done_payload


def _serialize_document_evidence(doc_evidence: list[dict]) -> list[dict]:
    """将 DocumentChunk 列表序列化为前端可消费的轻量格式。"""
    seen = set()
    result = []
    for dc in doc_evidence:
        if not isinstance(dc, dict):
            continue
        source = dc.get("source", "")
        doc_id = dc.get("doc_id", "")
        # 去重：同一 source+doc_id 只保留第一条
        key = f"{source}|{doc_id}"
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "source": source,
            "doc_id": doc_id,
            "doc_type": dc.get("doc_type", ""),
            "section": dc.get("section", ""),
            "publish_date": dc.get("publish_date", ""),
            "report_period": dc.get("report_period", ""),
            "page": dc.get("page", ""),
        })
    return result


def _sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
