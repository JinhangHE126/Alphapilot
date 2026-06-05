import os
from pathlib import Path
from typing import List, Dict, Any, Set
from datetime import datetime, timezone
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dataclasses import dataclass, field


@dataclass
class FactDocument:
    doc: Document
    distance: float
    similarity: float
    metadata: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        """
        Backward-compatible alias.
        Prefer `similarity` for new logic.
        """
        return self.similarity


# ====================== 配置 ======================
EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)

RAG_INDEX_PATH = Path("rag_data/faiss_index")
RAG_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

def _resolve_model_name() -> str:
    """Support short model name and full HF repo name."""
    if "/" in EMBEDDING_MODEL_NAME:
        return EMBEDDING_MODEL_NAME
    return f"sentence-transformers/{EMBEDDING_MODEL_NAME}"


def _build_embedding_model() -> HuggingFaceEmbeddings:
    """
    Build embeddings with robust fallback:
    1) local cache only (no network dependency)
    2) online download if local cache unavailable
    """
    model_name = _resolve_model_name()
    base_model_kwargs = {"device": "cpu"}
    encode_kwargs = {"normalize_embeddings": True}

    try:
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={**base_model_kwargs, "local_files_only": True},
            encode_kwargs=encode_kwargs,
        )
    except Exception as local_error:
        print(f"⚠️ 本地离线加载 embedding 失败，尝试联网加载: {local_error}")

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=base_model_kwargs,
        encode_kwargs=encode_kwargs,
    )

