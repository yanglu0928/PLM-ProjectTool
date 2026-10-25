"""Read-only, same-transaction proof of the current approved Solution inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.solution.application.outline_version_history import (
    OutlineVersionHistoryView,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery, OutlineVersionValidationFacts,
)
from plm_assistant.modules.solution.application.prove_outline_coverage import (
    CurrentOutlineCoverageProof,
)
from plm_assistant.modules.solution.application.read_outline import (
    OutlineCurrentView,
)
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_version_input import (
    is_normalized_spec_basis,
)
from plm_assistant.modules.solution.application.qualify_section_structured_spec import (
    QualifiedSectionStructuredSpec,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineRequirementRef,
)


class ApprovedSolutionInputProofError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PLAN_SOURCE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class ApprovedSectionInput:
    section_id: uuid.UUID
    section_version_id: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    spec_binding_state: str
    qualified_specs: tuple[QualifiedSectionStructuredSpec, ...]


@dataclass(frozen=True, slots=True)
class ApprovedSolutionInputProof:
    project_id: uuid.UUID
    outline_id: uuid.UUID
    outline_version_id: uuid.UUID
    outline_content_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[OutlineRequirementRef, ...]
    sections: tuple[ApprovedSectionInput, ...]
    requirement_scope_fingerprint: bytes = field(repr=False)


class OutlinePort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID) -> OutlineCurrentView | None: ...


class OutlineVersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            outline_id: uuid.UUID,
            version_id: uuid.UUID) -> OutlineVersionHistoryView | None: ...


class ReviewPort(Protocol):
    def get_round(self, transaction: object, scope: str,
                  project_id: uuid.UUID | None, review_id: uuid.UUID,
                  round_id: uuid.UUID) -> FixedReviewRoundSnapshot | None: ...


class CurrentFactsPort(Protocol):
    def facts(self, transaction: object, *, command: OutlineCurrentFactQuery,
              version: OutlineVersionHistoryView
              ) -> OutlineVersionValidationFacts: ...


class CoveragePort(Protocol):
    def prove(self, transaction: object, *, command: OutlineCurrentFactQuery,
              version: OutlineVersionHistoryView,
              approved_outline_review: FixedReviewRoundSnapshot | None = None
              ) -> CurrentOutlineCoverageProof: ...


class SectionVersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...


class SpecQualificationPort(Protocol):
    def prove_current(self, transaction: object, *,
                      version: SectionVersionHistoryView
                      ) -> tuple[QualifiedSectionStructuredSpec, ...]: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


class ApprovedSolutionInputProofService:
    """Combine existing Solution Owners without granting access or writing data.

    The caller must authorize its current Session, Project, role and License
    before invoking this service and pass its live transaction and query.
    """

    def __init__(self, *, outlines: OutlinePort,
                 versions: OutlineVersionPort, reviews: ReviewPort,
                 current_facts: CurrentFactsPort, coverage: CoveragePort,
                 sections: SectionVersionPort,
                 spec_qualification: SpecQualificationPort) -> None:
        if any(value is None for value in (
                outlines, versions, reviews, current_facts, coverage,
                sections, spec_qualification)):
            raise ValueError("approved Solution input proof dependencies required")
        self._outlines, self._versions, self._reviews = outlines, versions, reviews
        self._current_facts, self._coverage = current_facts, coverage
        self._sections, self._specs = sections, spec_qualification

    def prove(self, transaction: object, *, command: OutlineCurrentFactQuery
              ) -> ApprovedSolutionInputProof:
        if (transaction is None or type(command) is not OutlineCurrentFactQuery
                or not all(_id(value) for value in (
                    command.trace_id, command.project_id,
                    command.solution_outline_id,
                    command.solution_outline_version_id))):
            raise ApprovedSolutionInputProofError()
        try:
            command.__post_init__()
            root = self._outlines.get_current(
                transaction, project_id=command.project_id,
                outline_id=command.solution_outline_id)
            if (type(root) is not OutlineCurrentView
                    or root.project_id != command.project_id
                    or root.solution_outline_id != command.solution_outline_id
                    or root.outline_state != "ACTIVE"
                    or root.current_approved_version_ref
                       != command.solution_outline_version_id):
                raise ApprovedSolutionInputProofError()
            version = self._versions.get(
                transaction, project_id=command.project_id,
                outline_id=command.solution_outline_id,
                version_id=command.solution_outline_version_id)
            if (type(version) is not OutlineVersionHistoryView
                    or version.project_id != command.project_id
                    or version.solution_outline_id != command.solution_outline_id
                    or version.solution_outline_version_id
                       != command.solution_outline_version_id
                    or version.version_state != "APPROVED"
                    or not _digest(version.content_fingerprint)
                    or not _id(version.review_ref)
                    or not _id(version.review_round_ref)):
                raise ApprovedSolutionInputProofError()
            review = self._reviews.get_round(
                transaction, "PROJECT", command.project_id,
                version.review_ref, version.review_round_ref)
            self._assert_outline_review(version, review)

            facts = self._current_facts.facts(
                transaction, command=command, version=version)
            if (type(facts) is not OutlineVersionValidationFacts
                    or facts.order != "PASS" or facts.source != "PASS"):
                raise ApprovedSolutionInputProofError()
            coverage = self._coverage.prove(
                transaction, command=command, version=version,
                approved_outline_review=review)
            if (type(coverage) is not CurrentOutlineCoverageProof
                    or coverage.project_id != command.project_id
                    or coverage.solution_outline_id != command.solution_outline_id
                    or coverage.solution_outline_version_id
                       != command.solution_outline_version_id
                    or coverage.requirement_refs != version.requirement_refs
                    or type(coverage.section_version_ids) is not tuple
                    or len(coverage.section_version_ids) != len(version.section_ids)
                    or any(not _id(value)
                           for value in coverage.section_version_ids)
                    or len(set(coverage.section_version_ids))
                       != len(coverage.section_version_ids)
                    or not _digest(coverage.requirement_scope_fingerprint)):
                raise ApprovedSolutionInputProofError()

            sections = tuple(self._section_input(
                transaction, project_id=command.project_id,
                section_id=section_id, version_id=section_version_id)
                for section_id, section_version_id in zip(
                    version.section_ids, coverage.section_version_ids, strict=True))
            return ApprovedSolutionInputProof(
                command.project_id, command.solution_outline_id,
                command.solution_outline_version_id,
                version.content_fingerprint, version.requirement_refs,
                sections, coverage.requirement_scope_fingerprint)
        except ApprovedSolutionInputProofError:
            raise
        except Exception:
            raise ApprovedSolutionInputProofError() from None

    def _section_input(self, transaction: object, *, project_id: uuid.UUID,
                       section_id: uuid.UUID,
                       version_id: uuid.UUID) -> ApprovedSectionInput:
        section = self._sections.get(
            transaction, project_id=project_id,
            section_id=section_id, version_id=version_id)
        if (type(section) is not SectionVersionHistoryView
                or section.project_id != project_id
                or section.solution_section_id != section_id
                or section.solution_section_version_id != version_id
                or section.version_state != "APPROVED"
                or not _digest(section.content_fingerprint)):
            raise ApprovedSolutionInputProofError()
        if section.spec_binding_state == "NONE_REQUIRED":
            if (not is_normalized_spec_basis(section.spec_not_required_reason)
                    or section.structured_spec_refs):
                raise ApprovedSolutionInputProofError()
            qualified: tuple[QualifiedSectionStructuredSpec, ...] = ()
        elif section.spec_binding_state == "FIXED_REFS":
            qualified = self._specs.prove_current(
                transaction, version=section)
            if (type(qualified) is not tuple
                    or len(qualified) != len(section.structured_spec_refs)
                    or any(type(item) is not QualifiedSectionStructuredSpec
                           for item in qualified)
                    or tuple(item.ref for item in qualified)
                       != section.structured_spec_refs):
                raise ApprovedSolutionInputProofError()
        else:
            # In particular, an old UNDECLARED binding cannot be interpreted
            # as a business decision that no structured design is required.
            raise ApprovedSolutionInputProofError()
        return ApprovedSectionInput(
            section_id, version_id, section.content_fingerprint,
            section.spec_binding_state, qualified)

    @staticmethod
    def _assert_outline_review(
            version: OutlineVersionHistoryView,
            review: FixedReviewRoundSnapshot | None) -> None:
        if type(review) is not FixedReviewRoundSnapshot:
            raise ApprovedSolutionInputProofError()
        review.__post_init__()
        identity = review.review
        import hmac
        if (identity.review_id != version.review_ref
                or identity.scope != "PROJECT"
                or identity.project_id != version.project_id
                or identity.subject_type != "SOL-03"
                or identity.subject_id != version.solution_outline_id
                or identity.policy_code != "SOLUTION_OUTLINE_ALL_V1"
                or identity.state != "APPROVED"
                or review.progress.round_id != version.review_round_ref
                or review.progress.state is not ReviewRoundState.APPROVED
                or review.subject_version_id
                   != version.solution_outline_version_id
                or not hmac.compare_digest(
                    review.subject_fingerprint, version.content_fingerprint)):
            raise ApprovedSolutionInputProofError()
