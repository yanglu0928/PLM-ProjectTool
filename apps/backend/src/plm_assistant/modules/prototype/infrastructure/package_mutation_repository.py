"""PrototypePackage mutation and immutable replay persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.mutate_package import (
    PrototypePackageMutationError, PrototypePackageView,
)
from .orm import (
    PrototypePackageCommandResultRow, PrototypePackageMembershipRow,
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


def _view(row: PrototypePackageCommandResultRow) -> PrototypePackageView:
    return PrototypePackageView(
        row.prototype_package_id, row.project_id, row.name, row.package_state,
        tuple(row.member_refs), f'"v{row.lock_version}"',
    )


class SqlAlchemyPrototypePackageMutationRepository:
    def mutate(
        self, transaction: object, *, result_id: uuid.UUID, operation: str,
        project_id: uuid.UUID, prototype_package_id: uuid.UUID,
        expected_version: int, actor_id: uuid.UUID, name: str | None,
        prototype_ids: tuple[uuid.UUID, ...],
    ) -> PrototypePackageView:
        session = _session(transaction)
        package = session.execute(select(PrototypePackageRow).where(
            PrototypePackageRow.prototype_package_id == prototype_package_id,
            PrototypePackageRow.project_id == project_id,
        ).with_for_update(of=PrototypePackageRow)).scalar_one_or_none()
        if package is None:
            raise PrototypePackageMutationError("RESOURCE_NOT_FOUND")
        if package.lock_version != expected_version:
            raise PrototypePackageMutationError("CONFLICT_VERSION")
        if package.package_state != "ACTIVE":
            raise PrototypePackageMutationError("PROTOTYPE_STATE_INVALID")
        current = set(session.execute(select(
            PrototypePackageMembershipRow.prototype_id,
        ).where(
            PrototypePackageMembershipRow.prototype_package_id == prototype_package_id,
            PrototypePackageMembershipRow.project_id == project_id,
        )).scalars())
        new_name = package.name
        requested = set(prototype_ids)
        if operation == "PATCH":
            if name is None or name == package.name:
                raise PrototypePackageMutationError("CONFLICT_NO_CHANGE")
            new_name = name
        elif operation == "SET_MEMBERS":
            if requested == current:
                raise PrototypePackageMutationError("CONFLICT_NO_CHANGE")
            existing = set(session.execute(select(PrototypeRow.prototype_id).where(
                PrototypeRow.project_id == project_id,
                PrototypeRow.prototype_id.in_(requested),
                PrototypeRow.prototype_state != "ARCHIVED",
            )).scalars()) if requested else set()
            if existing != requested:
                raise PrototypePackageMutationError("RESOURCE_NOT_FOUND")
            session.execute(delete(PrototypePackageMembershipRow).where(
                PrototypePackageMembershipRow.prototype_package_id == prototype_package_id,
                PrototypePackageMembershipRow.project_id == project_id,
            ))
            if prototype_ids:
                session.execute(insert(PrototypePackageMembershipRow), [{
                    "prototype_package_id": prototype_package_id,
                    "prototype_id": item, "project_id": project_id,
                    "added_by": actor_id,
                } for item in prototype_ids])
            current = requested
        else:
            raise PrototypePackageMutationError("VALIDATION_FAILED")
        next_version = package.lock_version + 1
        changed = session.execute(update(PrototypePackageRow).where(
            PrototypePackageRow.prototype_package_id == prototype_package_id,
            PrototypePackageRow.project_id == project_id,
            PrototypePackageRow.lock_version == package.lock_version,
        ).values(
            name=new_name, updated_by=actor_id,
            updated_at=func.statement_timestamp(), lock_version=next_version,
        ))
        if changed.rowcount != 1:
            raise PrototypePackageMutationError("CONFLICT_VERSION")
        member_refs = sorted(current, key=str)
        session.execute(insert(PrototypePackageCommandResultRow).values(
            result_id=result_id, prototype_package_id=prototype_package_id,
            project_id=project_id, operation=operation, name=new_name,
            package_state=package.package_state, member_refs=member_refs,
            lock_version=next_version,
        ))
        return PrototypePackageView(
            prototype_package_id, project_id, new_name, package.package_state,
            tuple(member_refs), f'"v{next_version}"',
        )

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
        project_id: uuid.UUID, prototype_package_id: uuid.UUID,
        operation: str,
    ) -> PrototypePackageView | None:
        row = _session(transaction).execute(select(
            PrototypePackageCommandResultRow,
        ).where(
            PrototypePackageCommandResultRow.result_id == result_id,
            PrototypePackageCommandResultRow.project_id == project_id,
            PrototypePackageCommandResultRow.prototype_package_id == prototype_package_id,
            PrototypePackageCommandResultRow.operation == operation,
        )).scalar_one_or_none()
        return None if row is None else _view(row)
