"""3.3.2 Audit trail — [doc:N] marker extraction from final report.
Standalone module (no LLM/graph deps) — safe to import in tests.
"""
from __future__ import annotations

import re
from typing import Any


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
    for n_str in markers:
        try:
            n = int(n_str) - 1  # 转为 0-based index
            if n < 0 or n >= len(doc_evidence) or n in seen_n:
                continue
            seen_n.add(n)
            doc_markers.append(f"doc:{int(n_str)}")
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
        except (ValueError, IndexError):
            continue

    # 2) 兜底：无 [doc:N] 时，保存当时所有 document_evidence 的 chunk_id
    if not chunk_ids and doc_evidence:
        for dc in doc_evidence:
            if isinstance(dc, dict) and dc.get("chunk_id"):
                chunk_ids.append(dc["chunk_id"])
                evidence_snapshot.append({
                    "chunk_id": dc["chunk_id"],
                    "doc_id": dc.get("doc_id", ""),
                    "section": dc.get("section", ""),
                    "source": dc.get("source", ""),
                })

    return {
        "chunk_ids": chunk_ids,
        "doc_markers": doc_markers or None,
        "evidence_snapshot": evidence_snapshot or None,
    }
