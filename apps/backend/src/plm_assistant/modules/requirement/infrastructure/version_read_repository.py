"""Project-scoped immutable RequirementVersion read projections."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select

from plm_assistant.modules.requirement.application.read_versions import (
    RequirementAcceptanceView, RequirementAITaskView,
    RequirementAssessmentEvidenceView, RequirementCapabilityAssessmentView,
    RequirementSourceEvidenceView, RequirementSourceView,
    RequirementTextItemView, RequirementVersionSummary, RequirementVersionView,
)

from .identity_create_repository import _session
from .orm import (
    RequirementAcceptanceCriterionRow, RequirementAssessmentEvidenceRefRow,
    RequirementAssumptionRow, RequirementCapabilityAssessmentRow,
    RequirementDependencyRow, RequirementExclusionRow,
    RequirementSourceEvidenceRefRow, RequirementSourceRow,
    RequirementVersionAITaskRefRow, RequirementVersionRow,
)


class SqlAlchemyRequirementVersionReadRepository:
    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      requirement_id: uuid.UUID, after_version_no: int | None,
                      limit: int) -> tuple[RequirementVersionSummary, ...]:
        query = select(RequirementVersionRow).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
        )
        if after_version_no is not None:
            query = query.where(RequirementVersionRow.version_no < after_version_no)
        rows = _session(transaction).execute(query.order_by(
            RequirementVersionRow.version_no.desc(),
        ).limit(limit)).scalars().all()
        return tuple(self._summary(row) for row in rows)

    def get_version(self, transaction: object, *, project_id: uuid.UUID,
                    requirement_id: uuid.UUID,
                    requirement_version_id: uuid.UUID) -> RequirementVersionView | None:
        session = _session(transaction)
        version = session.execute(select(RequirementVersionRow).where(
            RequirementVersionRow.project_id == project_id,
            RequirementVersionRow.requirement_id == requirement_id,
            RequirementVersionRow.requirement_version_id == requirement_version_id,
        )).scalar_one_or_none()
        if version is None:
            return None
        source_rows = session.execute(select(RequirementSourceRow).where(
            RequirementSourceRow.project_id == project_id,
            RequirementSourceRow.requirement_id == requirement_id,
            RequirementSourceRow.requirement_version_id == requirement_version_id,
        ).order_by(RequirementSourceRow.ordinal)).scalars().all()
        source_evidence: dict[
            uuid.UUID, list[RequirementSourceEvidenceView]
        ] = defaultdict(list)
        for source_id, evidence_id, ordinal in session.execute(select(
            RequirementSourceEvidenceRefRow.requirement_source_id,
            RequirementSourceEvidenceRefRow.evidence_id,
            RequirementSourceEvidenceRefRow.ordinal,
        ).where(
            RequirementSourceEvidenceRefRow.project_id == project_id,
            RequirementSourceEvidenceRefRow.requirement_id == requirement_id,
            RequirementSourceEvidenceRefRow.requirement_version_id
            == requirement_version_id,
        ).order_by(RequirementSourceEvidenceRefRow.requirement_source_id,
                   RequirementSourceEvidenceRefRow.ordinal)):
            source_evidence[source_id].append(
                RequirementSourceEvidenceView(evidence_id, ordinal))
        sources = tuple(RequirementSourceView(
            row.ordinal, row.source_type, row.source_object_id,
            row.source_version_ref, tuple(source_evidence[row.requirement_source_id]),
        ) for row in source_rows)

        acceptance = tuple(RequirementAcceptanceView(
            row.ordinal, row.observable_result, row.verification_method,
            row.required_data, row.required_environment, row.evidence_requirement,
        ) for row in session.execute(select(RequirementAcceptanceCriterionRow).where(
            RequirementAcceptanceCriterionRow.project_id == project_id,
            RequirementAcceptanceCriterionRow.requirement_id == requirement_id,
            RequirementAcceptanceCriterionRow.requirement_version_id
            == requirement_version_id,
        ).order_by(RequirementAcceptanceCriterionRow.ordinal)).scalars())

        assessment_rows = session.execute(select(
            RequirementCapabilityAssessmentRow).where(
            RequirementCapabilityAssessmentRow.project_id == project_id,
            RequirementCapabilityAssessmentRow.requirement_id == requirement_id,
            RequirementCapabilityAssessmentRow.requirement_version_id
            == requirement_version_id,
        ).order_by(RequirementCapabilityAssessmentRow.ordinal)).scalars().all()
        assessment_evidence: dict[
            uuid.UUID, list[RequirementAssessmentEvidenceView]
        ] = defaultdict(list)
        for row in session.execute(select(RequirementAssessmentEvidenceRefRow).where(
            RequirementAssessmentEvidenceRefRow.project_id == project_id,
            RequirementAssessmentEvidenceRefRow.requirement_id == requirement_id,
            RequirementAssessmentEvidenceRefRow.requirement_version_id
            == requirement_version_id,
        ).order_by(RequirementAssessmentEvidenceRefRow.capability_assessment_id,
                   RequirementAssessmentEvidenceRefRow.ordinal)).scalars():
            assessment_evidence[row.capability_assessment_id].append(
                RequirementAssessmentEvidenceView(
                    row.evidence_id, row.evidence_role, row.ordinal,
                ))
        assessments = tuple(RequirementCapabilityAssessmentView(
            row.ordinal, row.baseline_version_id, row.capability_item_id,
            row.match_type, row.fit_gap, row.constraints_text, row.assessor_kind,
            row.assessed_by, row.assessed_at, row.confirmation_state,
            tuple(assessment_evidence[row.capability_assessment_id]),
        ) for row in assessment_rows)

        def texts(model, column: str):
            return tuple(RequirementTextItemView(row.ordinal, getattr(row, column))
                         for row in session.execute(select(model).where(
                             model.project_id == project_id,
                             model.requirement_id == requirement_id,
                             model.requirement_version_id == requirement_version_id,
                         ).order_by(model.ordinal)).scalars())

        tasks = tuple(RequirementAITaskView(row.ai_task_id, row.ordinal)
                      for row in session.execute(select(RequirementVersionAITaskRefRow).where(
                          RequirementVersionAITaskRefRow.project_id == project_id,
                          RequirementVersionAITaskRefRow.requirement_id == requirement_id,
                          RequirementVersionAITaskRefRow.requirement_version_id
                          == requirement_version_id,
                      ).order_by(RequirementVersionAITaskRefRow.ordinal)).scalars())
        return RequirementVersionView(
            self._summary(version), version.statement, version.rationale,
            sources, acceptance, assessments,
            texts(RequirementAssumptionRow, "assumption_text"),
            texts(RequirementExclusionRow, "exclusion_text"),
            texts(RequirementDependencyRow, "dependency_text"), tasks,
        )

    @staticmethod
    def _summary(row: RequirementVersionRow) -> RequirementVersionSummary:
        return RequirementVersionSummary(
            row.requirement_version_id, row.requirement_id, row.project_id,
            row.version_no, row.version_state, row.title,
            row.domain_name, row.priority, row.risk,
            row.requirement_classification, bytes(row.content_fingerprint).hex(),
            row.declared_source_count, row.declared_acceptance_count,
            row.declared_capability_count, row.declared_assumption_count,
            row.declared_exclusion_count, row.declared_dependency_count,
            row.declared_ai_task_count, row.supersedes_version_ref,
            row.review_ref, row.review_round_ref, row.created_by, row.created_at,
        )
