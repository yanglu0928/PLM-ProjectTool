"""Requirement-owned identity creation and immutable replay persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from plm_assistant.modules.requirement.application.create_identity import (
    RequirementIdentityCreateError,
    RequirementInitialView,
    RequirementPackageInitialView,
)

from .orm import (
    RequirementCreateResultRow,
    RequirementPackageCreateResultRow,
    RequirementPackageRow,
    RequirementRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Requirement transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Requirement transaction is required")
    return session


class SqlAlchemyRequirementIdentityCreateRepository:
    def create_package(
        self,
        transaction: object,
        *,
        requirement_package_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        actor_id: uuid.UUID,
    ) -> RequirementPackageInitialView:
        session = _session(transaction)
        created_at = session.execute(
            insert(RequirementPackageRow)
            .values(
                requirement_package_id=requirement_package_id,
                project_id=project_id,
                name=name,
                package_state="ACTIVE",
                created_by=actor_id,
                updated_by=None,
                lock_version=0,
            )
            .returning(RequirementPackageRow.created_at)
        ).scalar_one()
        session.execute(
            insert(RequirementPackageCreateResultRow).values(
                requirement_package_id=requirement_package_id,
                project_id=project_id,
                name=name,
                created_at=created_at,
            )
        )
        return RequirementPackageInitialView(
            requirement_package_id, project_id, name, created_at
        )

    def package_result(
        self,
        transaction: object,
        *,
        requirement_package_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> RequirementPackageInitialView | None:
        row = _session(transaction).execute(
            select(RequirementPackageCreateResultRow).where(
                RequirementPackageCreateResultRow.requirement_package_id
                == requirement_package_id,
                RequirementPackageCreateResultRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return RequirementPackageInitialView(
            row.requirement_package_id, row.project_id, row.name, row.created_at
        )

    def create_requirement(
        self,
        transaction: object,
        *,
        requirement_id: uuid.UUID,
        project_id: uuid.UUID,
        requirement_code: str,
        requirement_code_normalized: str,
        actor_id: uuid.UUID,
    ) -> RequirementInitialView:
        session = _session(transaction)
        try:
            created_at = session.execute(
                insert(RequirementRow)
                .values(
                    requirement_id=requirement_id,
                    project_id=project_id,
                    requirement_code=requirement_code,
                    requirement_code_normalized=requirement_code_normalized,
                    requirement_state="ACTIVE",
                    current_approved_version_ref=None,
                    created_by=actor_id,
                    updated_by=None,
                    lock_version=0,
                )
                .returning(RequirementRow.created_at)
            ).scalar_one()
        except IntegrityError as error:
            original = error.orig
            if (
                getattr(original, "sqlstate", None) == "23505"
                and getattr(getattr(original, "diag", None), "constraint_name", None)
                == "uq_req_requirements__project_code"
            ):
                raise RequirementIdentityCreateError("CONFLICT_DUPLICATE") from None
            raise
        session.execute(
            insert(RequirementCreateResultRow).values(
                requirement_id=requirement_id,
                project_id=project_id,
                requirement_code=requirement_code,
                created_at=created_at,
            )
        )
        return RequirementInitialView(
            requirement_id, project_id, requirement_code, created_at
        )

    def requirement_result(
        self,
        transaction: object,
        *,
        requirement_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> RequirementInitialView | None:
        row = _session(transaction).execute(
            select(RequirementCreateResultRow).where(
                RequirementCreateResultRow.requirement_id == requirement_id,
                RequirementCreateResultRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return RequirementInitialView(
            row.requirement_id,
            row.project_id,
            row.requirement_code,
            row.created_at,
        )
