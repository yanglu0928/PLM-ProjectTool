"""Shared-locked reconstruction of one immutable RequirementVersion."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select

from plm_assistant.modules.requirement.application.create_version import (
    RequirementAcceptanceDraft, RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
)
from plm_assistant.modules.requirement.application.prototype_workflow_proof import (
    RequirementAcceptanceRefsProof,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationSnapshot,
)

from .identity_create_repository import _session
from .orm import (
    RequirementAcceptanceCriterionRow, RequirementAssessmentEvidenceRefRow,
    RequirementAssumptionRow, RequirementCapabilityAssessmentRow,
    RequirementDependencyRow, RequirementExclusionRow,
    RequirementSourceEvidenceRefRow, RequirementSourceRow,
    RequirementVersionAITaskRefRow, RequirementVersionRow,
)


class SqlAlchemyRequirementVersionValidationRepository:
    def lock_snapshot(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> RequirementVersionValidationSnapshot | None:
        result = self._lock_snapshot_and_rows(
            transaction, project_id=project_id,
            requirement_id=requirement_id,
            requirement_version_id=requirement_version_id,
        )
        return None if result is None else result[0]

    def lock_snapshot_and_acceptance_refs(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> tuple[RequirementVersionValidationSnapshot,
               RequirementAcceptanceRefsProof] | None:
        """Expose stable IDs from the same shared-locked rows as the snapshot."""
        result = self._lock_snapshot_and_rows(
            transaction, project_id=project_id,
            requirement_id=requirement_id,
            requirement_version_id=requirement_version_id,
        )
        if result is None:
            return None
        snapshot, rows = result
        if (snapshot.declared_acceptance_count <= 0
                or len(rows) != snapshot.declared_acceptance_count
                or not self._contiguous(rows)):
            return None
        try:
            refs = RequirementAcceptanceRefsProof(
                project_id, requirement_id, requirement_version_id,
                tuple(row.acceptance_criterion_id for row in rows),
            )
        except ValueError:
            return None
        return snapshot, refs

    def _lock_snapshot_and_rows(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    ) -> tuple[RequirementVersionValidationSnapshot, tuple] | None:
        identities = (project_id, requirement_id, requirement_version_id)
        if any(type(value) is not uuid.UUID or value.int == 0
               for value in identities):
            return None
        session = _session(transaction)
        version = session.execute(select(RequirementVersionRow).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.requirement_version_id == requirement_version_id,
        ).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if version is None:
            return None

        source_rows = self._rows(session, RequirementSourceRow, project_id,
                                 requirement_id, requirement_version_id)
        source_evidence_rows = self._rows(
            session, RequirementSourceEvidenceRefRow, project_id,
            requirement_id, requirement_version_id,
            parent="requirement_source_id",
        )
        source_evidence: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for row in source_evidence_rows:
            source_evidence[row.requirement_source_id].append(row.evidence_id)
        sources = tuple(RequirementSourceDraft(
            row.source_type, row.source_object_id, row.source_version_ref,
            tuple(source_evidence[row.requirement_source_id]),
        ) for row in source_rows)

        acceptance_rows = self._rows(
            session, RequirementAcceptanceCriterionRow, project_id,
            requirement_id, requirement_version_id,
        )
        acceptance = tuple(RequirementAcceptanceDraft(
            row.observable_result, row.verification_method, row.required_data,
            row.required_environment, row.evidence_requirement,
        ) for row in acceptance_rows)

        assessment_rows = self._rows(
            session, RequirementCapabilityAssessmentRow, project_id,
            requirement_id, requirement_version_id,
        )
        assessment_evidence_rows = self._rows(
            session, RequirementAssessmentEvidenceRefRow, project_id,
            requirement_id, requirement_version_id,
            parent="capability_assessment_id",
        )
        assessment_evidence: dict[
            uuid.UUID, list[RequirementAssessmentEvidenceDraft]
        ] = defaultdict(list)
        for row in assessment_evidence_rows:
            assessment_evidence[row.capability_assessment_id].append(
                RequirementAssessmentEvidenceDraft(
                    row.evidence_id, row.evidence_role,
                ))
        assessments = tuple(RequirementCapabilityAssessmentDraft(
            row.baseline_version_id, row.capability_item_id, row.match_type,
            row.fit_gap, row.constraints_text, row.assessor_kind,
            row.confirmation_state,
            tuple(assessment_evidence[row.capability_assessment_id]),
        ) for row in assessment_rows)

        assumption_rows = self._rows(
            session, RequirementAssumptionRow, project_id,
            requirement_id, requirement_version_id,
        )
        exclusion_rows = self._rows(
            session, RequirementExclusionRow, project_id,
            requirement_id, requirement_version_id,
        )
        dependency_rows = self._rows(
            session, RequirementDependencyRow, project_id,
            requirement_id, requirement_version_id,
        )
        task_rows = self._rows(
            session, RequirementVersionAITaskRefRow, project_id,
            requirement_id, requirement_version_id,
        )
        contiguous = all((
            self._contiguous(source_rows),
            self._nested_contiguous(
                source_rows, source_evidence_rows, "requirement_source_id"),
            self._contiguous(acceptance_rows),
            self._contiguous(assessment_rows),
            self._nested_contiguous(
                assessment_rows, assessment_evidence_rows,
                "capability_assessment_id"),
            self._contiguous(assumption_rows), self._contiguous(exclusion_rows),
            self._contiguous(dependency_rows), self._contiguous(task_rows),
        ))
        snapshot = RequirementVersionValidationSnapshot(
            version.requirement_version_id, version.requirement_id,
            version.project_id, version.version_no, version.version_state,
            version.title, version.statement, version.rationale,
            version.domain_name, version.priority, version.risk,
            version.requirement_classification,
            bytes(version.content_fingerprint), version.declared_source_count,
            version.declared_acceptance_count,
            version.declared_capability_count,
            version.declared_assumption_count, version.declared_exclusion_count,
            version.declared_dependency_count, version.declared_ai_task_count,
            sources, acceptance, assessments,
            tuple(row.assumption_text for row in assumption_rows),
            tuple(row.exclusion_text for row in exclusion_rows),
            tuple(row.dependency_text for row in dependency_rows),
            tuple(row.ai_task_id for row in task_rows), contiguous,
        )
        return snapshot, tuple(acceptance_rows)

    @staticmethod
    def _rows(session, model, project_id: uuid.UUID,
              requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
              *, parent: str | None = None):
        order = [getattr(model, parent)] if parent is not None else []
        order.append(model.ordinal)
        return session.execute(select(model).where(
            model.project_id == project_id,
            model.requirement_id == requirement_id,
            model.requirement_version_id == requirement_version_id,
        ).order_by(*order).with_for_update(read=True).execution_options(
            populate_existing=True,
        )).scalars().all()

    @staticmethod
    def _contiguous(rows: list[object]) -> bool:
        return [row.ordinal for row in rows] == list(range(len(rows)))

    @staticmethod
    def _nested_contiguous(parents: list[object], children: list[object],
                           parent_field: str) -> bool:
        grouped: dict[uuid.UUID, list[int]] = defaultdict(list)
        for child in children:
            grouped[getattr(child, parent_field)].append(child.ordinal)
        parent_ids = {
            getattr(parent, parent_field) for parent in parents
        }
        return (set(grouped) <= parent_ids
                and all(ordinals == list(range(len(ordinals)))
                        for ordinals in grouped.values()))
