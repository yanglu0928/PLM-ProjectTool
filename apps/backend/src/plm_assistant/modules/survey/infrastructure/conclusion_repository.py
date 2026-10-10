"""SurveyConclusion lineage, immutable persistence, and read projections."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.survey.application.conclusion_views import (
    ConclusionEvidenceView, ConclusionOpenIssueView, DepartmentConclusionView,
    ModuleConclusionView, SurveyConclusionSummaryView, SurveyConclusionView,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionCreatePlan, ConclusionCreateSnapshot, SurveyConclusionCreateError,
)

from .orm import (
    SurveyConclusionEvidenceRefRow, SurveyConclusionOpenIssueRow,
    SurveyConclusionRow, SurveyDepartmentConclusionRow, SurveyModuleConclusionRow,
    SurveyRoundRow, SurveyRow,
)
from .survey_create_repository import _session


def _summary(row: SurveyConclusionRow) -> SurveyConclusionSummaryView:
    return SurveyConclusionSummaryView(
        survey_conclusion_id=row.survey_conclusion_id,
        conclusion_series_id=row.conclusion_series_id,
        project_id=row.project_id,
        survey_id=row.survey_id,
        round_refs=tuple(row.round_refs),
        ai_task_refs=tuple(row.ai_task_refs),
        version_no=row.version_no,
        conclusion_state=row.conclusion_state,
        content_fingerprint=bytes(row.content_fingerprint).hex(),
        declared_department_count=row.declared_department_count,
        declared_module_count=row.declared_module_count,
        declared_evidence_count=row.declared_evidence_count,
        declared_open_issue_count=row.declared_open_issue_count,
        supersedes_ref=row.supersedes_ref,
        review_ref=row.review_ref,
        review_round_ref=row.review_round_ref,
        created_by=row.created_by,
        created_at=row.created_at,
    )


class SqlAlchemySurveyConclusionRepository:
    def prepare(
        self, transaction: object, *, survey_conclusion_id: uuid.UUID,
        proposed_series_id: uuid.UUID, project_id: uuid.UUID,
        survey_id: uuid.UUID, round_refs: tuple[uuid.UUID, ...],
        supersedes_ref: uuid.UUID | None,
    ) -> ConclusionCreatePlan:
        session = _session(transaction)
        prior = None
        if supersedes_ref is None:
            series_id, version_no = proposed_series_id, 1
        else:
            prior = session.execute(select(SurveyConclusionRow).where(
                SurveyConclusionRow.project_id == project_id,
                SurveyConclusionRow.survey_id == survey_id,
                SurveyConclusionRow.survey_conclusion_id == supersedes_ref,
            ).with_for_update(of=SurveyConclusionRow).execution_options(
                populate_existing=True,
            )).scalar_one_or_none()
            if prior is None or prior.conclusion_state not in (
                    "DRAFT", "RETURNED", "APPROVED"):
                raise SurveyConclusionCreateError("RESOURCE_NOT_FOUND")
            latest = session.execute(select(SurveyConclusionRow).where(
                SurveyConclusionRow.project_id == project_id,
                SurveyConclusionRow.conclusion_series_id
                == prior.conclusion_series_id,
            ).order_by(SurveyConclusionRow.version_no.desc()).limit(1).with_for_update(
                of=SurveyConclusionRow,
            ).execution_options(populate_existing=True)).scalar_one()
            if latest.survey_conclusion_id != supersedes_ref:
                raise SurveyConclusionCreateError("CONCLUSION_VERSION_CONFLICT")
            series_id, version_no = prior.conclusion_series_id, prior.version_no + 1
        survey = session.execute(select(SurveyRow).where(
            SurveyRow.project_id == project_id,
            SurveyRow.survey_id == survey_id,
            SurveyRow.survey_state == "ACTIVE",
        ).with_for_update(of=SurveyRow).execution_options(
            populate_existing=True,
        )).scalar_one_or_none()
        if survey is None:
            raise SurveyConclusionCreateError("RESOURCE_NOT_FOUND")
        rounds = tuple(session.execute(select(SurveyRoundRow).where(
            SurveyRoundRow.project_id == project_id,
            SurveyRoundRow.survey_id == survey_id,
            SurveyRoundRow.survey_round_id.in_(round_refs),
            SurveyRoundRow.round_state == "CLOSED",
        ).order_by(SurveyRoundRow.survey_round_id).with_for_update(
            read=True, of=SurveyRoundRow,
        ).execution_options(populate_existing=True)).scalars())
        if tuple(row.survey_round_id for row in rounds) != round_refs:
            raise SurveyConclusionCreateError("SURVEY_CONCLUSION_SOURCE_INVALID")

        return ConclusionCreatePlan(
            survey_conclusion_id, series_id, project_id, survey_id,
            round_refs, version_no, supersedes_ref,
        )

    def create(
        self, transaction: object, snapshot: ConclusionCreateSnapshot,
    ) -> SurveyConclusionView:
        if type(snapshot) is not ConclusionCreateSnapshot:
            raise SurveyConclusionCreateError()
        session = _session(transaction)
        plan = snapshot.plan
        root = SurveyConclusionRow(
            survey_conclusion_id=plan.survey_conclusion_id,
            conclusion_series_id=plan.conclusion_series_id,
            project_id=plan.project_id,
            survey_id=plan.survey_id,
            round_refs=list(plan.round_refs),
            ai_task_refs=[item.ai_task_id for item in snapshot.ai_proofs],
            version_no=plan.version_no,
            conclusion_state="DRAFT",
            content_fingerprint=snapshot.content_fingerprint,
            declared_department_count=len(snapshot.departments),
            declared_module_count=len(snapshot.modules),
            declared_evidence_count=len(snapshot.evidence_inputs),
            declared_open_issue_count=len(snapshot.issue_inputs),
            supersedes_ref=plan.supersedes_ref,
            review_ref=None,
            review_round_ref=None,
            created_by=snapshot.actor_id,
        )
        session.add(root)
        session.flush()

        for ordinal, item in enumerate(snapshot.departments):
            session.add(SurveyDepartmentConclusionRow(
                survey_conclusion_id=plan.survey_conclusion_id,
                conclusion_series_id=plan.conclusion_series_id,
                project_id=plan.project_id,
                department_id=item.department_id,
                title=item.title,
                statement=item.statement,
                response_refs=list(item.response_refs),
                decision_type=None,
                decision_reason=None,
                decision_impact=None,
                decision_evidence_id=None,
                decision_review_ref=None,
                ordinal=ordinal,
            ))
        for ordinal, item in enumerate(snapshot.modules):
            session.add(SurveyModuleConclusionRow(
                survey_conclusion_id=plan.survey_conclusion_id,
                conclusion_series_id=plan.conclusion_series_id,
                project_id=plan.project_id,
                module_key=item.module_key,
                title=item.title,
                statement=item.statement,
                response_refs=list(item.response_refs),
                decision_type=None,
                decision_reason=None,
                decision_impact=None,
                decision_evidence_id=None,
                decision_review_ref=None,
                ordinal=ordinal,
            ))
        evidence_by_id = {
            item.evidence_id: item for item in snapshot.evidence_proofs
        }
        for ordinal, item in enumerate(snapshot.evidence_inputs):
            proof = evidence_by_id[item.evidence_id]
            session.add(SurveyConclusionEvidenceRefRow(
                survey_conclusion_id=plan.survey_conclusion_id,
                conclusion_series_id=plan.conclusion_series_id,
                project_id=plan.project_id,
                reference_role=item.reference_role,
                document_id=proof.document_id,
                document_version_id=proof.document_version_id,
                evidence_id=proof.evidence_id,
                observed_evidence_lock_version=(
                    proof.observed_evidence_lock_version
                ),
                content_fingerprint=proof.content_fingerprint,
                ordinal=ordinal,
            ))
        issues_by_id = {
            item.action_item_id: item for item in snapshot.issue_proofs
        }
        for ordinal, item in enumerate(snapshot.issue_inputs):
            proof = issues_by_id[item.action_item_id]
            session.add(SurveyConclusionOpenIssueRow(
                survey_conclusion_id=plan.survey_conclusion_id,
                conclusion_series_id=plan.conclusion_series_id,
                project_id=plan.project_id,
                issue_owner_module="handover",
                issue_object_type="HND-03",
                issue_id=proof.action_item_id,
                observed_issue_state=proof.action_state,
                observed_lock_version=proof.lock_version,
                is_blocking=item.is_blocking,
                ordinal=ordinal,
            ))
        session.flush()
        view = self.get_conclusion(
            transaction, project_id=plan.project_id,
            survey_conclusion_id=plan.survey_conclusion_id,
        )
        if view is None:
            raise SurveyConclusionCreateError()
        return view

    def get_initial(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyConclusionView | None:
        view = self.get_conclusion(
            transaction, project_id=project_id,
            survey_conclusion_id=survey_conclusion_id,
        )
        if (view is None or view.summary.created_by != actor_id
                or view.summary.conclusion_state != "DRAFT"):
            return None
        return view

    def list_conclusions(
        self, transaction: object, *, project_id: uuid.UUID,
        after_created_at: datetime | None,
        after_conclusion_id: uuid.UUID | None, limit: int,
    ) -> tuple[SurveyConclusionSummaryView, ...]:
        query = select(SurveyConclusionRow).where(
            SurveyConclusionRow.project_id == project_id,
        )
        if after_created_at is not None and after_conclusion_id is not None:
            query = query.where(or_(
                SurveyConclusionRow.created_at < after_created_at,
                and_(
                    SurveyConclusionRow.created_at == after_created_at,
                    SurveyConclusionRow.survey_conclusion_id < after_conclusion_id,
                ),
            ))
        rows = _session(transaction).execute(query.order_by(
            SurveyConclusionRow.created_at.desc(),
            SurveyConclusionRow.survey_conclusion_id.desc(),
        ).limit(limit)).scalars()
        return tuple(_summary(row) for row in rows)

    def get_conclusion(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_conclusion_id: uuid.UUID,
    ) -> SurveyConclusionView | None:
        session = _session(transaction)
        root = session.execute(select(SurveyConclusionRow).where(
            SurveyConclusionRow.project_id == project_id,
            SurveyConclusionRow.survey_conclusion_id == survey_conclusion_id,
        )).scalar_one_or_none()
        if root is None:
            return None
        departments = tuple(DepartmentConclusionView(
            row.department_conclusion_id, row.department_id, row.title,
            row.statement, tuple(row.response_refs), row.ordinal,
        ) for row in session.execute(select(
            SurveyDepartmentConclusionRow,
        ).where(
            SurveyDepartmentConclusionRow.project_id == project_id,
            SurveyDepartmentConclusionRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyDepartmentConclusionRow.ordinal)).scalars())
        modules = tuple(ModuleConclusionView(
            row.module_conclusion_id, row.module_key, row.title,
            row.statement, tuple(row.response_refs), row.ordinal,
        ) for row in session.execute(select(
            SurveyModuleConclusionRow,
        ).where(
            SurveyModuleConclusionRow.project_id == project_id,
            SurveyModuleConclusionRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyModuleConclusionRow.ordinal)).scalars())
        evidence = tuple(ConclusionEvidenceView(
            row.conclusion_evidence_ref_id, row.reference_role,
            row.document_id, row.document_version_id, row.evidence_id,
            row.observed_evidence_lock_version,
            bytes(row.content_fingerprint).hex(), row.ordinal,
        ) for row in session.execute(select(
            SurveyConclusionEvidenceRefRow,
        ).where(
            SurveyConclusionEvidenceRefRow.project_id == project_id,
            SurveyConclusionEvidenceRefRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyConclusionEvidenceRefRow.ordinal)).scalars())
        issues = tuple(ConclusionOpenIssueView(
            row.conclusion_open_issue_ref_id, row.issue_owner_module,
            row.issue_object_type, row.issue_id, row.observed_issue_state,
            row.observed_lock_version, row.is_blocking, row.ordinal,
        ) for row in session.execute(select(
            SurveyConclusionOpenIssueRow,
        ).where(
            SurveyConclusionOpenIssueRow.project_id == project_id,
            SurveyConclusionOpenIssueRow.survey_conclusion_id
            == survey_conclusion_id,
        ).order_by(SurveyConclusionOpenIssueRow.ordinal)).scalars())
        return SurveyConclusionView(
            _summary(root), departments, modules, evidence, issues,
        )
