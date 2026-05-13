import os
from pathlib import Path
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

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
        else:
            print("🆕 创建新的 FAISS 索引...")
            self.vectorstore = FAISS.from_texts(
                ["[Placeholder] AlphaPilot RAG 初始化文档"],
                self.embedding_model,
                metadatas=[{"source": "init", "type": "placeholder"}],
            )
            self.vectorstore.save_local(str(RAG_INDEX_PATH))

    def add_document(self, text: str, metadata: Dict[str, Any], doc_id: str):
        """添加单篇文档（推荐使用）"""
        if not self.vectorstore:
            print("⚠️ RAG 未初始化，跳过 add_document")
            return
        doc = Document(page_content=text, metadata={**metadata, "doc_id": doc_id})
        self.vectorstore.add_documents([doc])
        self.vectorstore.save_local(str(RAG_INDEX_PATH))
        print(f"✅ Document added: {doc_id}")

    def add_documents(self, documents: List[Document]):
        """批量添加 Document 对象"""
        if not self.vectorstore:
            print("⚠️ RAG 未初始化，跳过 add_documents")
            return
        self.vectorstore.add_documents(documents)
        self.vectorstore.save_local(str(RAG_INDEX_PATH))
        print(f"✅ 已添加 {len(documents)} 篇文档")

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """语义检索，返回 Document 对象（带 metadata）"""
        if not self.vectorstore:
            return []
        return self.vectorstore.similarity_search(query, k=k)

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