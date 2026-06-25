from langgraph.prebuilt import create_react_agent
from langgraph.graph import END
from config.llm import get_llm
from graph.state import GraphState
from graph.lang_labels import inject_language
from pydantic import BaseModel, Field
import json
import re

model = get_llm("bull_researcher")


# ══════════════════════════════════════════════════════════════════════
# Schema + normalize — 防止 LLM 输出 malformed JSON
# ══════════════════════════════════════════════════════════════════════

class DebateClaim(BaseModel):
    text: str = Field(description="Claim statement citing specific numbers")
    confidence: int | float = Field(default=50, ge=0, le=100, description="Confidence 0-100")
    sources: list[str] = Field(default_factory=list)
    supporting_fields: list[str] = Field(default_factory=list)

class DebateStructuredOutput(BaseModel):
    stance_strength: int | float = Field(default=50, ge=0, le=100)
    summary: str = Field(default="")
    claims: list[DebateClaim] = Field(default_factory=list, min_length=1, max_length=12)


def _normalize_debate_json(raw: dict) -> dict | None:
    """Coerce LLM JSON into schema-safe dict. Returns None if unrecoverable."""
    if not isinstance(raw, dict):
        return None
    try:
        validated = DebateStructuredOutput.model_validate(raw)
    except Exception:
        # 宽松修复：逐字段强制转换
        normalized: dict = {}

        ss = raw.get("stance_strength")
        if isinstance(ss, (int, float)) and 0 <= ss <= 100:
            normalized["stance_strength"] = int(ss)
        else:
            normalized["stance_strength"] = 50

        normalized["summary"] = str(raw.get("summary", ""))

        raw_claims = raw.get("claims")
        if not isinstance(raw_claims, list):
            raw_claims = []

        safe_claims: list[dict] = []
        for c in raw_claims:
            if not isinstance(c, dict):
                continue
            text = str(c.get("text", ""))
            if not text.strip():
                continue
            conf = c.get("confidence")
            if isinstance(conf, (int, float)) and 0 <= conf <= 100:
                pass
            elif isinstance(conf, str):
                try:
                    conf = float(conf)
                except ValueError:
                    conf = 50
            else:
                conf = 50

            sources = c.get("sources", [])
            if isinstance(sources, str):
                sources = [s.strip() for s in sources.split(",") if s.strip()]
            elif not isinstance(sources, list):
                sources = []
            sources = [str(s) for s in sources if s]

            fields = c.get("supporting_fields", [])
            if isinstance(fields, str):
                fields = [f.strip() for f in fields.split(",") if f.strip()]
            elif not isinstance(fields, list):
                fields = []
            fields = [str(f) for f in fields if f]

            safe_claims.append({
                "text": text,
                "confidence": int(conf),
                "sources": sources,
                "supporting_fields": fields,
            })

        normalized["claims"] = safe_claims

        if not safe_claims:
            return None

        return normalized

    return validated.model_dump()


