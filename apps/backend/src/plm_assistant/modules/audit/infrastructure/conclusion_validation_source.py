"""Audit-owned immutable replay proof for SurveyConclusion validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.survey.application.validate_conclusion import (
    ConclusionValidationAudit,
)

from .audit_orm import AuditEventRow


class SqlAlchemyConclusionValidationAuditSource:
    def get(
        self, transaction: object, *, audit_event_id: uuid.UUID,
        actor_id: uuid.UUID, project_id: uuid.UUID,
        conclusion_series_id: uuid.UUID, survey_conclusion_id: uuid.UUID,
    ) -> ConclusionValidationAudit | None:
        values = (
            audit_event_id, actor_id, project_id, conclusion_series_id,
            survey_conclusion_id,
        )
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            return None
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active Audit transaction required") from error
        row = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.action == "SURVEY_CONCLUSION_VALIDATED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "survey",
            AuditEventRow.target_object_type == "SRV-05",
            AuditEventRow.target_object_id == conclusion_series_id,
            AuditEventRow.target_version_id == survey_conclusion_id,
            AuditEventRow.before_state == AuditEventRow.after_state,
        ).execution_options(populate_existing=True)).scalar_one_or_none()
        if row is None or row.reason_code is None:
            return None
        return ConclusionValidationAudit(
            row.audit_event_id, row.trace_id, row.occurred_at, row.reason_code,
        )
