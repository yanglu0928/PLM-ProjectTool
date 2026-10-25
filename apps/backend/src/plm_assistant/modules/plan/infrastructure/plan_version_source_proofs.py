"""Same-transaction Project and fixed-source proofs for PlanVersion creation."""

from __future__ import annotations

import hmac
import uuid

from sqlalchemy import func, select

from plm_assistant.modules.plan.application.plan_version_input import (
    FixedVersionRef, PlanExclusionInput, PlanVersionDraftInput,
)
from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionSourceProofError,
)
from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProof,
)
from plm_assistant.modules.plan.infrastructure.plan_version_create_repository import _session
from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow
from plm_assistant.modules.requirement.infrastructure.orm import RequirementRow, RequirementVersionRow
from plm_assistant.modules.prototype.infrastructure.orm import (
    PrototypeRow, PrototypeVersionRow,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewSnapshotReadPort,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.solution.infrastructure.orm import (
    SolutionOutlineRow, SolutionOutlineVersionRow,
    SolutionSectionRow, SolutionSectionVersionRow,
    StructuredSolutionSpecRow,
)


class SqlAlchemyPlanVersionSourceProofs:
    def __init__(self, *, reviews: ReviewSnapshotReadPort) -> None:
        if reviews is None:
            raise ValueError("Review snapshot reader is required")
        self._reviews = reviews

    def validate(self, transaction: object, *, project_id: uuid.UUID,
                 draft: PlanVersionDraftInput,
                 solution: ApprovedSolutionInputProof) -> None:
        try:
            if solution.project_id != project_id:
                raise PlanVersionSourceProofError()
            session = _session(transaction)
            self._members(session, project_id, draft)
            self._solutions(session, project_id, draft, solution)
            self._prototypes(transaction, project_id, draft)
            self._exclusions(session, project_id, draft.exclusions)
        except PlanVersionSourceProofError:
            raise
        except Exception:
            raise PlanVersionSourceProofError() from None

    @staticmethod
    def _members(session, project_id: uuid.UUID, draft: PlanVersionDraftInput) -> None:
        ids = {item.owner_project_member_id for item in draft.wbs_items
               if item.owner_project_member_id is not None}
        if not ids:
            return
        rows = tuple(session.execute(select(ProjectMemberRow).where(
            ProjectMemberRow.project_id == project_id,
            ProjectMemberRow.project_member_id.in_(ids),
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.effective_at <= func.statement_timestamp(),
            ProjectMemberRow.ended_at.is_(None),
        ).with_for_update(read=True, of=ProjectMemberRow)).scalars())
        if {row.project_member_id for row in rows} != ids:
            raise PlanVersionSourceProofError()

    def _solutions(self, session, project_id: uuid.UUID,
                   draft: PlanVersionDraftInput,
                   proof: ApprovedSolutionInputProof) -> None:
        expected = {
            FixedVersionRef("OUTLINE", proof.outline_id, proof.outline_version_id),
            *(FixedVersionRef("SECTION", item.section_id, item.section_version_id)
              for item in proof.sections),
        }
        for section in proof.sections:
            for qualified in section.qualified_specs:
                ref = qualified.ref
                row = session.execute(select(StructuredSolutionSpecRow).where(
                    StructuredSolutionSpecRow.project_id == project_id,
                    StructuredSolutionSpecRow.spec_series_id == ref.spec_series_id,
                    StructuredSolutionSpecRow.version_state == "APPROVED",
                ).with_for_update(read=True, of=StructuredSolutionSpecRow)).scalar_one_or_none()
                if (row is None or row.structured_solution_spec_id.int == 0
                        or row.spec_type != qualified.spec_type):
                    raise PlanVersionSourceProofError()
                expected.add(FixedVersionRef(
                    "STRUCTURED_SPEC", ref.spec_series_id,
                    row.structured_solution_spec_id,
                    ref.spec_series_id, row.spec_type))
        submitted = set(draft.approved_solution_refs)
        if submitted != expected:
            raise PlanVersionSourceProofError()
        if any(ref not in expected for item in draft.wbs_items
               for ref in item.solution_refs):
            raise PlanVersionSourceProofError()

    def _prototypes(self, transaction: object, project_id: uuid.UUID,
                    draft: PlanVersionDraftInput) -> None:
        session = _session(transaction)
        refs = {ref for item in draft.wbs_items for ref in item.prototype_refs}
        for ref in refs:
            pair = session.execute(select(PrototypeRow, PrototypeVersionRow).join(
                PrototypeVersionRow,
                (PrototypeVersionRow.prototype_id == PrototypeRow.prototype_id)
                & (PrototypeVersionRow.project_id == PrototypeRow.project_id),
            ).where(
                PrototypeRow.project_id == project_id,
                PrototypeRow.prototype_id == ref.resource_id,
                PrototypeRow.prototype_state == "ACTIVE",
                PrototypeRow.current_approved_version_ref == ref.version_id,
                PrototypeVersionRow.prototype_version_id == ref.version_id,
                PrototypeVersionRow.version_state == "APPROVED",
            ).with_for_update(read=True, of=(PrototypeRow, PrototypeVersionRow))).one_or_none()
            if pair is None:
                raise PlanVersionSourceProofError()
            prototype, version = pair
            if (version.review_ref is None or version.review_round_ref is None
                    or type(version.content_fingerprint) is not bytes
                    or len(version.content_fingerprint) != 32):
                raise PlanVersionSourceProofError()
            review = self._reviews.get_round(
                transaction, "PROJECT", project_id,
                version.review_ref, version.review_round_ref)
            if (review is None or review.review.review_id != version.review_ref
                    or review.review.project_id != project_id
                    or review.review.subject_type != "PRT-03"
                    or review.review.subject_id != prototype.prototype_id
                    or review.review.state != "APPROVED"
                    or review.progress.round_id != version.review_round_ref
                    or review.progress.state is not ReviewRoundState.APPROVED
                    or review.subject_version_id != version.prototype_version_id
                    or not hmac.compare_digest(
                        review.subject_fingerprint, version.content_fingerprint)):
                raise PlanVersionSourceProofError()

    @staticmethod
    def _exclusions(session, project_id: uuid.UUID,
                    exclusions: tuple[PlanExclusionInput, ...]) -> None:
        # Require a current approved target for every exclusion. A historical or
        # unapproved object is not silently promoted to a formal Plan fact.
        for item in exclusions:
            if item.target_kind == "REQUIREMENT_VERSION":
                pair = session.execute(select(RequirementRow, RequirementVersionRow).join(
                    RequirementVersionRow,
                    (RequirementVersionRow.requirement_id == RequirementRow.requirement_id)
                    & (RequirementVersionRow.project_id == RequirementRow.project_id),
                ).where(
                    RequirementRow.project_id == project_id,
                    RequirementRow.requirement_id == item.resource_id,
                    RequirementRow.current_approved_version_ref == item.version_id,
                    RequirementVersionRow.requirement_version_id == item.version_id,
                    RequirementVersionRow.version_state == "APPROVED",
                ).with_for_update(read=True,
                                  of=(RequirementRow, RequirementVersionRow))).one_or_none()
            elif item.target_kind == "SOLUTION_OUTLINE_VERSION":
                pair = session.execute(select(SolutionOutlineRow, SolutionOutlineVersionRow).join(
                    SolutionOutlineVersionRow,
                    (SolutionOutlineVersionRow.solution_outline_id
                     == SolutionOutlineRow.solution_outline_id)
                    & (SolutionOutlineVersionRow.project_id == SolutionOutlineRow.project_id),
                ).where(
                    SolutionOutlineRow.project_id == project_id,
                    SolutionOutlineRow.solution_outline_id == item.resource_id,
                    SolutionOutlineRow.current_approved_version_ref == item.version_id,
                    SolutionOutlineVersionRow.solution_outline_version_id == item.version_id,
                    SolutionOutlineVersionRow.version_state == "APPROVED",
                ).with_for_update(read=True,
                                  of=(SolutionOutlineRow, SolutionOutlineVersionRow))).one_or_none()
            elif item.target_kind == "SOLUTION_SECTION_VERSION":
                pair = session.execute(select(SolutionSectionRow, SolutionSectionVersionRow).join(
                    SolutionSectionVersionRow,
                    (SolutionSectionVersionRow.solution_section_id
                     == SolutionSectionRow.solution_section_id)
                    & (SolutionSectionVersionRow.project_id == SolutionSectionRow.project_id),
                ).where(
                    SolutionSectionRow.project_id == project_id,
                    SolutionSectionRow.solution_section_id == item.resource_id,
                    SolutionSectionRow.current_approved_version_ref == item.version_id,
                    SolutionSectionVersionRow.solution_section_version_id == item.version_id,
                    SolutionSectionVersionRow.version_state == "APPROVED",
                ).with_for_update(read=True,
                                  of=(SolutionSectionRow, SolutionSectionVersionRow))).one_or_none()
            elif item.target_kind == "STRUCTURED_SPEC_VERSION":
                pair = session.execute(select(StructuredSolutionSpecRow).where(
                    StructuredSolutionSpecRow.project_id == project_id,
                    StructuredSolutionSpecRow.structured_solution_spec_id == item.version_id,
                    StructuredSolutionSpecRow.spec_series_id == item.spec_series_id,
                    StructuredSolutionSpecRow.spec_type == item.spec_type,
                    StructuredSolutionSpecRow.version_state == "APPROVED",
                ).with_for_update(read=True, of=StructuredSolutionSpecRow)
                ).scalar_one_or_none()
            else:
                pair = None
            if pair is None:
                raise PlanVersionSourceProofError()
