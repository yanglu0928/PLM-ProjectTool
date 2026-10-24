"""Same-transaction complete Requirement coverage by current approved Sections.

The caller owns the transaction. This internal Owner does not persist a
validation result or turn a historical approval into a current fact.
"""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.requirement.application.approved_inventory import (
    ApprovedRequirementInventory,
    ApprovedRequirementInventoryError,
    CurrentApprovedRequirement,
    ExplainedRequirementExclusion,
    MAX_INVENTORY_ROOTS,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadQuery,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState

from .outline_version_history import OutlineVersionHistoryView
from .outline_version_input import OutlineRequirementRef
from .outline_version_validation_contract import (
    OutlineVersionValidationContractError,
    OutlineVersionValidationSnapshot,
    ValidateOutlineVersion,
)
from .read_section import SectionCurrentView
from .read_section_version import SectionVersionHistoryView
from .section_version_input import SectionRequirementRef
from .section_version_validation_contract import (
    SectionCurrentFactQuery,
    SectionVersionValidationFacts,
)


class OutlineCoverageProofError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_COVERAGE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CurrentOutlineCoverageProof:
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID
    solution_outline_version_id: uuid.UUID
    requirement_refs: tuple[OutlineRequirementRef, ...]
    section_version_ids: tuple[uuid.UUID, ...]
    requirement_scope_fingerprint: bytes


class ApprovedInventoryPort(Protocol):
    def prove_in_transaction(
        self, transaction: object, query: RequirementVersionReadQuery,
    ) -> ApprovedRequirementInventory: ...


class SectionCurrentPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None: ...


class SectionVersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...


class ReviewRoundPort(Protocol):
    def get_round(self, transaction: object, scope: str,
                  project_id: uuid.UUID | None, review_id: uuid.UUID,
                  round_id: uuid.UUID) -> FixedReviewRoundSnapshot | None: ...


class SectionCurrentFactsPort(Protocol):
    def facts(self, transaction: object, *, command: SectionCurrentFactQuery,
              version: SectionVersionHistoryView) -> SectionVersionValidationFacts: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class OutlineCoverageProofService:
    """Prove exact, currently eligible Section union against the full scope."""

    def __init__(self, *, inventory: ApprovedInventoryPort,
                 sections: SectionCurrentPort, versions: SectionVersionPort,
                 reviews: ReviewRoundPort,
                 current: SectionCurrentFactsPort) -> None:
        if any(value is None for value in (
                inventory, sections, versions, reviews, current)):
            raise ValueError("Outline coverage dependencies required")
        self._inventory = inventory
        self._sections = sections
        self._versions = versions
        self._reviews = reviews
        self._current = current

    def prove(self, transaction: object, *, command: ValidateOutlineVersion,
              version: OutlineVersionHistoryView) -> CurrentOutlineCoverageProof:
        if (transaction is None or type(command) is not ValidateOutlineVersion
                or type(version) is not OutlineVersionHistoryView
                or (version.project_id, version.solution_outline_id,
                    version.solution_outline_version_id) != (
                        command.project_id, command.solution_outline_id,
                        command.solution_outline_version_id)
                or version.version_state != "DRAFT"):
            raise OutlineCoverageProofError()
        try:
            command.__post_init__()
            self._fixed_input(version)
            inventory = self._inventory.prove_in_transaction(
                transaction, RequirementVersionReadQuery(
                    command.session_token, command.trace_id, command.project_id,
                ),
            )
            expected = self._inventory_refs(inventory, command.project_id)
            fixed = {(ref.requirement_id, ref.requirement_version_id)
                     for ref in version.requirement_refs}
            if fixed != expected:
                raise OutlineCoverageProofError("SOLUTION_COVERAGE_INCOMPLETE")
            covered: set[tuple[uuid.UUID, uuid.UUID]] = set()
            section_versions: list[uuid.UUID] = []
            for section_id in version.section_ids:
                section = self._sections.get_current(
                    transaction, project_id=command.project_id,
                    section_id=section_id,
                )
                if (type(section) is not SectionCurrentView
                        or section.project_id != command.project_id
                        or section.solution_outline_id != command.solution_outline_id
                        or section.solution_section_id != section_id
                        or section.section_state != "ACTIVE"
                        or not _id(section.current_approved_version_ref)):
                    raise OutlineCoverageProofError()
                current_version = self._versions.get(
                    transaction, project_id=command.project_id,
                    section_id=section_id,
                    version_id=section.current_approved_version_ref,
                )
                current_version = self._approved_version(
                    transaction, command, section_id, current_version,
                    section.current_approved_version_ref,
                )
                section_versions.append(current_version.solution_section_version_id)
                for ref in current_version.requirement_refs:
                    if (type(ref) is not SectionRequirementRef
                            or not _id(ref.requirement_id)
                            or not _id(ref.requirement_version_id)):
                        raise OutlineCoverageProofError()
                    pair = (ref.requirement_id, ref.requirement_version_id)
                    if pair not in expected:
                        raise OutlineCoverageProofError(
                            "SOLUTION_COVERAGE_INCOMPLETE")
                    covered.add(pair)
            if covered != expected:
                raise OutlineCoverageProofError("SOLUTION_COVERAGE_INCOMPLETE")
            return CurrentOutlineCoverageProof(
                command.project_id, command.solution_outline_id,
                command.solution_outline_version_id,
                version.requirement_refs, tuple(section_versions),
                inventory.scope_fingerprint,
            )
        except OutlineCoverageProofError:
            raise
        except ApprovedRequirementInventoryError as exc:
            if exc.code in ("LICENSE_OPERATION_DENIED", "AUTH_ACCESS_DENIED"):
                raise OutlineCoverageProofError(exc.code) from None
            raise OutlineCoverageProofError() from None
        except Exception:
            raise OutlineCoverageProofError() from None

    @staticmethod
    def _fixed_input(version: OutlineVersionHistoryView) -> None:
        sections, requirements = version.section_ids, version.requirement_refs
        if (type(sections) is not tuple or not 1 <= len(sections) <= 100
                or any(not _id(value) for value in sections)
                or len(set(sections)) != len(sections)
                or type(requirements) is not tuple
                or not 1 <= len(requirements) <= 500
                or any(type(value) is not OutlineRequirementRef
                       or not _id(value.requirement_id)
                       or not _id(value.requirement_version_id)
                       for value in requirements)
                or len({value.requirement_id for value in requirements})
                   != len(requirements)
                or len({value.requirement_version_id for value in requirements})
                   != len(requirements)):
            raise OutlineCoverageProofError()
        try:
            OutlineVersionValidationSnapshot(
                version.project_id, version.solution_outline_id,
                version.solution_outline_version_id, version.version_no,
                version.version_state, version.content_fingerprint,
                len(sections), len(requirements), len(version.reference_refs),
            )
        except (OutlineVersionValidationContractError, TypeError, AttributeError):
            raise OutlineCoverageProofError() from None

    @staticmethod
    def _inventory_refs(inventory: object, project_id: uuid.UUID
                        ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        if (type(inventory) is not ApprovedRequirementInventory
                or inventory.project_id != project_id
                or not 1 <= inventory.root_count <= MAX_INVENTORY_ROOTS
                or type(inventory.approved) is not tuple
                or not inventory.approved
                or type(inventory.explained) is not tuple
                or inventory.root_count
                   != len(inventory.approved) + len(inventory.explained)
                or type(inventory.scope_fingerprint) is not bytes
                or len(inventory.scope_fingerprint) != 32):
            raise OutlineCoverageProofError()
        refs = set()
        for value in inventory.approved:
            if (type(value) is not CurrentApprovedRequirement
                    or not _id(value.requirement_id)
                    or not _id(value.requirement_version_id)
                    or type(value.content_fingerprint) is not bytes
                    or len(value.content_fingerprint) != 32
                    or not _id(value.review_id)
                    or not _id(value.review_round_id)):
                raise OutlineCoverageProofError()
            refs.add((value.requirement_id, value.requirement_version_id))
        if (len(refs) != len(inventory.approved)
                or len({item[0] for item in refs}) != len(refs)
                or len({item[1] for item in refs}) != len(refs)
                or any(type(item) is not ExplainedRequirementExclusion
                       or not _id(item.requirement_id)
                       or item.requirement_state not in (
                           "DEFERRED", "REJECTED", "ARCHIVED")
                       or not _id(item.decision_id)
                       for item in inventory.explained)
                or len({item.requirement_id for item in inventory.explained})
                   != len(inventory.explained)
                or {item.requirement_id for item in inventory.explained}
                   & {item[0] for item in refs}):
            raise OutlineCoverageProofError()
        return refs

    def _approved_version(self, transaction: object,
                          command: ValidateOutlineVersion, section_id: uuid.UUID,
                          version: object, version_id: uuid.UUID
                          ) -> SectionVersionHistoryView:
        if (type(version) is not SectionVersionHistoryView
                or version.project_id != command.project_id
                or version.solution_section_id != section_id
                or version.solution_section_version_id != version_id
                or version.version_state != "APPROVED"
                or not _id(version.review_ref)
                or not _id(version.review_round_ref)
                or type(version.content_fingerprint) is not bytes
                or len(version.content_fingerprint) != 32):
            raise OutlineCoverageProofError()
        fixed = self._reviews.get_round(
            transaction, "PROJECT", command.project_id,
            version.review_ref, version.review_round_ref,
        )
        if type(fixed) is not FixedReviewRoundSnapshot:
            raise OutlineCoverageProofError()
        fixed.__post_init__()
        identity = fixed.review
        if (identity.review_id != version.review_ref
                or identity.scope != "PROJECT"
                or identity.project_id != command.project_id
                or identity.subject_type != "SOL-05"
                or identity.subject_id != section_id
                or identity.policy_code != "SOLUTION_SECTION_ALL_V1"
                or identity.state != "APPROVED"
                or fixed.progress.round_id != version.review_round_ref
                or fixed.progress.state is not ReviewRoundState.APPROVED
                or fixed.subject_version_id != version_id
                or not hmac.compare_digest(
                    fixed.subject_fingerprint, version.content_fingerprint)):
            raise OutlineCoverageProofError()
        facts = self._current.facts(
            transaction, command=SectionCurrentFactQuery(
                command.session_token, command.trace_id,
                command.project_id, section_id, version_id,
            ), version=version,
        )
        if type(facts) is not SectionVersionValidationFacts:
            raise OutlineCoverageProofError()
        statuses = tuple(getattr(facts, name) for name in (
            "integrity", "content", "requirements", "evidence", "trace", "spec"))
        if any(status == "FAIL" for status in statuses):
            raise OutlineCoverageProofError("SOLUTION_COVERAGE_INCOMPLETE")
        if any(status != "PASS" for status in statuses):
            raise OutlineCoverageProofError()
        return version
