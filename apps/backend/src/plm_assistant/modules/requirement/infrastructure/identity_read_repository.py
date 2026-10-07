"""PostgreSQL projections for RequirementPackage and Requirement reads."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.requirement.application.read_identities import (
    RequirementPackageSummary, RequirementPackageView, RequirementSummary,
)

from .identity_create_repository import _session
from .orm import (
    RequirementPackageMembershipRow, RequirementPackageRow, RequirementRow,
)


def _package(row: RequirementPackageRow) -> RequirementPackageSummary:
    return RequirementPackageSummary(
        row.requirement_package_id, row.project_id, row.name,
        row.package_state, row.created_by, row.created_at, row.updated_by,
        row.updated_at, f'"v{row.lock_version}"')


def _requirement(row: RequirementRow) -> RequirementSummary:
    return RequirementSummary(
        row.requirement_id, row.project_id, row.requirement_code,
        row.requirement_state, row.current_approved_version_ref,
        row.created_by, row.created_at, row.updated_by, row.updated_at,
        f'"v{row.lock_version}"')


class SqlAlchemyRequirementIdentityReadRepository:
    def list_packages(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_requirement_package_id: uuid.UUID | None, limit: int,
    ) -> tuple[RequirementPackageSummary, ...]:
        query = select(RequirementPackageRow).where(
            RequirementPackageRow.project_id == project_id)
        if (after_updated_at is not None
                and after_requirement_package_id is not None):
            query = query.where(or_(
                RequirementPackageRow.updated_at < after_updated_at,
                and_(
                    RequirementPackageRow.updated_at == after_updated_at,
                    RequirementPackageRow.requirement_package_id
                    < after_requirement_package_id)))
        rows = _session(transaction).execute(query.order_by(
            RequirementPackageRow.updated_at.desc(),
            RequirementPackageRow.requirement_package_id.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_package(row) for row in rows)

    def get_package(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_package_id: uuid.UUID,
    ) -> RequirementPackageView | None:
        session = _session(transaction)
        row = session.execute(select(RequirementPackageRow).where(
            RequirementPackageRow.project_id == project_id,
            RequirementPackageRow.requirement_package_id
            == requirement_package_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        member_ids = tuple(session.execute(select(
            RequirementPackageMembershipRow.requirement_id,
        ).where(
            RequirementPackageMembershipRow.project_id == project_id,
            RequirementPackageMembershipRow.requirement_package_id
            == requirement_package_id,
        ).order_by(
            RequirementPackageMembershipRow.requirement_id,
        )).scalars().all())
        return RequirementPackageView(_package(row), member_ids)

    def list_requirements(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_requirement_id: uuid.UUID | None, limit: int,
    ) -> tuple[RequirementSummary, ...]:
        query = select(RequirementRow).where(
            RequirementRow.project_id == project_id)
        if after_updated_at is not None and after_requirement_id is not None:
            query = query.where(or_(
                RequirementRow.updated_at < after_updated_at,
                and_(RequirementRow.updated_at == after_updated_at,
                     RequirementRow.requirement_id < after_requirement_id)))
        rows = _session(transaction).execute(query.order_by(
            RequirementRow.updated_at.desc(),
            RequirementRow.requirement_id.desc(),
        ).limit(limit)).scalars().all()
        return tuple(_requirement(row) for row in rows)

    def get_requirement(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> RequirementSummary | None:
        row = _session(transaction).execute(select(RequirementRow).where(
            RequirementRow.project_id == project_id,
            RequirementRow.requirement_id == requirement_id,
        )).scalar_one_or_none()
        return None if row is None else _requirement(row)
