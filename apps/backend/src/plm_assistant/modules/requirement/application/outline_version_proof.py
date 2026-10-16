"""Requirement-owned current Approved version proof for SolutionOutline use.

This internal interface validates a fixed Requirement identity in the caller's
transaction. It never authorizes a user or exposes Requirement content.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from .prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
    PrototypeApprovedRequirementVersionProofPort,
)


class OutlineRequirementUseError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineApprovedRequirementProof:
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)
    review_id: uuid.UUID
    review_round_id: uuid.UUID


class OutlineRequirementUseProofService:
    def __init__(self, *, approved_versions: PrototypeApprovedRequirementVersionProofPort) -> None:
        if approved_versions is None:
            raise ValueError("approved RequirementVersion proof port required")
        self._approved = approved_versions

    def prove(self, transaction: object, *, project_id: uuid.UUID,
              requirement_id: uuid.UUID,
              requirement_version_id: uuid.UUID) -> OutlineApprovedRequirementProof:
        if (transaction is None or any(
                type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, requirement_id, requirement_version_id))):
            raise OutlineRequirementUseError("VALIDATION_FAILED")
        try:
            proven = self._approved.prove(
                transaction, project_id=project_id,
                requirement_id=requirement_id,
                requirement_version_id=requirement_version_id)
            if (type(proven) is not PrototypeApprovedRequirementVersionProof
                    or proven.project_id != project_id
                    or proven.requirement_id != requirement_id
                    or proven.requirement_version_id != requirement_version_id
                    or type(proven.version_no) is not int or proven.version_no < 1
                    or type(proven.content_fingerprint) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", proven.content_fingerprint) is None
                    or type(proven.review_id) is not uuid.UUID
                    or proven.review_id.int == 0
                    or type(proven.review_round_id) is not uuid.UUID
                    or proven.review_round_id.int == 0):
                raise OutlineRequirementUseError()
            return OutlineApprovedRequirementProof(
                project_id, requirement_id, requirement_version_id,
                proven.version_no, bytes.fromhex(proven.content_fingerprint),
                proven.review_id, proven.review_round_id)
        except OutlineRequirementUseError:
            raise
        except Exception:
            raise OutlineRequirementUseError() from None
