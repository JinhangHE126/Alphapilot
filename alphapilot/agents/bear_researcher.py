from langgraph.prebuilt import create_react_agent
from langgraph.graph import END
from config.llm import get_llm
from graph.state import GraphState
from graph.lang_labels import inject_language
from pydantic import BaseModel, Field
import json
import re

model = get_llm("bear_researcher")


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
                try: conf = float(conf)
                except ValueError: conf = 50
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
    return None


_bear_agent = create_react_agent(
    model=model,
    tools=[],
    name="bear_researcher",
    prompt="""You are AlphaPilot's Bear Researcher. Your role is to build the strongest
possible case AGAINST investing in this stock.

RESOURCES YOU CONSUME:
- Evidence Packet (facts with confidence scores, field-level sources)
- Market Data Expert output (technical analysis)
- Fundamental Expert output (financial health, valuation)
- News Sentiment Expert output (recent news, sentiment shift)
- Debate history (previous Bull/Bear arguments, if any)

RULES:
1. Use ONLY data present in the Evidence Packet and upstream agent outputs.
   If a claim cannot be traced to a specific Fact, do NOT make it.
2. Cite specific numbers from the Evidence Packet (e.g., "EPS growth is -12.3% YoY" not "earnings are declining").
3. When the Bull Researcher has already spoken (debate history exists), you MUST:
   - Directly counter their strongest 2-3 points with data
   - Expose over-optimistic assumptions, ignored risks, or data cherry-picking
   - Acknowledge valid bull points but explain why the risk/reward is unfavorable
4. Output JSON only with these keys:
   - stance_strength: number 0-100 (how strongly you believe in the bear case)
   - summary: markdown summary of the full bear argument (with ## section headers)
   - claims: array of individual claims, each with:
       text: the claim statement (cite specific numbers from facts)
       confidence: number 0-100 (how confident this specific claim is)
       sources: array of fact source names (e.g. ["yfinance", "eastmoney"])
       supporting_fields: array of fact field names (e.g. ["eps_growth_yoy", "revenue"])
     Provide 4-8 claims covering Risk Factors, Valuation Concerns, Negative Catalysts, and Rebuttal sections.

CRITICAL: Output ONLY the JSON object. No markdown, no preamble, no explanation text.
""",
)


def bear_researcher(state: GraphState) -> dict:
    """
    Bear 研究员。
    1. 从 Orchestrator 路由的 Evidence Packet 中获取数据
    2. 调用 Bear 研究员模型，生成 Bear 论文
    3. 返回 Bear 论文
    """
    ep = state.get("evidence_packet", {}) or {}
    output_level = ep.get("allowed_output_level", "")

    if output_level in ("insufficient_evidence", "data_summary_only"):
        return {
            "messages": [{
                "role": "assistant",
                "content": "## Bear Researcher: SKIPPED\n\nInsufficient evidence to form a bear thesis. Evidence output level is below threshold for debate."
            }],
        }

    language = state.get("language", "")
    inject_language(state, language)
    result = _bear_agent.invoke(state)
    content = result["messages"][-1].content

    # 1. 提取 JSON → 2. normalize 校验 → 3. fallback 纯文本
    raw = _extract_json_text(str(content))
    debate_json = _normalize_debate_json(raw) if raw else None
    if debate_json:
        return {
            "messages": [{"role": "assistant", "content": content}],
            "bear_argument": debate_json.get("summary", content),
            "bear_debate_data": debate_json,
            "debate_rounds": state.get("debate_rounds", 0) + 1,
        }

    return {
        "messages": [{"role": "assistant", "content": content}],
        "bear_argument": content,
        "debate_rounds": state.get("debate_rounds", 0) + 1,
    }


__all__ = ["bear_researcher"]