def _extract_json_text(text: str) -> dict | None:
    """从文本中提取JSON，失败返回None"""
    block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if block:
        try:
            return json.loads(block.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    # Fallback: deepseek 输出 "Stance Strength: N\nSummary: ...\nClaims: {...}" 文本格式
    return _parse_debate_text_to_json(text)


def _parse_debate_text_to_json(text: str) -> dict | None:
    """将 deepseek 输出的非 JSON 结构化文本转为 dict。
    格式: Stance Strength: N
          Summary: ## ...
          Claims: {'text': '...', 'confidence': N, 'sources': [...], 'supporting_fields': [...]}, {...}, ...
    """
    stance_match = re.search(r"Stance\s*Strength\s*:\s*(\d+)", text, re.IGNORECASE)
    if not stance_match:
        return None

    stance = int(stance_match.group(1))
    stance = max(0, min(100, stance))

    # 提取 Summary: 后面的 Markdown 正文（到 Claims: 之前）
    summary = ""
    summary_match = re.search(r"Summary\s*:\s*(.+?)(?=\n+\s*Claims?\s*:)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()

    # 提取 Claims 区域：Claims: {...}, {...}, ...
    claims_raw = ""
    claims_match = re.search(r"Claims?\s*:\s*(.+)$", text, re.IGNORECASE)
    if claims_match:
        claims_raw = claims_match.group(1).strip()

    claims: list[dict] = []
    if claims_raw:
        # 逐个提取 {...} 块（支持单引号 Python dict 格式）
        depth = 0
        buf = ""
        for ch in claims_raw:
            buf += ch
            if ch in ("{",):
                depth += 1
            elif ch in ("}",):
                depth -= 1
                if depth == 0 and buf.strip():
                    claims.append(buf.strip())
                    buf = ""
        if not claims:
            # 尝试直接 eval（安全受限环境用 ast.literal_eval）
            try:
                claims_list = json.loads(claims_raw.replace("'", '"'))
                if isinstance(claims_list, list):
                    claims = claims_list
            except (json.JSONDecodeError, ValueError):
                pass

    safe_claims: list[dict] = []
    for raw_claim in claims:
        try:
            # Python dict 单引号 → JSON 双引号
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


_bull_agent = create_react_agent(
    model=model,
    tools=[],
    name="bull_researcher",
    prompt="""You are AlphaPilot's Bull Researcher. Your role is to build the strongest
possible case FOR investing in this stock.

RESOURCES YOU CONSUME:
- Evidence Packet (facts with confidence scores, field-level sources)
- Market Data Expert output (technical analysis)
- Fundamental Expert output (financial health, valuation)
- News Sentiment Expert output (recent news, sentiment shift)
- Debate history (previous Bull/Bear arguments, if any)

RULES:
1. Use ONLY data present in the Evidence Packet and upstream agent outputs.
   If a claim cannot be traced to a specific Fact, do NOT make it.
2. Cite specific numbers from the Evidence Packet (e.g., "PE ratio is 18.5" not "PE is reasonable").
3. When the Bear Researcher has already spoken (debate history exists), you MUST:
   - Directly counter their strongest 2-3 points with data
   - Expose logical flaws, cherry-picked data, or overblown risks
   - Acknowledge valid concerns but explain why they are overpriced by the market
4. Output JSON only with these keys:
   - stance_strength: number 0-100 (how strongly you believe in the bull case)
   - summary: markdown summary of the full bull argument (with ## section headers)
   - claims: array of individual claims, each with:
       text: the claim statement (cite specific numbers from facts)
       confidence: number 0-100 (how confident this specific claim is)
       sources: array of fact source names (e.g. ["yfinance", "eastmoney"])
       supporting_fields: array of fact field names (e.g. ["pe_ratio", "revenue"])
     Provide 4-8 claims covering Growth, Valuation, Catalysts, and Rebuttal sections.

CRITICAL: Output ONLY the JSON object. No markdown, no preamble, no explanation text.
""",
)


def bull_researcher(state: GraphState) -> dict:
    """
    Bull 研究员。
    1. 从 Orchestrator 路由的 Evidence Packet 中获取数据
    2. 调用 Bull 研究员模型，生成 Bull 论文
    3. 返回 Bull 论文
    """
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": "## Bull Researcher: SKIPPED\n\nInsufficient evidence to form a bull thesis. Evidence output level is below threshold for debate."
            }],
        }

    language = state.get("language", "")
    inject_language(state, language)
    result = _bull_agent.invoke(state)
    content = result["messages"][-1].content

    # 1. 提取 JSON → 2. normalize 校验 → 3. fallback 纯文本
    raw = _extract_json_text(str(content))
    debate_json = _normalize_debate_json(raw) if raw else None
    if debate_json:
        return {
            "messages": [{"role": "assistant", "content": content}],
            "bull_argument": debate_json.get("summary", content),
            "bull_debate_data": debate_json,
        }

    return {
        "messages": [{"role": "assistant", "content": content}],
        "bull_argument": content,
    }


__all__ = ["bull_researcher"]