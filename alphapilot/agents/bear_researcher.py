from langgraph.prebuilt import create_react_agent
from langgraph.graph import END
from config.llm import get_llm
from graph.state import GraphState
from graph.lang_labels import inject_language

model = get_llm("bear_researcher")

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
4. Organize your argument into sections:
   - **Risk Factors**: Financial instability, competitive threats, macro headwinds
   - **Valuation Concerns**: Why current price is NOT justified (PE decompression, growth slowdown, margin pressure)
   - **Negative Catalysts**: Upcoming risks, industry headwinds, regulatory threats, insider selling
   - **Counterpoint Rebuttal**: (only if Bull has spoken) Refute bull arguments with evidence
5. Be critical and data-driven, not fear-mongering. Every claim must reference the Evidence Packet.

OUTPUT: Plain text bear argument with section headers. No JSON. No tool calls.""",
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

    return {
        "messages": [{"role": "assistant", "content": content}],
        "bear_argument": content,
        "debate_rounds": state.get("debate_rounds", 0) + 1,
    }


__all__ = ["bear_researcher"]