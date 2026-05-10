from langchain_core.tools import tool
from rag.retriever import retriever


@tool
def retrieve_knowledge(query: str, k: int = 5) -> str:
    """
    从 RAG 知识库检索最相关的公司信息、财报、研报、公告等。
    输入：查询字符串（如 "TSLA Q4 2024 earnings"）
    返回：检索到的文档内容（供 Agent 使用）
    """
    docs = retriever.retrieve(query, k=k)
    if not docs:
        return "No relevant knowledge found in RAG index."

    result = "\n\n".join(
        f"[Source {i+1}]\n{getattr(doc, 'page_content', doc)}"
        for i, doc in enumerate(docs)
    )
    return result