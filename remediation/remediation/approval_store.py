"""
Approval storage and management for remediation requests.

This module provides in-memory storage for approval decisions,
allowing developers to approve or reject proposed code changes.
"""

from datetime import datetime
from typing import Optional, Dict, List
from .models import (
    ApprovalDecision,
    ApprovalRecord,
    RemediationResponse,
    CodeChange,
)


class ApprovalStore:
    """
    In-memory store for approval decisions.

    This is a simple implementation for Milestone 6 Phase 1.
    In production, this would be backed by a database.
    """

    def __init__(self):
        self._approvals: Dict[str, ApprovalRecord] = {}
        self._responses: Dict[str, RemediationResponse] = {}

    def store_response(self, request_id: str, response: RemediationResponse) -> None:
        """Store a remediation response for later approval."""
        self._responses[request_id] = response

    def get_response(self, request_id: str) -> Optional[RemediationResponse]:
        """Get a stored remediation response."""
        return self._responses.get(request_id)

    def record_approval(
        self,
        request_id: str,
        decision: ApprovalDecision,
        reviewer: Optional[str] = None,
        feedback: Optional[str] = None,
        approved_changes: Optional[List[str]] = None,
        rejected_changes: Optional[List[str]] = None,
        feedback_category: Optional[str] = None,
        requires_rework: bool = False,
    ) -> ApprovalRecord:
        """
        Record an approval or rejection decision.

        Args:
            request_id: ID of the remediation request
            decision: APPROVED or REJECTED
            reviewer: Who made the decision (optional)
            feedback: Feedback on the decision (optional)
            approved_changes: List of finding_ids to approve (None = all)
            rejected_changes: List of finding_ids to reject (None = all for rejections)
            feedback_category: Category of feedback
            requires_rework: Whether rework is needed

        Returns:
            The created ApprovalRecord
        """
        response = self._responses.get(request_id)
        if not response:
            raise ValueError(f"No response found for request_id: {request_id}")

        # If no specific changes given, apply to all or none
        if approved_changes is None and decision == ApprovalDecision.APPROVED:
            approved_changes = [c.finding_id for c in response.changes]
        if rejected_changes is None and decision == ApprovalDecision.REJECTED:
            rejected_changes = [c.finding_id for c in response.changes]
        if approved_changes is None:
            approved_changes = []
        if rejected_changes is None:
            rejected_changes = []

        record = ApprovalRecord(
            request_id=request_id,
            decision=decision,
            reviewer=reviewer,
            feedback=feedback,
            approved_changes=approved_changes,
            rejected_changes=rejected_changes,
            timestamp=datetime.utcnow().isoformat(),
            applied=False,
            feedback_category=feedback_category,
            requires_rework=requires_rework,
        )

        self._approvals[request_id] = record
        return record

    def get_approval(self, request_id: str) -> Optional[ApprovalRecord]:
        """Get an approval record by request ID."""
        return self._approvals.get(request_id)

    def get_pending_requests(self) -> List[str]:
        """Get list of request IDs pending approval."""
        pending = []
        for request_id, response in self._responses.items():
            if request_id not in self._approvals and response.requires_approval:
                pending.append(request_id)
        return pending

    def get_approved_requests(self) -> List[str]:
        """Get list of request IDs that have been approved."""
        return [
            rid for rid, rec in self._approvals.items()
            if rec.decision == ApprovalDecision.APPROVED
        ]

    def get_rejected_requests(self) -> List[str]:
        """Get list of request IDs that have been rejected."""
        return [
            rid for rid, rec in self._approvals.items()
            if rec.decision == ApprovalDecision.REJECTED
        ]

    def mark_applied(self, request_id: str) -> None:
        """Mark an approved request as having changes applied."""
        if request_id in self._approvals:
            self._approvals[request_id].applied = True

    def get_changes_to_apply(self, request_id: str) -> List[CodeChange]:
        """
        Get the list of changes that should be applied for an approved request.

        Returns only the approved changes, not rejected ones.
        """
        record = self._approvals.get(request_id)
        response = self._responses.get(request_id)

        if not record or not response:
            return []

        if record.decision == ApprovalDecision.APPROVED:
            # All changes approved
            if not record.approved_changes:  # Approved all
                return response.changes
            return [c for c in response.changes if c.finding_id in record.approved_changes]

        if record.decision == ApprovalDecision.REJECTED:
            # Return only rejected changes for potential partial re-application
            if not record.rejected_changes:  # All rejected
                return []
            return []

        return []

    def clear_all(self) -> None:
        """Clear all stored approvals and responses (for testing)."""
        self._approvals.clear()
        self._responses.clear()


# Global instance (singleton pattern for simplicity)
_store: Optional[ApprovalStore] = None


def get_approval_store() -> ApprovalStore:
    """Get the global approval store instance."""
    global _store
    if _store is None:
        _store = ApprovalStore()
    return _store


def reset_approval_store() -> None:
    """Reset the global approval store (for testing)."""
    global _store
    if _store is not None:
        _store.clear_all()
    _store = ApprovalStore()