from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from config.llm import get_llm

SYSTEM_PROMPT = """
You are Portfolio Agent, AlphaPilot 的专业仓位管理和风险控制专家。

你的核心职责是：
- 根据 Strategy Agent 的投资建议 + Risk Agent 的风险评估 + Guard 的置信度
- 结合用户风险偏好（如果 state 中有 user_profile 则优先使用）
- 给出具体、可执行的仓位建议

必须输出的字段（用清晰格式）：
- suggested_position: "5-8% of total portfolio" （建议仓位比例）
- stop_loss: "Trailing stop 8%" 或具体价格
- take_profit: "目标价位或分批减仓计划"
- risk_rating: "Low / Medium / High"
- reasoning: 简短理由（不超过 80 字）

规则：
- 永远不要建议全仓
- Guard 置信度低于 70 时，必须降低仓位建议
- 保持专业、谨慎、数据驱动
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