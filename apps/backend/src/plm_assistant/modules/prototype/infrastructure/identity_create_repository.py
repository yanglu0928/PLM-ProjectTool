"""Prototype-owned identity creation and immutable replay persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.create_identity import (
    PrototypeInitialView, PrototypePackageInitialView,
)
from .orm import (
    PrototypeCreateResultRow, PrototypePackageCreateResultRow,
    PrototypePackageRow, PrototypeRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Prototype transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prototype transaction is required")
    return session


class SqlAlchemyPrototypeIdentityCreateRepository:
    def create_package(
        self, transaction: object, *, prototype_package_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> PrototypePackageInitialView:
        session = _session(transaction)
        created_at = session.execute(insert(PrototypePackageRow).values(
            prototype_package_id=prototype_package_id, project_id=project_id,
            name=name, package_state="ACTIVE", created_by=actor_id,
            updated_by=None, lock_version=0,
        ).returning(PrototypePackageRow.created_at)).scalar_one()
        session.execute(insert(PrototypePackageCreateResultRow).values(
            prototype_package_id=prototype_package_id, project_id=project_id,
            name=name, created_at=created_at,
        ))
        return PrototypePackageInitialView(
            prototype_package_id, project_id, name, created_at,
        )

    def package_result(
        self, transaction: object, *, prototype_package_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PrototypePackageInitialView | None:
        row = _session(transaction).execute(
            select(PrototypePackageCreateResultRow).where(
                PrototypePackageCreateResultRow.prototype_package_id
                == prototype_package_id,
                PrototypePackageCreateResultRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        return None if row is None else PrototypePackageInitialView(
            row.prototype_package_id, row.project_id, row.name, row.created_at,
        )

    def create_prototype(
        self, transaction: object, *, prototype_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> PrototypeInitialView:
        session = _session(transaction)
        created_at = session.execute(insert(PrototypeRow).values(
            prototype_id=prototype_id, project_id=project_id, name=name,
            prototype_state="ACTIVE", current_approved_version_ref=None,
            created_by=actor_id, updated_by=None, lock_version=0,
        ).returning(PrototypeRow.created_at)).scalar_one()
        session.execute(insert(PrototypeCreateResultRow).values(
            prototype_id=prototype_id, project_id=project_id,
            name=name, created_at=created_at,
        ))
        return PrototypeInitialView(prototype_id, project_id, name, created_at)

    def prototype_result(
        self, transaction: object, *, prototype_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PrototypeInitialView | None:
        row = _session(transaction).execute(
            select(PrototypeCreateResultRow).where(
                PrototypeCreateResultRow.prototype_id == prototype_id,
                PrototypeCreateResultRow.project_id == project_id,
            )
        ).scalar_one_or_none()
        return None if row is None else PrototypeInitialView(
            row.prototype_id, row.project_id, row.name, row.created_at,
        )
