"""Evidence Packet 文档证据加载（workflow 与测试共用）。"""
from __future__ import annotations

from schemas.evidence_packet import DocumentChunk, EvidencePacket
from rag.retriever import retriever


def attach_document_evidence(
    packet: EvidencePacket,
    symbol: str,
    query: str,
    k: int = 5,
    user_session_id: str = "",
    doc_type: str = "",
) -> EvidencePacket:
    """
    检索 document_chunk 并写入 packet.document_evidence。
    doc_type: 可选后过滤（"annual_report" / "earnings_call" / "news"），空串=不过滤。
    失败时保持 document_evidence 为空，不抛异常。
    """
    try:
        doc_results = retriever.hybrid_retrieve(
            query=query,
            symbol=symbol,
            k=k,
            user_session_id=user_session_id,
            doc_type=doc_type,
        )
        print(f"📊 attach_document_evidence: symbol={symbol}, results={len(doc_results)}")
        if doc_results:
            packet.document_evidence = [
                DocumentChunk(
                    chunk_id=dc.get("chunk_id", ""),
                    content=dc.get("content", ""),
                    source=dc.get("source", "unknown"),
                    doc_id=dc.get("doc_id", ""),
                    doc_type=dc.get("doc_type", ""),
                    section=dc.get("section", ""),
                    page=dc.get("page", ""),
                    publish_date=dc.get("publish_date", ""),
                    report_period=dc.get("report_period", ""),
                    symbol=dc.get("symbol", ""),
                    contains_table=bool(dc.get("contains_table", False)),
                    language=dc.get("language", ""),
                    confidence_tier=dc.get("confidence_tier", ""),
                )
                for dc in doc_results
            ]
            packet.coverage.document_evidence = "available"
    except Exception:
        packet.document_evidence = []
        packet.coverage.document_evidence = "missing"
    return packet
