"""Same-transaction candidate qualification for fixed Section Spec references.

This proves referential/current Review eligibility, not semantic fit or approval
of the new SectionVersion. The caller must already authorize the project write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot, ReviewSnapshotReadPort,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState

from .read_section_version import SectionVersionHistoryView
from .read_structured_spec import StructuredSpecHistoryView
from .section_version_base import CurrentSectionVersionBase
from .section_version_input import (
    SectionRequirementRef, SectionStructuredSpecRef,
    is_normalized_spec_basis,
)


class SectionStructuredSpecQualificationError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SOURCE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class QualifiedSectionStructuredSpec:
    ref: SectionStructuredSpecRef
    spec_type: str
    content_fingerprint: bytes = field(repr=False)
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    source_section_version_id: uuid.UUID
    source_content_fingerprint: bytes = field(repr=False)
    shared_requirement_version_ids: tuple[uuid.UUID, ...]


class SpecPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            spec_id: uuid.UUID) -> StructuredSpecHistoryView | None: ...

    def current_approved(self, transaction: object, *, project_id: uuid.UUID,
                         series_id: uuid.UUID) -> uuid.UUID | None: ...


class SectionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...

    def is_ancestor(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID, latest_version_id: uuid.UUID,
                    ancestor_version_id: uuid.UUID) -> bool: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


class SectionStructuredSpecQualificationService:
    def __init__(self, *, specs: SpecPort, sections: SectionPort,
                 reviews: ReviewSnapshotReadPort) -> None:
        if any(port is None for port in (specs, sections, reviews)):
            raise ValueError("fixed Spec qualification ports required")
        self._specs, self._sections, self._reviews = specs, sections, reviews

    def prove(
        self, transaction: object, *, base: CurrentSectionVersionBase,
        project_id: uuid.UUID, section_id: uuid.UUID,
        requirement_refs: tuple[SectionRequirementRef, ...],
        spec_refs: tuple[SectionStructuredSpecRef, ...],
    ) -> tuple[QualifiedSectionStructuredSpec, ...]:
        if (transaction is None or type(base) is not CurrentSectionVersionBase
                or not _id(project_id) or not _id(section_id)
                or base.project_id != project_id
                or base.solution_section_id != section_id
                or type(base.next_version_no) is not int
                or base.next_version_no < 2
                or not _id(base.supersedes_version_id)
                or type(requirement_refs) is not tuple
                or type(spec_refs) is not tuple
                or not 1 <= len(spec_refs) <= 500
                or any(type(item) is not SectionRequirementRef
                       or not _id(item.requirement_id)
                       or not _id(item.requirement_version_id)
                       for item in requirement_refs)
                or any(type(item) is not SectionStructuredSpecRef
                       or not _id(item.spec_series_id)
                       or not _id(item.structured_solution_spec_id)
                       for item in spec_refs)
                or len({item.spec_series_id for item in spec_refs}) != len(spec_refs)
                or len({item.structured_solution_spec_id for item in spec_refs})
                != len(spec_refs)):
            raise SectionStructuredSpecQualificationError()
        requirements = {(item.requirement_id, item.requirement_version_id)
                        for item in requirement_refs}
        if len(requirements) != len(requirement_refs):
            raise SectionStructuredSpecQualificationError()
        return self._prove_refs(
            transaction, project_id=project_id, section_id=section_id,
            target_version_no=base.next_version_no,
            predecessor_version_id=base.supersedes_version_id,
            requirements=requirements, spec_refs=spec_refs)

    def prove_current(self, transaction: object, *,
                      version: SectionVersionHistoryView,
                      ) -> tuple[QualifiedSectionStructuredSpec, ...]:
        """Re-qualify fixed history against today's approved Spec/Review facts."""
        if (transaction is None or type(version) is not SectionVersionHistoryView
                or not _id(version.project_id)
                or not _id(version.solution_section_id)
                or not _id(version.solution_section_version_id)
                or version.version_state not in ("DRAFT", "IN_REVIEW")
                or version.spec_binding_state != "FIXED_REFS"
                or type(version.version_no) is not int or version.version_no < 2
                or not _id(version.supersedes_version_ref)
                or type(version.requirement_refs) is not tuple
                or type(version.structured_spec_refs) is not tuple
                or not 1 <= len(version.structured_spec_refs) <= 500
                or any(type(item) is not SectionRequirementRef
                       or not _id(item.requirement_id)
                       or not _id(item.requirement_version_id)
                       for item in version.requirement_refs)
                or any(type(item) is not SectionStructuredSpecRef
                       or not _id(item.spec_series_id)
                       or not _id(item.structured_solution_spec_id)
                       or not is_normalized_spec_basis(item.fit_rationale)
                       for item in version.structured_spec_refs)
                or len({item.spec_series_id for item in version.structured_spec_refs})
                != len(version.structured_spec_refs)
                or len({item.structured_solution_spec_id
                        for item in version.structured_spec_refs})
                != len(version.structured_spec_refs)):
            raise SectionStructuredSpecQualificationError()
        requirements = {(item.requirement_id, item.requirement_version_id)
                        for item in version.requirement_refs}
        if len(requirements) != len(version.requirement_refs):
            raise SectionStructuredSpecQualificationError()
        return self._prove_refs(
            transaction, project_id=version.project_id,
            section_id=version.solution_section_id,
            target_version_no=version.version_no,
            predecessor_version_id=version.supersedes_version_ref,
            requirements=requirements,
            spec_refs=version.structured_spec_refs)

    def _prove_refs(
        self, transaction: object, *, project_id: uuid.UUID,
        section_id: uuid.UUID, target_version_no: int,
        predecessor_version_id: uuid.UUID,
        requirements: set[tuple[uuid.UUID, uuid.UUID]],
        spec_refs: tuple[SectionStructuredSpecRef, ...],
    ) -> tuple[QualifiedSectionStructuredSpec, ...]:
        try:
            return tuple(self._one(
                transaction, target_version_no=target_version_no,
                predecessor_version_id=predecessor_version_id,
                project_id=project_id, section_id=section_id,
                requirements=requirements, ref=ref)
                for ref in spec_refs)
        except SectionStructuredSpecQualificationError:
            raise
        except Exception:
            raise SectionStructuredSpecQualificationError() from None

    def _one(
        self, transaction: object, *, target_version_no: int,
        predecessor_version_id: uuid.UUID,
        project_id: uuid.UUID, section_id: uuid.UUID,
        requirements: set[tuple[uuid.UUID, uuid.UUID]],
        ref: SectionStructuredSpecRef,
    ) -> QualifiedSectionStructuredSpec:
        spec = self._specs.get(
            transaction, project_id=project_id,
            spec_id=ref.structured_solution_spec_id)
        approved_id = self._specs.current_approved(
            transaction, project_id=project_id,
            series_id=ref.spec_series_id)
        if (type(spec) is not StructuredSpecHistoryView
                or spec.project_id != project_id
                or spec.spec_series_id != ref.spec_series_id
                or spec.structured_solution_spec_id
                != ref.structured_solution_spec_id
                or spec.version_state != "APPROVED"
                or approved_id != ref.structured_solution_spec_id
                or not _digest(spec.content_fingerprint)
                or not _id(spec.review_ref)
                or not _id(spec.review_round_ref)
                or spec.artifact_ids
                or not spec.requirement_refs
                or not spec.section_refs):
            raise SectionStructuredSpecQualificationError()
        identity = self._reviews.get_review(
            transaction, "PROJECT", project_id, spec.review_ref)
        round_snapshot = self._reviews.get_round(
            transaction, "PROJECT", project_id,
            spec.review_ref, spec.review_round_ref)
        if (type(identity) is not ReviewIdentitySnapshot
                or type(round_snapshot) is not FixedReviewRoundSnapshot
                or identity.review_id != spec.review_ref
                or identity.scope != "PROJECT"
                or identity.project_id != project_id
                or identity.subject_type != "SOL-06"
                or identity.subject_id != ref.spec_series_id
                or identity.policy_code != "STRUCTURED_SPEC_ALL_V1"
                or identity.state != "APPROVED"
                or round_snapshot.review != identity
                or round_snapshot.progress.round_id != spec.review_round_ref
                or round_snapshot.progress.state is not ReviewRoundState.APPROVED
                or round_snapshot.subject_version_id
                != ref.structured_solution_spec_id
                or round_snapshot.subject_fingerprint
                != spec.content_fingerprint):
            raise SectionStructuredSpecQualificationError()
        sources = tuple(item for item in spec.section_refs
                        if item.solution_section_id == section_id)
        if len(sources) != 1:
            raise SectionStructuredSpecQualificationError()
        source_ref = sources[0]
        source = self._sections.get(
            transaction, project_id=project_id,
            section_id=section_id,
            version_id=source_ref.solution_section_version_id)
        if (type(source) is not SectionVersionHistoryView
                or source.project_id != project_id
                or source.solution_section_id != section_id
                or source.solution_section_version_id
                != source_ref.solution_section_version_id
                or source.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "SUPERSEDED")
                or type(source.version_no) is not int
                or not 1 <= source.version_no < target_version_no
                or not _digest(source.content_fingerprint)
                or not self._sections.is_ancestor(
                    transaction, project_id=project_id,
                    section_id=section_id,
                    latest_version_id=predecessor_version_id,
                    ancestor_version_id=source_ref.solution_section_version_id)):
            raise SectionStructuredSpecQualificationError()
        source_requirements = {
            (item.requirement_id, item.requirement_version_id)
            for item in source.requirement_refs}
        spec_requirements = {
            (item.requirement_id, item.requirement_version_id)
            for item in spec.requirement_refs}
        shared = requirements & source_requirements & spec_requirements
        if not shared:
            raise SectionStructuredSpecQualificationError()
        return QualifiedSectionStructuredSpec(
            ref, spec.spec_type, spec.content_fingerprint,
            spec.review_ref, spec.review_round_ref,
            source.solution_section_version_id, source.content_fingerprint,
            tuple(sorted((version_id for _, version_id in shared), key=lambda value: value.int)),
        )


class SectionCurrentSpecQualificationService:
    """Narrow VALIDATE port; never accepts a CREATE next-version base."""

    def __init__(self, qualification: SectionStructuredSpecQualificationService) -> None:
        if type(qualification) is not SectionStructuredSpecQualificationService:
            raise ValueError("current Section Spec qualification required")
        self._qualification = qualification

    def prove(self, transaction: object, *,
              version: SectionVersionHistoryView,
              ) -> tuple[QualifiedSectionStructuredSpec, ...]:
        return self._qualification.prove_current(transaction, version=version)