# ====================== 主 RAG 类 ======================
class RagRetriever:
    """AlphaPilot 本地 FAISS RAG（离线版）"""

    def __init__(self):
        self.vectorstore = None
        self.embedding_model = None
        self._known_doc_ids: Set[str] = set()
        try:
            self.embedding_model = _build_embedding_model()
            self.load_or_create_index()
        except Exception as err:
            print(f"❌ RAG 初始化失败，已降级为禁用模式: {err}")
            self.vectorstore = None

    def load_or_create_index(self):
        """加载已有索引或创建新索引"""
        if not self.embedding_model:
            return

        if RAG_INDEX_PATH.exists():
            print(f"✅ 加载现有 FAISS 索引: {RAG_INDEX_PATH}")
            self.vectorstore = FAISS.load_local(
                str(RAG_INDEX_PATH),
                self.embedding_model,
                allow_dangerous_deserialization=True,
            )
            self._scan_existing_doc_ids()
        else:
            print("🆕 创建新的 FAISS 索引...")
            self.vectorstore = FAISS.from_texts(
                ["[Placeholder] AlphaPilot RAG 初始化文档"],
                self.embedding_model,
                metadatas=[{"source": "init", "type": "placeholder"}],
            )
            self.vectorstore.save_local(str(RAG_INDEX_PATH))
            self._known_doc_ids = set()

    def _scan_existing_doc_ids(self):
        """扫描向量库中已有的 doc_id，用于去重。"""
        try:
            docstore = self.vectorstore.docstore
            for doc_id in docstore._dict:
                doc = docstore._dict.get(doc_id)
                if doc and hasattr(doc, "metadata"):
                    existing = doc.metadata.get("doc_id")
                    if existing:
                        self._known_doc_ids.add(existing)
            print(f"📚 已加载 {len(self._known_doc_ids)} 个已知 doc_id 用于去重")
        except Exception:
            self._known_doc_ids = set()

    def add_document(self, text: str, metadata: Dict[str, Any], doc_id: str) -> bool:
        """添加单篇文档（推荐使用），相同 doc_id 自动跳过。返回 True 表示新增成功。"""
        if not self.vectorstore:
            print("⚠️ RAG 未初始化，跳过 add_document")
            return False
        if doc_id in self._known_doc_ids:
            print(f"⏭️ Document already exists, skipped: {doc_id}")
            return False
        doc = Document(page_content=text, metadata={**metadata, "doc_id": doc_id})
        self.vectorstore.add_documents([doc])
        self.vectorstore.save_local(str(RAG_INDEX_PATH))
        self._known_doc_ids.add(doc_id)
        print(f"✅ Document added: {doc_id}")
        return True

    def add_documents(self, documents: List[Document]):
        """批量添加 Document 对象"""
        if not self.vectorstore:
            print("⚠️ RAG 未初始化，跳过 add_documents")
            return
        self.vectorstore.add_documents(documents)
        self.vectorstore.save_local(str(RAG_INDEX_PATH))
        print(f"✅ 已添加 {len(documents)} 篇文档")

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """语义检索，返回 Document 对象（带 metadata）。over-fetch 后截断避免过期文档挤掉有效结果。"""
        if not self.vectorstore:
            return []
        fetch_k = max(k * 3, k + 10)
        docs = self.vectorstore.similarity_search(query, k=fetch_k)
        filtered_docs: List[Document] = []
        for doc in docs:
            normalized = self._normalize_metadata(doc.metadata)
            if not self._is_not_expired(normalized):
                continue
            doc.metadata = normalized
            filtered_docs.append(doc)
        return filtered_docs[:k]

    def retrieve_with_scores(self, query: str, k: int = 5) -> List[FactDocument]:
        """
        返回带距离和相似度的检索结果。
        FAISS/LangChain 常见返回为 distance（越小越相关），这里统一转换为 similarity（越大越相关）。
        over-fetch 后截断避免过期文档挤掉有效结果。
        """
        if not self.vectorstore:
            return []
        fetch_k = max(k * 3, k + 10)
        docs_with_scores = self.vectorstore.similarity_search_with_score(query, k=fetch_k)
        results = []
        for doc, distance in docs_with_scores:
            normalized = self._normalize_metadata(doc.metadata)
            if not self._is_not_expired(normalized):
                continue
            distance = round(float(distance), 6)
            similarity = self._distance_to_similarity(distance)
            fact = FactDocument(
                doc=doc,
                distance=distance,
                similarity=similarity,
                metadata=normalized,
            )
            results.append(fact)
        return results[:k]

    @staticmethod
    def _distance_to_similarity(distance: float) -> float:
        """
        Normalize distance into [0, 1] similarity.
        0 distance -> 1 similarity; larger distance -> lower similarity.
        """
        safe_distance = max(0.0, float(distance))
        return round(1.0 / (1.0 + safe_distance), 6)

    @staticmethod
    def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize historical and ingestion metadata keys:
        - as_of_date/date
        - data_type/type
        Keep both aliases for backward compatibility.
        """
        raw = dict(metadata or {})
        as_of_date = raw.get("as_of_date") or raw.get("date") or ""
        data_type = raw.get("data_type") or raw.get("type") or ""

        normalized = {
            **raw,
            "symbol": raw.get("symbol", ""),
            "source": raw.get("source", "unknown"),
            "as_of_date": as_of_date,
            "date": as_of_date,
            "data_type": data_type,
            "type": data_type,
            "url": raw.get("url"),
            "confidence_tier": raw.get("confidence_tier", ""),
            "expires_at": raw.get("expires_at"),
        }
        return normalized

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def _is_not_expired(cls, metadata: Dict[str, Any]) -> bool:
        expires_at = metadata.get("expires_at")
        exp = cls._parse_iso_datetime(expires_at)
        if exp is None:
            return True
        return exp >= datetime.now(timezone.utc)

    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        """返回纯文本列表（兼容原有 tools/rag_tools.py）"""
        docs = self.retrieve(query_text, k=n_results)
        return [doc.page_content for doc in docs]


# ====================== 全局实例 ======================
retriever = RagRetriever()


def retrieve_knowledge(query_text: str, n_results: int = 3) -> List[str]:
    """供 Agent 工具调用的函数（保持完全兼容）"""
    return retriever.query(query_text, n_results=n_results)


# ====================== 启动提示 ======================
print(
    f"✅ rag/retriever.py → FAISS 本地离线 RAG | "
    f"模型: {_resolve_model_name()} | "
    f"索引路径: {RAG_INDEX_PATH}"
)