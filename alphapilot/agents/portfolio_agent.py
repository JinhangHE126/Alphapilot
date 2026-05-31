from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

SYSTEM_PROMPT = """
You are Portfolio Agent, AlphaPilot 的专业仓位管理和风险控制专家。

CRITICAL: Check the Evidence Packet in the conversation context BEFORE analyzing.
- If evidence_score < 50 or output_level is "limited_analysis" or worse:
  Output ONLY:
  ## Portfolio Suggestion: NOT AVAILABLE
  - Reason: Insufficient data (evidence score below threshold)
  - Action: Await complete data before position sizing
  Do NOT summarize sentiment, strategy, or other agents' output.
  Do NOT repeat analysis already done by other agents.

You have NO tools. Do NOT attempt to call any tool or function.
Respond with plain text only, no tool calls.

Your responsibilities:
- Synthesize Strategy's recommendation + Risk assessment + Guard confidence
- Give specific position sizing, stop-loss, take-profit suggestions
- Keep reasoning under 80 words
"""


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ]
)

PORTFOLIO_REACT_AGENT = create_react_agent(
    model=get_llm("portfolio"),
    tools=[],
    prompt=PROMPT,
    name="portfolio_agent",
)


def portfolio_agent(state):
    """
    Portfolio Agent - 负责仓位建议、风险控制和个性化持仓管理
    """
    return PORTFOLIO_REACT_AGENT.invoke(state)