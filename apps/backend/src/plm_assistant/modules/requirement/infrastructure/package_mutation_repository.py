"""Requirement-owned Package mutation and immutable replay persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.requirement.application.mutate_package import (
    RequirementPackageMutationError, RequirementPackageView,
)
from .orm import (
    RequirementPackageCommandResultRow, RequirementPackageMembershipRow,
    RequirementPackageRow, RequirementRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Requirement transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Requirement transaction is required")
    return session


def _view(row: RequirementPackageCommandResultRow) -> RequirementPackageView:
    return RequirementPackageView(
        row.requirement_package_id, row.project_id, row.name, row.package_state,
        tuple(row.member_refs), f'"v{row.lock_version}"',
    )


class SqlAlchemyRequirementPackageMutationRepository:
    def mutate(self, transaction: object, *, result_id: uuid.UUID, operation: str,
               project_id: uuid.UUID, requirement_package_id: uuid.UUID,
               expected_version: int, actor_id: uuid.UUID, name: str | None,
               package_state: str | None,
               requirement_ids: tuple[uuid.UUID, ...]) -> RequirementPackageView:
        session = _session(transaction)
        package = session.execute(select(RequirementPackageRow).where(
            RequirementPackageRow.requirement_package_id == requirement_package_id,
            RequirementPackageRow.project_id == project_id,
        ).with_for_update(of=RequirementPackageRow)).scalar_one_or_none()
        if package is None:
            raise RequirementPackageMutationError("RESOURCE_NOT_FOUND")
        if package.lock_version != expected_version:
            raise RequirementPackageMutationError("CONFLICT_VERSION")
        if package.package_state == "ARCHIVED":
            raise RequirementPackageMutationError("REQUIREMENT_STATE_INVALID")

        current = set(session.execute(select(
            RequirementPackageMembershipRow.requirement_id
        ).where(
            RequirementPackageMembershipRow.requirement_package_id == requirement_package_id,
            RequirementPackageMembershipRow.project_id == project_id,
        )).scalars())
        new_name = package.name if name is None else name
        new_state = package.package_state if package_state is None else package_state
        requested = set(requirement_ids)

        if operation == "PATCH":
            if new_name == package.name and new_state == package.package_state:
                raise RequirementPackageMutationError("CONFLICT_NO_CHANGE")
        elif operation == "ADD":
            if package.package_state != "ACTIVE":
                raise RequirementPackageMutationError("REQUIREMENT_STATE_INVALID")
            existing_requirements = set(session.execute(select(RequirementRow.requirement_id).where(
                RequirementRow.project_id == project_id,
                RequirementRow.requirement_id.in_(requested),
            )).scalars())
            if existing_requirements != requested:
                raise RequirementPackageMutationError("RESOURCE_NOT_FOUND")
            if current.intersection(requested):
                raise RequirementPackageMutationError("CONFLICT_DUPLICATE")
            session.execute(insert(RequirementPackageMembershipRow), [{
                "requirement_package_id": requirement_package_id,
                "requirement_id": item, "project_id": project_id, "added_by": actor_id,
            } for item in requirement_ids])
            current.update(requested)
        elif operation == "REMOVE":
            if package.package_state != "ACTIVE":
                raise RequirementPackageMutationError("REQUIREMENT_STATE_INVALID")
            if not requested.issubset(current):
                raise RequirementPackageMutationError("RESOURCE_NOT_FOUND")
            session.execute(delete(RequirementPackageMembershipRow).where(
                RequirementPackageMembershipRow.requirement_package_id == requirement_package_id,
                RequirementPackageMembershipRow.project_id == project_id,
                RequirementPackageMembershipRow.requirement_id.in_(requested),
            ))
            current.difference_update(requested)
        else:
            raise RequirementPackageMutationError("VALIDATION_FAILED")

        next_version = package.lock_version + 1
        changed = session.execute(update(RequirementPackageRow).where(
            RequirementPackageRow.requirement_package_id == requirement_package_id,
            RequirementPackageRow.project_id == project_id,
            RequirementPackageRow.lock_version == package.lock_version,
        ).values(
            name=new_name, package_state=new_state, updated_by=actor_id,
            updated_at=func.statement_timestamp(), lock_version=next_version,
        ))
        if changed.rowcount != 1:
            raise RequirementPackageMutationError("CONFLICT_VERSION")
        member_refs = sorted(current, key=str)
        session.execute(insert(RequirementPackageCommandResultRow).values(
            result_id=result_id, requirement_package_id=requirement_package_id,
            project_id=project_id, operation=operation, name=new_name,
            package_state=new_state, member_refs=member_refs,
            lock_version=next_version,
        ))
        return RequirementPackageView(
            requirement_package_id, project_id, new_name, new_state,
            tuple(member_refs), f'"v{next_version}"',
        )

    def result(self, transaction: object, *, result_id: uuid.UUID,
               project_id: uuid.UUID, requirement_package_id: uuid.UUID,
               operation: str) -> RequirementPackageView | None:
        row = _session(transaction).execute(select(
            RequirementPackageCommandResultRow
        ).where(
            RequirementPackageCommandResultRow.result_id == result_id,
            RequirementPackageCommandResultRow.project_id == project_id,
            RequirementPackageCommandResultRow.requirement_package_id == requirement_package_id,
            RequirementPackageCommandResultRow.operation == operation,
        )).scalar_one_or_none()
        return None if row is None else _view(row)
