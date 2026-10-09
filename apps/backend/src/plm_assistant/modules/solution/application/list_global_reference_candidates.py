"""Internal-only GLOBAL candidate scan; this service does not authorize callers."""

from __future__ import annotations

import uuid
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from .prove_reference_use import (
    ReferenceUseProofError, ReferenceUseProofService, ReferenceUseQuery,
)


class GlobalReferenceCandidateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GlobalReferenceCandidate:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    display_label: str
    version_no: int
    eligibility_state: str


@dataclass(frozen=True, slots=True)
class GlobalReferenceCandidatePage:
    items: tuple[GlobalReferenceCandidate, ...]
    next_after_reference_solution_id: uuid.UUID | None
    has_more: bool


class CandidateRepository(Protocol):
    def scan(self, transaction: object, *,
             after_reference_solution_id: uuid.UUID | None,
             limit: int) -> GlobalReferenceCandidatePage: ...


class GlobalReferenceCandidateCatalog:
    """Caller must authorize Project/License before invoking in its transaction."""

    def __init__(self, *, repository: CandidateRepository,
                 proof: ReferenceUseProofService) -> None:
        if repository is None or proof is None:
            raise ValueError("GLOBAL candidate dependencies required")
        self._repository, self._proof = repository, proof

    def scan(self, transaction: object, *, trace_id: uuid.UUID,
             project_id: uuid.UUID,
             after_reference_solution_id: uuid.UUID | None = None,
             limit: int = 50) -> GlobalReferenceCandidatePage:
        if (transaction is None or not self._id(trace_id)
                or not self._id(project_id)
                or (after_reference_solution_id is not None
                    and not self._id(after_reference_solution_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise GlobalReferenceCandidateError("VALIDATION_FAILED")
        try:
            page = self._repository.scan(
                transaction, after_reference_solution_id=after_reference_solution_id,
                limit=limit)
            if (type(page) is not GlobalReferenceCandidatePage
                    or type(page.items) is not tuple
                    or len(page.items) > limit
                    or type(page.has_more) is not bool
                    or (page.has_more and not self._id(
                        page.next_after_reference_solution_id))
                    or (page.has_more
                        and after_reference_solution_id is not None
                        and page.next_after_reference_solution_id
                        <= after_reference_solution_id)
                    or (not page.has_more
                        and page.next_after_reference_solution_id is not None)):
                raise GlobalReferenceCandidateError()
            items: list[GlobalReferenceCandidate] = []
            previous = after_reference_solution_id
            for item in page.items:
                if (type(item) is not GlobalReferenceCandidate
                        or not self._id(item.reference_solution_id)
                        or not self._id(item.reference_version_id)
                        or (previous is not None
                            and item.reference_solution_id <= previous)
                        or type(item.display_label) is not str
                        or not 1 <= len(item.display_label) <= 160
                        or item.display_label != item.display_label.strip()
                        or not unicodedata.is_normalized("NFC", item.display_label)
                        or any(unicodedata.category(char) == "Cc"
                               for char in item.display_label)
                        or type(item.version_no) is not int
                        or item.version_no <= 0
                        or item.eligibility_state != "ELIGIBLE"):
                    raise GlobalReferenceCandidateError()
                previous = item.reference_solution_id
                if (page.has_more and item.reference_solution_id
                        > page.next_after_reference_solution_id):
                    raise GlobalReferenceCandidateError()
                try:
                    proved = self._proof.prove(transaction, ReferenceUseQuery(
                        trace_id, project_id, item.reference_solution_id,
                        item.reference_version_id, "GLOBAL"))
                except ReferenceUseProofError:
                    continue
                if (proved.reference_solution_id != item.reference_solution_id
                        or proved.reference_version_id != item.reference_version_id
                        or proved.scope != "GLOBAL"
                        or proved.target_project_id != project_id):
                    raise GlobalReferenceCandidateError()
                items.append(item)
            return GlobalReferenceCandidatePage(
                tuple(items), page.next_after_reference_solution_id, page.has_more)
        except GlobalReferenceCandidateError:
            raise
        except Exception:
            raise GlobalReferenceCandidateError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
