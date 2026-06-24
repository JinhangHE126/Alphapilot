from langgraph.prebuilt import create_react_agent
from langgraph.graph import END
from config.llm import get_llm
from graph.state import GraphState
from graph.lang_labels import inject_language

model = get_llm("bull_researcher")

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
4. Organize your argument into sections:
   - **Growth Thesis**: Revenue trajectory, market expansion, earnings momentum
   - **Valuation Support**: Why current price is justified (DCF anchors, peer comparison, PEG)
   - **Positive Catalysts**: Upcoming events, industry tailwinds, competitive moat
   - **Counterpoint Rebuttal**: (only if Bear has spoken) Refute bear arguments with evidence
5. Be persuasive and data-driven, not hype-driven. Every claim must reference the Evidence Packet.

OUTPUT: Plain text bull argument with section headers. No JSON. No tool calls.""",
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

    return {
        "messages": [{"role": "assistant", "content": content}],
        "bull_argument": content,
    }


__all__ = ["bull_researcher"]