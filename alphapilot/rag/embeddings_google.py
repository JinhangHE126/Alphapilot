"""Google Gemini embeddings adapter shared by vectorstore and retriever."""

import os
from typing import Any, List

from langchain_google_genai import GoogleGenerativeAIEmbeddings


def as_embedding_vector(vec: Any) -> List[float]:
    """Chroma 需要 Python List[float]；numpy / 异常返回值会变成 rust 侧 TypeError。"""
    if vec is None:
        return []
    try:
        import numpy as np

        if isinstance(vec, np.ndarray):
            return [float(x) for x in vec.astype(np.float64).flatten()]
    except ImportError:
        pass
    if isinstance(vec, float):
        raise TypeError(
            "嵌入模型返回了单个 float，无法作为向量；请检查 GOOGLE_API_KEY / gemini-embedding 配置。"
        )
    if isinstance(vec, (list, tuple)):
        return [float(x) for x in vec]
    raise TypeError(f"无法解析嵌入向量类型: {type(vec)!r}")


class ChromaGoogleEmbeddingFunction:
    """Adapter that lets ChromaDB use LangChain's Google embeddings."""

    def __init__(self):
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-001"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document",
        )

    def name(self) -> str:
        return "google_generative_ai_embeddings"

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        raw = self.embedding_model.embed_documents(input)
        return [as_embedding_vector(row) for row in raw]

    def embed_query(self, input: Any, **kwargs) -> List[List[float]]:
        """Chroma 要求返回 Embeddings = List[List[float]]，不是单个向量。"""
        if input is None:
            return []
        if isinstance(input, str):
            texts = [input]
        elif isinstance(input, (list, tuple)):
            texts = list(input)
        else:
            texts = [str(input)]
        out: List[List[float]] = []
        for t in texts:
            s = t if isinstance(t, str) else str(t)
            if not s.strip():
                out.append([])
                continue
            out.append(as_embedding_vector(self.embedding_model.embed_query(s)))
        return out

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.__call__(texts)
