"""Immutable PrototypeVersion list/get reconstruction."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView, VersionArtifactRef, VersionRequirementRef,
)
from .orm import (
    PrototypeInteractionSpecRow, PrototypeVersionArtifactRefRow,
    PrototypeVersionCreateResultRow, PrototypeVersionRequirementRefRow,
    PrototypeVersionRow,
)


class SqlAlchemyPrototypeVersionReadRepository:
    @staticmethod
    def _session(transaction: object) -> Session:
        try: session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError) as error:
            raise RuntimeError("active PrototypeVersion transaction is required") from error
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active PrototypeVersion transaction is required")
        return session

    def list(self, transaction: object, *, project_id: uuid.UUID,
             prototype_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[PrototypeVersionInitialView, ...]:
        session = self._session(transaction)
        query = select(PrototypeVersionRow.prototype_version_id).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id)
        if before_version_no is not None:
            query = query.where(PrototypeVersionRow.version_no < before_version_no)
        ids = session.execute(query.order_by(
            PrototypeVersionRow.version_no.desc()).limit(limit)).scalars()
        return tuple(view for version_id in ids if (view := self.get(
            transaction, project_id=project_id, prototype_id=prototype_id,
            version_id=version_id)) is not None)

    def get(self, transaction: object, *, project_id: uuid.UUID,
            prototype_id: uuid.UUID,
            version_id: uuid.UUID) -> PrototypeVersionInitialView | None:
        session = self._session(transaction)
        row = session.execute(select(
            PrototypeVersionRow, PrototypeInteractionSpecRow,
            PrototypeVersionCreateResultRow,
        ).join(
            PrototypeInteractionSpecRow,
            PrototypeInteractionSpecRow.prototype_version_id
            == PrototypeVersionRow.prototype_version_id,
        ).join(
            PrototypeVersionCreateResultRow,
            PrototypeVersionCreateResultRow.prototype_version_id
            == PrototypeVersionRow.prototype_version_id,
        ).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
            PrototypeVersionRow.prototype_version_id == version_id,
            PrototypeInteractionSpecRow.project_id == project_id,
            PrototypeInteractionSpecRow.prototype_id == prototype_id,
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None: return None
        version, spec, result = row
        artifacts = tuple(VersionArtifactRef(x.artifact_kind, x.target_id) for x in
            session.execute(select(PrototypeVersionArtifactRefRow).where(
                PrototypeVersionArtifactRefRow.prototype_version_id == version_id,
                PrototypeVersionArtifactRefRow.project_id == project_id,
                PrototypeVersionArtifactRefRow.prototype_id == prototype_id,
            ).order_by(PrototypeVersionArtifactRefRow.ordinal)).scalars())
        requirements = tuple(VersionRequirementRef(x.requirement_id, x.requirement_version_id)
            for x in session.execute(select(PrototypeVersionRequirementRefRow).where(
                PrototypeVersionRequirementRefRow.prototype_version_id == version_id,
                PrototypeVersionRequirementRefRow.project_id == project_id,
                PrototypeVersionRequirementRefRow.prototype_id == prototype_id,
            ).order_by(PrototypeVersionRequirementRefRow.ordinal)).scalars())
        if (len(artifacts) != version.declared_artifact_count
            or len(requirements) != version.declared_requirement_count
            or version.declared_interaction_count != 1):
            raise RuntimeError("PrototypeVersion owned set is incomplete")
        return PrototypeVersionInitialView(
            version.prototype_version_id, version.prototype_id, version.project_id,
            version.version_no, version.supersedes_version_ref, version.template_ref,
            version.template_version_ref, artifacts, requirements,
            dict(spec.specification), dict(version.coverage_summary),
            bytes(version.content_fingerprint).hex(), version.created_at,
            version_state=version.version_state,
            expected_lock_version=(None if result.prototype_lock_version is None
                                   else result.prototype_lock_version - 1))
