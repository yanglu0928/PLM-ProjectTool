"""Internal immutable observations, not current Owner approval or a Gate verdict."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from ..domain.checklist_record import ChecklistRecordSnapshot
from ..domain.history import _uuid
from ..domain.transition import ChecklistState


class ChecklistRecordReadError(ValueError):
    def __init__(self) -> None:
        super().__init__("current Checklist record unavailable")


@dataclass(frozen=True, slots=True)
class ChecklistBasisObservation:
    ref_kind: str
    ref_id: UUID
    ref_scope: str
    ref_project_id: UUID | None
    observed_state: str
    observed_lock_version: int
    content_fingerprint: bytes
    verified_at: datetime
    proof_schema_version: int

    def __post_init__(self) -> None:
        states = {
            "EVIDENCE": ("CANDIDATE", "ELIGIBLE", "INELIGIBLE", "REVOKED"),
            "REVIEW_ROUND": ("PENDING", "IN_REVIEW", "APPROVED", "RETURNED", "WITHDRAWN"),
            "APPROVED_EXCEPTION": ("APPROVED",),
        }
        if (type(self.ref_kind) is not str or self.ref_kind not in states
                or not _uuid(self.ref_id)
                or self.observed_state not in states[self.ref_kind]
                or not (self.ref_scope == "PROJECT" and _uuid(self.ref_project_id)
                        or self.ref_scope == "GLOBAL" and self.ref_kind == "EVIDENCE"
                        and self.ref_project_id is None)
                or type(self.observed_lock_version) is not int
                or not 0 <= self.observed_lock_version < 2**63
                or type(self.content_fingerprint) is not bytes or len(self.content_fingerprint) != 32
                or type(self.verified_at) is not datetime or self.verified_at.tzinfo is None
                or self.verified_at.utcoffset() != timedelta(0)
                or type(self.proof_schema_version) is not int or self.proof_schema_version != 1):
            raise ChecklistRecordReadError()


@dataclass(frozen=True, slots=True)
class CurrentChecklistRecord:
    record: ChecklistRecordSnapshot
    basis: tuple[ChecklistBasisObservation, ...]
    content_fingerprint: bytes
    observed_stage_state: str
    current_workflow_version: int

    def __post_init__(self) -> None:
        if type(self.record) is not ChecklistRecordSnapshot:
            raise ChecklistRecordReadError()
        # Revalidate nested immutable values, including objects constructed outside __init__.
        try:
            self.record.__post_init__()
        except ValueError:
            raise ChecklistRecordReadError() from None
        if (type(self.basis) is not tuple
                or any(type(ref) is not ChecklistBasisObservation for ref in self.basis)
                or type(self.content_fingerprint) is not bytes or len(self.content_fingerprint) != 32
                or self.observed_stage_state not in ("ACTIVE", "BLOCKED")
                or type(self.current_workflow_version) is not int
                or not self.record.after_workflow_version <= self.current_workflow_version < 2**63):
            raise ChecklistRecordReadError()
        identities = set()
        for ref in self.basis:
            ref.__post_init__()
            identity = (ref.ref_kind, ref.ref_id)
            if identity in identities or ref.ref_scope == "PROJECT" and ref.ref_project_id != self.record.project_id:
                raise ChecklistRecordReadError()
            identities.add(identity)
            if self.record.result in (ChecklistState.PASS, ChecklistState.WAIVED):
                expected = "ELIGIBLE" if ref.ref_kind == "EVIDENCE" else "APPROVED"
                if ref.observed_state != expected:
                    raise ChecklistRecordReadError()
        for kind, expected in (
                ("EVIDENCE", self.record.evidence_refs),
                ("REVIEW_ROUND", self.record.review_round_refs),
                ("APPROVED_EXCEPTION", self.record.exception_refs)):
            if tuple(ref.ref_id for ref in self.basis if ref.ref_kind == kind) != expected:
                raise ChecklistRecordReadError()


class CurrentChecklistRecordPort(Protocol):
    """Caller must authenticate/authorize/License-check before supplying its transaction.

    None means missing scoped identity or untouched PENDING. A changed projection
    without a complete matching chain raises ChecklistRecordReadError, never None/PASS.
    Implementations do not commit or initialize; observations still need Owner reproof.
    """
    def get(self, transaction: object, project_id: UUID, workflow_id: UUID,
            item_key: str) -> CurrentChecklistRecord | None: ...
