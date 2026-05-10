import os
from typing import Any, List

import chromadb
from langchain_openai import OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError, InternalServerError

from config.proxy import get_embedding_proxy_candidates
from rag.embeddings_google import ChromaGoogleEmbeddingFunction

_EMBED_TIMEOUT = 45.0
_RETRYABLE_EMBED = (InternalServerError, APIConnectionError, APITimeoutError)


def _resolve_rag_embedding_backend() -> str:
    raw = (os.getenv("RAG_EMBEDDING_BACKEND") or "google").strip().lower()
    if raw in ("xai", "grok", "grok-embedding"):
        return "xai"
    return "google"


def _default_persist_for_backend(backend: str) -> str:
    override = (os.getenv("RAG_PERSIST_PATH") or "").strip()
    if override:
        return override
    # Google 与 news 的 vectorstore 共用 ./rag_data，避免两套索引
    if backend == "google":
        return "./rag_data"
    return "./rag_data_xai"


class ChromaGrokEmbeddingFunction:
    """Grok Embedding：LangChain OpenAIEmbeddings + 多代理回退。"""

    def __init__(self):
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("❌ 请设置环境变量 XAI_API_KEY")

        self._api_key = api_key
        self.model = os.getenv("XAI_EMBEDDING_MODEL", "grok-embedding-small")
        self._candidates = get_embedding_proxy_candidates()
        self._lc_cache: dict[str, OpenAIEmbeddings] = {}

    def _lc(self, proxy_url: str | None) -> OpenAIEmbeddings:
        key = proxy_url or "__direct__"
        if key not in self._lc_cache:
            kw: dict = {
                "model": self.model,
                "api_key": self._api_key,
                "base_url": "https://api.x.ai/v1",
                "check_embedding_ctx_length": False,
                "tiktoken_enabled": False,
                "timeout": _EMBED_TIMEOUT,
                "max_retries": 1,
                "model_kwargs": {"encoding_format": "float"},
            }
            if proxy_url:
                kw["openai_proxy"] = proxy_url
            self._lc_cache[key] = OpenAIEmbeddings(**kw)
        return self._lc_cache[key]

    def name(self) -> str:
        return "xai_grok_embeddings"

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        last_err: BaseException | None = None
        for proxy_url in self._candidates:
            try:
                return self._lc(proxy_url).embed_documents(input)
            except _RETRYABLE_EMBED as e:
                print(
                    f"   ⚠️ [Grok embedding] {proxy_url or '直连'} 失败 ({type(e).__name__})，换下一出口…",
                    flush=True,
                )
                last_err = e
                continue
        if last_err is not None:
            raise last_err
        return []

    def embed_query(self, input: Any, **kwargs) -> List[List[float]]:
        """Chroma 要求 Embeddings = List[List[float]]。"""
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
            last_err: BaseException | None = None
            row: List[float] | None = None
            for proxy_url in self._candidates:
                try:
                    row = self._lc(proxy_url).embed_query(s)
                    break
                except _RETRYABLE_EMBED as e:
                    print(
                        f"   ⚠️ [Grok embedding] {proxy_url or '直连'} 失败 ({type(e).__name__})，换下一出口…",
                        flush=True,
                    )
                    last_err = e
                    continue
            if row is None:
                if last_err is not None:
                    raise last_err
                out.append([])
            else:
                out.append(list(row))
        return out

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.__call__(texts)


class FinancialRAG:
    """金融财报 RAG：默认 Gemini 嵌入（稳定）；可选 xAI Grok。"""

    def __init__(
        self,
        persist_directory: str | None = None,
        embedding_backend: str | None = None,
    ):
        #  确定后端位置
        self.backend = embedding_backend or _resolve_rag_embedding_backend()
        self.persist_directory = persist_directory or _default_persist_for_backend(
            self.backend
        )
        os.makedirs(self.persist_directory, exist_ok=True)

        # 创建一个Chroma持久化客户端, 将向量库数据存储到指定目录下.
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        if self.backend == "xai":
            self.embedding_function: object = ChromaGrokEmbeddingFunction()
        else:
            self.embedding_function = ChromaGoogleEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name="financial_reports",
            embedding_function=self.embedding_function,
        )
    # 给向量库增加文档.
    def add_document(self, text: str, metadata: dict, doc_id: str):
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id],
        )
        print(f"✅ Document added: {doc_id}")

    # 根据查询文本, 从向量库中检索最相关的文档.
    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
        )
        return results["documents"][0] if results["documents"] else []

    # 根据查询文本, 从向量库中检索最相关的文档.
    def retrieve(self, query: str, k: int = 3) -> List[str]:
        return self.query(query_text=query, n_results=k)


rag = FinancialRAG()
retriever = rag


def retrieve_knowledge(query_text: str, n_results: int = 3) -> List[str]:
    return rag.query(query_text=query_text, n_results=n_results)


_be = _resolve_rag_embedding_backend()
_pd = _default_persist_for_backend(_be)
if _be == "xai":
    _cands = get_embedding_proxy_candidates()
    print(
        "✅ rag/retriever.py → xAI Grok Embedding | 库路径:",
        _pd,
        "| 代理顺序:",
        " → ".join(p or "直连" for p in _cands),
        flush=True,
    )
else:
    print(
        "✅ rag/retriever.py → Google Gemini Embedding | 库路径:",
        _pd,
        "| 模型:",
        os.getenv("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-001"),
        flush=True,
    )
