from langchain_core.tools import tool
from rag.retriever import retriever
import json


@tool
def retrieve_knowledge(query: str, k: int = 5) -> str:
    """
    从 RAG 知识库检索最相关的公司信息、财报、研报、公告等。
    输入：查询字符串（如 "TSLA Q4 2024 earnings"）
    返回：结构化 JSON，包含文档内容、相似度分数、来源和日期等元数据。
    """
    results = retriever.retrieve_with_scores(query, k=k)
    if not results:
        return json.dumps({"status": "empty", "documents": []})

    docs_json = []
    for r in results:
        docs_json.append({
            "content": r.doc.page_content[:500],
            "score": r.score,
            "source": r.metadata.get("source", "unknown"),
            "symbol": r.metadata.get("symbol", ""),
            "date": r.metadata.get("date", ""),
            "type": r.metadata.get("type", ""),
        })

    return json.dumps({"status": "ok", "documents": docs_json}, ensure_ascii=False)