from __future__ import annotations

import uuid

from knowledge.ingestion import should_ingest, extract_records, IngestionRecord
from schemas.evidence_packet import EvidencePacket, ConfidenceTier
from rag.retriever import retriever as vectorstore


def upsert_packet(packet: EvidencePacket) -> dict:
    result = {
        "symbol": packet.symbol,
        "ingested": 0,
        "skipped": 0,
        "records": [],
    }

    if not should_ingest(packet):
        result["skipped"] = -1
        result["reason"] = f"evidence_score {packet.evidence_score} < 50"
        return result

    records = extract_records(packet)
    for record in records:
        doc_id = _make_doc_id(record)
        metadata = {
            "symbol": record.symbol,
            "field": record.field,
            "source": record.source,
            "data_type": record.data_type,
            "confidence_tier": record.confidence_tier,
            "as_of_date": record.as_of_date,
            "ingested_at": record.ingested_at,
            "expires_at": record.expires_at,
        }
        text = f"{record.field}: {record.value} (source: {record.source}, date: {record.as_of_date})"

        try:
            if vectorstore.add_document(text=text, metadata=metadata, doc_id=doc_id):
                result["ingested"] += 1
                result["records"].append({"field": record.field, "source": record.source})
            else:
                result["skipped"] += 1
        except Exception as exc:
            result["skipped"] += 1
            result.setdefault("errors", []).append(str(exc))

    try:
        from db.fact_store import get_fact_store
        store = get_fact_store()
        for fact in packet.facts:
            if fact.confidence_tier == ConfidenceTier.LLM_INFERRED:
                continue
            store.upsert_fact(packet.symbol, fact)
        result["fact_store_written"] = True
    except Exception as exc:
        result["fact_store_written"] = False
        result.setdefault("errors", []).append(f"fact_store: {exc}")

    try:
        import json
        from db.document_store import get_document_store
        doc_store = get_document_store()
        raw_json = packet.model_dump_json(indent=2).encode("utf-8")
        doc_id = doc_store.upsert(
            symbol=packet.symbol,
            doc_type="evidence_packet",
            fmt="json",
            source="evidence_packet_builder",
            content=raw_json,
            as_of_date=packet.as_of_date,
            title=f"Evidence Packet {packet.symbol} {packet.as_of_date}",
        )
        if doc_id is not None:
            result["document_id"] = doc_id
            result["document_stored"] = True
    except Exception as exc:
        result["document_stored"] = False
        result.setdefault("errors", []).append(f"document_store: {exc}")

    return result


def _make_doc_id(record: IngestionRecord) -> str:
    unique = f"{record.symbol}_{record.field}_{record.source}_{record.as_of_date}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, unique).hex


__all__ = ["upsert_packet"]