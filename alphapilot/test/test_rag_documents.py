from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import retriever
from langchain_core.documents import Document

print("📚 正在向 RAG 知识库添加 TSLA 真实文档...")

documents = [
    Document(
        page_content="TSLA Q4 2024 Earnings: Record vehicle deliveries of 495,570 units. Energy storage deployment reached 11.0 GWh. Revenue $25.7B (+2% YoY). GAAP EPS declined 71% YoY due to ASP compression. Energy business achieved record gross profit.",
        metadata={"source": "TSLA_Q4_2024_Earnings", "type": "earnings"}
    ),
    Document(
        page_content="Tesla China sales in April 2025 increased 36% YoY, sixth consecutive monthly gain. Shanghai plant delivered 79,478 vehicles including exports. Stock broke above $400 on strong China demand.",
        metadata={"source": "China_Sales_April_2025", "type": "news"}
    ),
    Document(
        page_content="TSLA current technical indicators: RSI(14) 55.9 (neutral-bullish), MACD bullish crossover with expanding histogram. 20-day volatility 2.44%. 5-day gain +7.59%.",
        metadata={"source": "Technical_Analysis", "type": "market"}
    ),
]

for i, doc in enumerate(documents):
    doc_id = str(doc.metadata.get("source") or f"seed_doc_{i}")
    retriever.add_document(doc.page_content, dict(doc.metadata), doc_id)

print(f"✅ 已成功添加 {len(documents)} 条真实文档到 RAG 知识库！")
print("现在 Agent 可以检索这些知识了。")