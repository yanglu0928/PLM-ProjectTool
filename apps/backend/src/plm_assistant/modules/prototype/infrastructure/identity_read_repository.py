"""PostgreSQL reads for PrototypePackage and Prototype identities."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.prototype.application.read_identities import (
    PrototypePackageSummary, PrototypePackageView, PrototypeSummary,
)

from .identity_create_repository import _session
from .orm import (
    PrototypePackageMembershipRow, PrototypePackageRow, PrototypeRow,
)


class SqlAlchemyPrototypeIdentityReadRepository:
    def list_packages(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_prototype_package_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypePackageSummary, ...]:
        query = select(PrototypePackageRow).where(
            PrototypePackageRow.project_id == project_id,
        )
        if after_updated_at is not None:
            query = query.where(or_(
                PrototypePackageRow.updated_at < after_updated_at,
                and_(
                    PrototypePackageRow.updated_at == after_updated_at,
                    PrototypePackageRow.prototype_package_id
                    < after_prototype_package_id,
                ),
            ))
        rows = _session(transaction).execute(query.order_by(
            PrototypePackageRow.updated_at.desc(),
            PrototypePackageRow.prototype_package_id.desc(),
        ).limit(limit)).scalars()
        return tuple(self._package_summary(row) for row in rows)

    def get_package(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_package_id: uuid.UUID,
    ) -> PrototypePackageView | None:
        session = _session(transaction)
        row = session.execute(select(PrototypePackageRow).where(
            PrototypePackageRow.project_id == project_id,
            PrototypePackageRow.prototype_package_id == prototype_package_id,
        )).scalar_one_or_none()
        if row is None:
            return None
        members = tuple(session.execute(select(
            PrototypePackageMembershipRow.prototype_id,
        ).where(
            PrototypePackageMembershipRow.project_id == project_id,
            PrototypePackageMembershipRow.prototype_package_id
            == prototype_package_id,
        ).order_by(
            PrototypePackageMembershipRow.prototype_id,
        )).scalars())
        return PrototypePackageView(self._package_summary(row), members)

    def list_prototypes(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_prototype_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypeSummary, ...]:
        query = select(PrototypeRow).where(PrototypeRow.project_id == project_id)
        if after_updated_at is not None:
            query = query.where(or_(
                PrototypeRow.updated_at < after_updated_at,
                and_(
                    PrototypeRow.updated_at == after_updated_at,
                    PrototypeRow.prototype_id < after_prototype_id,
                ),
            ))
        rows = _session(transaction).execute(query.order_by(
            PrototypeRow.updated_at.desc(), PrototypeRow.prototype_id.desc(),
        ).limit(limit)).scalars()
        return tuple(self._prototype_summary(row) for row in rows)

    def get_prototype(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID,
    ) -> PrototypeSummary | None:
        row = _session(transaction).execute(select(PrototypeRow).where(
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_id == prototype_id,
        )).scalar_one_or_none()
        return None if row is None else self._prototype_summary(row)

    @staticmethod
    def _package_summary(row):
        return PrototypePackageSummary(
            row.prototype_package_id, row.project_id, row.name,
            row.package_state, row.created_by, row.created_at,
            row.updated_by, row.updated_at, f'"v{row.lock_version}"',
        )

    @staticmethod
    def _prototype_summary(row):
        return PrototypeSummary(
            row.prototype_id, row.project_id, row.name, row.prototype_state,
            row.current_approved_version_ref, row.created_by, row.created_at,
            row.updated_by, row.updated_at, f'"v{row.lock_version}"',
        )
