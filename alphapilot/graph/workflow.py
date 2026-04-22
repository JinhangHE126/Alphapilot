import os
from dotenv import load_dotenv
load_dotenv()

from langgraph_supervisor import create_supervisor
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.market_agent import market_agent
from graph.state import GraphState
from prompts.supervisor_prompt import supervisor_prompt  # 后面我们会改成从 txt 读取

model = ChatGoogleGenerativeAI(
    model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite-preview"),
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1,
)

# 创建 Supervisor（目前只传入 market_agent，后续逐步添加）
workflow = create_supervisor(
    agents=[market_agent],           # Week 2 会继续添加其他 Agent
    model=model,
    prompt=supervisor_prompt,
    output_mode="last_message",
)

# 注意：目前 create_supervisor 内部会自动管理 state，
# 但我们已经定义好 GraphState，后面 Week 3-4 会切换成自定义 StateGraph 以获得更强控制力
app = workflow.compile()

# 导出供 main.py 使用
__all__ = ["app", "GraphState"]