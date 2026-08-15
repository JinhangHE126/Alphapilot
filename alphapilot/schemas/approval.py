from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Human review lifecycle for an AI-generated research report."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class PublicationStatus(str, Enum):
    """Whether an approved report has been released."""

    NOT_PUBLISHED = "not_published"
    PUBLISHED = "published"


class ApprovalRecord(BaseModel):
    """
    Approval state for a single analysis.

    Status transitions are enforced later in governance/approvals.py;
    this schema only defines the allowed values and payload shape.
    """

    analysis_id: int = Field(description="FK to analysis_history.id")
    status: ApprovalStatus = ApprovalStatus.DRAFT
    publication_status: PublicationStatus = PublicationStatus.NOT_PUBLISHED
    human_reviewer: Optional[str] = Field(
        default=None,
        description="Reviewer identity; required before approve/reject",
    )
    review_comments: Optional[str] = None
    approval_timestamp: Optional[str] = Field(
        default=None,
        description="ISO or SQLite datetime string when status last changed",
    )


__all__ = [
    "ApprovalStatus",
    "PublicationStatus",
    "ApprovalRecord",
]
