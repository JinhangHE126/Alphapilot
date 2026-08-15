"""3.3.2 Audit trail — [doc:N] marker extraction from final report.
Standalone module (no LLM/graph deps) — safe to import in tests.
"""
from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_citations(
    final_report: str,
    evidence_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    从 final_report 中正则提取 [doc:N]，映射 evidence_packet.document_evidence[N-1]。
    返回 {chunk_ids, doc_markers, evidence_snapshot}。
    """
    chunk_ids: list[str] = []
    doc_markers: list[str] = []
    evidence_snapshot: list[dict[str, Any]] = []
    invalid_citations: list[str] = []

    # 提取文档证据列表
    doc_evidence = []
    if evidence_packet and isinstance(evidence_packet, dict):
        de = evidence_packet.get("document_evidence", [])
        if isinstance(de, list):
            doc_evidence = de

    # 1) 正则提取 [doc:N] 标记（大小写不敏感，允许空格在冒号前后）
    marker_pattern = re.compile(r"\[doc\s*:\s*(\d+)\]", re.IGNORECASE)
    markers = marker_pattern.findall(final_report or "")
    seen_n = set()
    seen_invalid = set()
    for n_str in markers:
        try:
            marker_num = int(n_str)
            marker_id = f"doc:{marker_num}"
            n = marker_num - 1  # 转为 0-based index
            if n < 0 or n >= len(doc_evidence):
                logger.warning(
                    "Skipping out-of-range [doc:%s]; document_evidence has %s chunk(s)",
                    n_str,
                    len(doc_evidence),
                )
                if marker_id not in seen_invalid:
                    invalid_citations.append(marker_id)
                    seen_invalid.add(marker_id)
                continue
            if n in seen_n:
                continue
            seen_n.add(n)
            doc_markers.append(marker_id)
            dc = doc_evidence[n]
            if isinstance(dc, dict):
                chunk_id = dc.get("chunk_id", "")
                if chunk_id:
                    chunk_ids.append(chunk_id)
                    evidence_snapshot.append({
                        "chunk_id": chunk_id,
                        "doc_id": dc.get("doc_id", ""),
                        "section": dc.get("section", ""),
                        "source": dc.get("source", ""),
                    })
                elif marker_id not in seen_invalid:
                    invalid_citations.append(marker_id)
                    seen_invalid.add(marker_id)
        except (ValueError, IndexError):
            continue

    has_docs = bool(doc_evidence)
    missing_citations = has_docs and not chunk_ids
    validation_ok = (not invalid_citations) and (not missing_citations)

    return {
        "chunk_ids": chunk_ids,
        "doc_markers": doc_markers or None,
        "evidence_snapshot": evidence_snapshot or None,
        "validation": {
            "ok": validation_ok,
            "missing_citations": missing_citations,
            "invalid_citations": invalid_citations,
            "cited_count": len(chunk_ids),
            "retrieved_count": len(doc_evidence),
        },
    }
