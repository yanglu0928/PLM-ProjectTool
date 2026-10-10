"""Compatibility adapter from the proven Handover owner to Workflow contract."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowCurrentQualificationQuery,
)

from .checklist_qualification import (
    ChecklistQualificationError,
    ChecklistQualificationEvidence,
    ChecklistQualificationReview,
    CurrentChecklistQualification,
    CurrentChecklistQualificationQuery,
)


_ITEMS = frozenset({"HANDOVER_BASELINE", "HANDOVER_ISSUES"})


class HandoverQualificationPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: HandoverWorkflowCurrentQualificationQuery,
    ) -> HandoverChecklistQualification: ...


class HandoverChecklistQualificationAdapter:
    def __init__(self, owner: HandoverQualificationPort) -> None:
        if owner is None or not callable(getattr(
                owner, "qualify_only_current_in_transaction", None)):
            raise ValueError("Handover qualification owner required")
        self._owner = owner

    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification:
        if (transaction is None
                or type(query) is not CurrentChecklistQualificationQuery
                or query.item_key not in _ITEMS):
            raise ChecklistQualificationError()
        query.__post_init__()
        try:
            result = self._owner.qualify_only_current_in_transaction(
                transaction, HandoverWorkflowCurrentQualificationQuery(
                    query.session_token, query.trace_id,
                    query.project_id, query.item_key,
                ),
            )
            if type(result) is not HandoverChecklistQualification:
                raise ChecklistQualificationError()
            result.__post_init__()
            review = result.review
            mapped = CurrentChecklistQualification(
                project_id=result.project_id,
                stage_key="HANDOVER",
                item_key=result.item_key,
                subject_type=review.subject_type,
                subject_id=review.subject_id,
                subject_version_id=result.handover_analysis_version_id,
                content_fingerprint=result.content_fingerprint,
                evidence=tuple(ChecklistQualificationEvidence(
                    value.evidence_id, value.project_id,
                    value.observed_lock_version, value.content_fingerprint,
                    value.verified_at,
                ) for value in result.evidence),
                review=ChecklistQualificationReview(
                    review.review_id, review.review_round_id,
                    review.project_id, review.subject_id,
                    review.subject_version_id, review.observed_lock_version,
                    review.subject_fingerprint, review.verified_at,
                    review.subject_type, review.policy_code,
                    review.observed_state,
                ),
            )
            mapped.__post_init__()
            return mapped
        except ChecklistQualificationError:
            raise
        except Exception:
            raise ChecklistQualificationError() from None
