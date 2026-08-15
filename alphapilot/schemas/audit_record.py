from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.approval import ApprovalStatus, PublicationStatus


class AuditRecord(BaseModel):
    """
    Unified AI audit trail for one analysis request.

    Demo-grade contract aligned with the Day-1 SFC governance proposal.
    Do not store API keys, passwords, tokens, or unredacted personal data.
    """

    request_id: str = Field(description="Stable id for this HTTP/analysis request")
    analysis_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[int] = None

    timestamp_started: str = ""
    timestamp_completed: Optional[str] = None

    use_case: str = "ai_assisted_investment_research"
    stock_symbol: str = ""

    data_sources: list[str] = Field(default_factory=list)
    retrieved_document_ids: list[str] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)

    evidence_packet_snapshot: Optional[dict[str, Any]] = None

    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None

    generated_output: Optional[str] = None
    citation_validation: Optional[dict[str, Any]] = None
    guard_result: Optional[dict[str, Any]] = None
    risk_flags: list[str] = Field(default_factory=list)

    human_reviewer: Optional[str] = None
    review_comments: Optional[str] = None
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    approval_timestamp: Optional[str] = None
    publication_status: PublicationStatus = PublicationStatus.NOT_PUBLISHED
    kill_switch_status: str = Field(
        default="enabled",
        description="enabled | output_paused | publication_paused",
    )


__all__ = [
    "AuditRecord",
]
