"""Prototype identity mutation and immutable replay persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.mutate_prototype import (
    PrototypeIdentityView, PrototypeMutationError,
)
from .orm import PrototypeCommandResultRow, PrototypeRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Prototype transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prototype transaction is required")
    return session


def _view(row: PrototypeCommandResultRow) -> PrototypeIdentityView:
    return PrototypeIdentityView(
        row.prototype_id, row.project_id, row.name, row.prototype_state,
        row.current_approved_version_ref, f'"v{row.lock_version}"',
    )


class SqlAlchemyPrototypeMutationRepository:
    def mutate(
        self, transaction: object, *, result_id: uuid.UUID, operation: str,
        project_id: uuid.UUID, prototype_id: uuid.UUID, expected_version: int,
        actor_id: uuid.UUID, name: str | None,
    ) -> PrototypeIdentityView:
        session = _session(transaction)
        root = session.execute(select(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
        ).with_for_update(of=PrototypeRow)).scalar_one_or_none()
        if root is None:
            raise PrototypeMutationError("RESOURCE_NOT_FOUND")
        if root.lock_version != expected_version:
            raise PrototypeMutationError("CONFLICT_VERSION")
        if root.prototype_state == "ARCHIVED":
            raise PrototypeMutationError("PROTOTYPE_STATE_INVALID")

        new_name, new_state = root.name, root.prototype_state
        if operation == "PATCH":
            if root.prototype_state != "ACTIVE":
                raise PrototypeMutationError("PROTOTYPE_STATE_INVALID")
            if name is None or name == root.name:
                raise PrototypeMutationError("CONFLICT_NO_CHANGE")
            new_name = name
        elif operation == "ARCHIVE":
            new_state = "ARCHIVED"
        else:
            raise PrototypeMutationError("VALIDATION_FAILED")

        next_version = root.lock_version + 1
        changed = session.execute(update(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
            PrototypeRow.lock_version == root.lock_version,
        ).values(
            name=new_name, prototype_state=new_state, updated_by=actor_id,
            updated_at=func.statement_timestamp(), lock_version=next_version,
        ))
        if changed.rowcount != 1:
            raise PrototypeMutationError("CONFLICT_VERSION")
        session.execute(insert(PrototypeCommandResultRow).values(
            result_id=result_id, prototype_id=prototype_id, project_id=project_id,
            operation=operation, name=new_name, prototype_state=new_state,
            current_approved_version_ref=root.current_approved_version_ref,
            lock_version=next_version,
        ))
        return PrototypeIdentityView(
            prototype_id, project_id, new_name, new_state,
            root.current_approved_version_ref, f'"v{next_version}"',
        )

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
        project_id: uuid.UUID, prototype_id: uuid.UUID, operation: str,
    ) -> PrototypeIdentityView | None:
        row = _session(transaction).execute(select(
            PrototypeCommandResultRow,
        ).where(
            PrototypeCommandResultRow.result_id == result_id,
            PrototypeCommandResultRow.project_id == project_id,
            PrototypeCommandResultRow.prototype_id == prototype_id,
            PrototypeCommandResultRow.operation == operation,
        )).scalar_one_or_none()
        return None if row is None else _view(row)
