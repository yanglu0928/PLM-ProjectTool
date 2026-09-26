"""Project-owned conditional Department metadata mutation."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.patch_department import ProjectDepartmentPatchError
from plm_assistant.modules.project.application.read_departments import DepartmentFacts
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow


class SqlAlchemyProjectDepartmentPatchRepository:
    def patch(self, transaction: object, *, project_id: uuid.UUID,
              department_id: uuid.UUID, expected_version: int,
              code: str | None, normalized_code: str | None,
              name: str | None) -> tuple[DepartmentFacts, bool]:
        session = transaction.session  # type: ignore[attr-defined]
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Project Department transaction is required")
        department = session.execute(select(DepartmentRow).where(
            DepartmentRow.department_id == department_id,
            DepartmentRow.project_id == project_id,
        ).with_for_update(of=DepartmentRow)).scalar_one_or_none()
        if department is None:
            raise ProjectDepartmentPatchError("RESOURCE_NOT_FOUND")
        if department.lock_version != expected_version:
            raise ProjectDepartmentPatchError("CONFLICT_VERSION")
        if department.state != "ACTIVE":
            raise ProjectDepartmentPatchError("CONFLICT_STATE")
        new_code = department.department_code if code is None else code
        new_normalized = department.department_code_normalized if normalized_code is None else normalized_code
        new_name = department.name if name is None else name
        changed = (new_code != department.department_code
                   or new_normalized != department.department_code_normalized
                   or new_name != department.name)
        if not changed:
            return DepartmentFacts(
                department_id, project_id, department.department_code,
                department.name, department.state, department.created_at,
                department.lock_version,
            ), False
        if new_normalized != department.department_code_normalized:
            duplicate = session.execute(select(DepartmentRow.department_id).where(
                DepartmentRow.project_id == project_id,
                DepartmentRow.department_id != department_id,
                DepartmentRow.department_code_normalized == new_normalized,
                DepartmentRow.state == "ACTIVE",
            ).limit(1)).scalar_one_or_none()
            if duplicate is not None:
                raise ProjectDepartmentPatchError("CONFLICT_DUPLICATE")
        try:
            row = session.execute(update(DepartmentRow).where(
                DepartmentRow.department_id == department_id,
                DepartmentRow.project_id == project_id,
                DepartmentRow.state == "ACTIVE",
                DepartmentRow.lock_version == expected_version,
            ).values(
                department_code=new_code, department_code_normalized=new_normalized,
                name=new_name, lock_version=DepartmentRow.lock_version + 1,
                updated_at=func.statement_timestamp(),
            ).returning(
                DepartmentRow.department_id, DepartmentRow.project_id,
                DepartmentRow.department_code, DepartmentRow.name,
                DepartmentRow.state, DepartmentRow.created_at,
                DepartmentRow.lock_version,
            )).one_or_none()
        except IntegrityError as exc:
            original = exc.orig
            if (getattr(original, "sqlstate", None) == "23505"
                    and getattr(getattr(original, "diag", None), "constraint_name", None)
                    == "uq_prj_departments__project_code_live"):
                raise ProjectDepartmentPatchError("CONFLICT_DUPLICATE") from None
            raise
        if row is None:
            raise ProjectDepartmentPatchError("CONFLICT_VERSION")
        return DepartmentFacts(
            row.department_id, row.project_id, row.department_code,
            row.name, row.state, row.created_at, row.lock_version,
        ), True
