"""Apply MisGen-style evidence perturbations to an EvidencePacket (research pilot)."""
from __future__ import annotations

from typing import Any

from schemas.evidence_packet import ConfidenceTier, DocumentChunk, EvidencePacket, Fact


def apply_evidence_attack(packet: EvidencePacket, attack: dict[str, Any]) -> dict[str, Any]:
    """
    Mutate *packet* in place per attack config.

    Supported attack["type"]:
      - news_headline: patch or append facts[] entry with field news_headline
      - document_chunk: replace document_evidence[].content for chunk_id

    Returns metadata dict for logging (injected fields, MER inputs).
    """
    if not attack:
        return {"applied": False}

    attack_type = attack.get("type", "")
    meta: dict[str, Any] = {
        "applied": False,
        "attack_id": attack.get("attack_id", ""),
        "stimulus_id": attack.get("stimulus_id", ""),
        "candidate_id": attack.get("candidate_id", ""),
        "type": attack_type,
    }

    if attack_type == "news_headline":
        text = str(attack.get("text", "")).strip()
        if not text:
            return meta
        patched = False
        for fact in packet.facts:
            if fact.field == "news_headline":
                fact.value = text
                fact.source = attack.get("source", "research_injected")
                fact.confidence = float(attack.get("confidence", 0.85))
                fact.confidence_tier = ConfidenceTier.LLM_EXTRACTED
                patched = True
                break
        if not patched:
            packet.facts.append(
                Fact(
                    field="news_headline",
                    value=text,
                    unit="text",
                    period="latest",
                    source=attack.get("source", "research_injected"),
                    as_of_date=packet.as_of_date or packet.generated_at[:10],
                    confidence=float(attack.get("confidence", 0.85)),
                    confidence_tier=ConfidenceTier.LLM_EXTRACTED,
                )
            )
        packet.coverage.news_data = "available"
        meta.update({"applied": True, "news_headline_patched": True})
        return meta

    if attack_type == "document_chunk":
        chunk_id = attack.get("chunk_id", "")
        text = str(attack.get("text", "")).strip()
        if not chunk_id or not text:
            return meta
        replaced = False
        for dc in packet.document_evidence:
            if dc.chunk_id == chunk_id:
                dc.content = text
                dc.confidence_tier = ""
                replaced = True
                break
        if not replaced:
            packet.document_evidence.insert(
                0,
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=text,
                    source=attack.get("source", "SEC"),
                    doc_id=attack.get("doc_id", ""),
                    doc_type=attack.get("doc_type", "annual_report"),
                    section=attack.get("section", "Risk Factors"),
                    page=attack.get("page", ""),
                    publish_date=attack.get("publish_date", ""),
                    report_period=attack.get("report_period", ""),
                    symbol=packet.symbol,
                    contains_table=False,
                    language="en",
                    confidence_tier="",
                ),
            )
            # Keep at most k=5 chunks if caller attached 5
            if len(packet.document_evidence) > 5:
                packet.document_evidence = packet.document_evidence[:5]
        meta.update({"applied": True, "chunk_id": chunk_id, "chunk_replaced": replaced})
        return meta

    meta["error"] = f"unsupported attack type: {attack_type}"
    return meta


def compute_mer(packet: EvidencePacket | dict, attack_meta: dict[str, Any]) -> float:
    """Estimate MER from evidence packet size and injection type."""
    if isinstance(packet, dict):
        doc_ev = packet.get("document_evidence", []) or []
    else:
        doc_ev = packet.document_evidence

    n_docs = len(doc_ev) or 1
    attack_type = attack_meta.get("type", "")

    if attack_type == "document_chunk" and attack_meta.get("applied"):
        return round(1.0 / n_docs, 4)

    if attack_type == "news_headline" and attack_meta.get("applied"):
        if isinstance(packet, dict) and not packet.get("document_evidence"):
            return 0.2
        return round(1.0 / n_docs, 4)

    return 0.0
