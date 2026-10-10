"""Project-owned active Department proof for Survey writes."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.survey_source_proof import (
    SurveyTargetDepartmentProof,
)

from .orm import DepartmentRow


class SqlAlchemySurveyTargetDepartmentProof:
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> SurveyTargetDepartmentProof | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(department_id) is not uuid.UUID or department_id.int == 0):
            return None
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project transaction is required")
        row = session.execute(select(
            DepartmentRow.department_id, DepartmentRow.project_id, DepartmentRow.state,
        ).where(
            DepartmentRow.department_id == department_id,
            DepartmentRow.project_id == project_id,
            DepartmentRow.state == "ACTIVE",
        ).with_for_update(read=True)).one_or_none()
        return None if row is None else SurveyTargetDepartmentProof(*row)
