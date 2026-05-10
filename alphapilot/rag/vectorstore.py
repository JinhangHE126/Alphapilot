import chromadb
import os
from typing import List

from rag.embeddings_google import ChromaGoogleEmbeddingFunction


class FinancialRAG:
    """Financial report RAG retrieval module.
        这段代码实现了一个金融财报领域的 RAG 检索系统：
        使用 ChromaDB 作为本地向量数据库，负责存储文本与向量，为大模型提供长期记忆和外部知识库。
        采用 OpenAI 的 text-embedding-3-small 模型将文本转化为向量。
        创建了一个名为 financial_reports 的集合（相当于数据库表）用于统一管理财报数据。
        提供两个核心方法：
        add_document: 添加财报文本、元数据与唯一 ID 到向量库
        query: 根据用户问题做语义检索,返回最相关的内容
        最后创建了全局 RAG 实例，方便直接调用。
        当前缺失：删除文档的功能。
    
    """
    
    def __init__(self, persist_directory="./rag_data"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(path=persist_directory)
        # 初始化 Google Gemini Embedding Function
        self.embedding_function = ChromaGoogleEmbeddingFunction()
        
        # 创建或获取 Collection
        self.collection = self.client.get_or_create_collection(
            name="financial_reports",
            embedding_function=self.embedding_function
        )

    def add_document(self, text: str, metadata: dict, doc_id: str):
        """Add a document to the vector store."""
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        print(f"Document added: {doc_id}")

    def query(self, query_text: str, n_results: int = 3) -> List[str]:
        """Retrieve the most relevant content."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results['documents'][0] if results['documents'] else []

# 初始化全局 RAG 实例
rag = FinancialRAG()