"""Locked reconstruction of one immutable SurveyConclusion aggregate."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.handover.application.survey_conclusion_issue import (
    SurveyConclusionIssueProof,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordProof,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    DepartmentConclusionInput, ModuleConclusionInput,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    ConclusionValidationSnapshot,
)

from .orm import (
    SurveyConclusionEvidenceRefRow, SurveyConclusionOpenIssueRow,
    SurveyConclusionRow, SurveyDepartmentConclusionRow,
    SurveyModuleConclusionRow, SurveyRoundRow,
)
from .survey_create_repository import _session


class SqlAlchemySurveyConclusionValidationRepository:
    def lock_snapshot(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID,
    ) -> ConclusionValidationSnapshot | None:
        if (transaction is None or any(
                type(value) is not uuid.UUID or value.int == 0
                for value in (project_id, survey_conclusion_id))):
            return None
        session = _session(transaction)
        root = session.execute(select(SurveyConclusionRow).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.survey_conclusion_id == survey_conclusion_id,
        ).with_for_update(of=SurveyConclusionRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if root is None:
            return None

        rounds = session.execute(select(SurveyRoundRow.survey_round_id).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_id == root.survey_id,
            SurveyRoundRow.survey_round_id.in_(tuple(root.round_refs)),
            SurveyRoundRow.round_state == "CLOSED",
        ).order_by(SurveyRoundRow.survey_round_id).with_for_update(
            read=True, of=SurveyRoundRow,
        ).execution_options(populate_existing=True)).scalars().all()
        expected_rounds = tuple(sorted(root.round_refs, key=lambda value: value.int))
        rounds_current = tuple(rounds) == expected_rounds

        departments = session.execute(select(
            SurveyDepartmentConclusionRow,
        ).where(
            SurveyDepartmentConclusionRow.project_id == project_id,
            SurveyDepartmentConclusionRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyDepartmentConclusionRow.ordinal).with_for_update(
            read=True, of=SurveyDepartmentConclusionRow,
        ).execution_options(populate_existing=True)).scalars().all()
        modules = session.execute(select(
            SurveyModuleConclusionRow,
        ).where(
            SurveyModuleConclusionRow.project_id == project_id,
            SurveyModuleConclusionRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyModuleConclusionRow.ordinal).with_for_update(
            read=True, of=SurveyModuleConclusionRow,
        ).execution_options(populate_existing=True)).scalars().all()
        evidence = session.execute(select(
            SurveyConclusionEvidenceRefRow,
        ).where(
            SurveyConclusionEvidenceRefRow.project_id == project_id,
            SurveyConclusionEvidenceRefRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyConclusionEvidenceRefRow.ordinal).with_for_update(
            read=True, of=SurveyConclusionEvidenceRefRow,
        ).execution_options(populate_existing=True)).scalars().all()
        issues = session.execute(select(
            SurveyConclusionOpenIssueRow,
        ).where(
            SurveyConclusionOpenIssueRow.project_id == project_id,
            SurveyConclusionOpenIssueRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyConclusionOpenIssueRow.ordinal).with_for_update(
            read=True, of=SurveyConclusionOpenIssueRow,
        ).execution_options(populate_existing=True)).scalars().all()

        ordinals_contiguous = all(
            [row.ordinal for row in rows] == list(range(len(rows)))
            for rows in (departments, modules, evidence, issues)
        )
        formal_decision_count = sum(
            any(value is not None for value in (
                row.decision_type, row.decision_reason, row.decision_impact,
                row.decision_evidence_id, row.decision_review_ref,
            ))
            for row in (*departments, *modules)
        )
        return ConclusionValidationSnapshot(
            root.survey_conclusion_id, root.conclusion_series_id,
            root.project_id, root.survey_id, tuple(root.round_refs),
            tuple(root.ai_task_refs), root.version_no, root.conclusion_state,
            bytes(root.content_fingerprint), root.declared_department_count,
            root.declared_module_count, root.declared_evidence_count,
            root.declared_open_issue_count, root.supersedes_ref,
            tuple(DepartmentConclusionInput(
                row.department_id, row.title, row.statement,
                tuple(row.response_refs),
            ) for row in departments),
            tuple(ModuleConclusionInput(
                row.module_key, row.title, row.statement,
                tuple(row.response_refs),
            ) for row in modules),
            tuple(ConclusionProjectRecordProof(
                row.evidence_id, row.project_id, row.document_id,
                row.document_version_id, row.observed_evidence_lock_version,
                bytes(row.content_fingerprint), root.created_by,
            ) for row in evidence),
            tuple(row.reference_role for row in evidence),
            tuple(SurveyConclusionIssueProof(
                row.issue_id, row.project_id, "PROVIDE_INFO",
                row.observed_issue_state, row.observed_lock_version,
                row.created_at,
            ) for row in issues),
            tuple(row.is_blocking for row in issues), rounds_current,
            ordinals_contiguous, formal_decision_count,
        )
