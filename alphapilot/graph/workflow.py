import os
from langgraph_supervisor import create_supervisor
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.market_agent import market_agent
from prompts.supervisor_prompt import supervisor_prompt  # 后面会改成 from txt 读取
# 其他 agent 暂时用占位，后面再加

model = ChatGoogleGenerativeAI(
    model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1,
)

# 目前只有 1 个真实 Agent，其余后续添加
workflow = create_supervisor(
    agents=[market_agent],   # 后面会逐步添加 fundamental_agent 等
    model=model,
    prompt=supervisor_prompt,
    output_mode="last_message",
)

app = workflow.compile()