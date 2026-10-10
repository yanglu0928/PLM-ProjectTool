"""PostgreSQL persistence for atomic DRAFT PrototypeVersion creation."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionCreateError, PrototypeVersionInitialView,
    VersionArtifactRef, VersionRequirementRef,
)

from .orm import (
    PrototypeInteractionSpecRow, PrototypeRow, PrototypeVersionArtifactRefRow,
    PrototypeVersionCreateResultRow, PrototypeVersionRequirementRefRow,
    PrototypeVersionRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active PrototypeVersion transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active PrototypeVersion transaction is required")
    return session


class SqlAlchemyPrototypeVersionCreateRepository:
    def create(self, transaction: object, *, result_id: uuid.UUID,
               version_id: uuid.UUID, project_id: uuid.UUID,
               prototype_id: uuid.UUID, template_id: uuid.UUID,
               template_version_id: uuid.UUID,
               expected_lock_version: int,
               artifacts: tuple[VersionArtifactRef, ...],
               requirements: tuple[VersionRequirementRef, ...],
               interaction: dict[str, object], interaction_fingerprint: bytes,
               coverage: dict[str, object], content_fingerprint: bytes,
               actor_id: uuid.UUID) -> PrototypeVersionInitialView:
        session = _session(transaction)
        root = session.execute(select(PrototypeRow).where(
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.prototype_state == "ACTIVE",
        ).with_for_update(of=PrototypeRow)).scalar_one_or_none()
        if root is None:
            raise RuntimeError("Prototype is unavailable")
        if root.lock_version != expected_lock_version:
            raise PrototypeVersionCreateError("CONFLICT_VERSION")
        prior = session.execute(select(PrototypeVersionRow).where(
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
        ).order_by(PrototypeVersionRow.version_no.desc()).limit(1)).scalar_one_or_none()
        number = 1 if prior is None else prior.version_no + 1
        supersedes = None if prior is None else prior.prototype_version_id
        changed = session.execute(update(PrototypeRow).where(
            PrototypeRow.prototype_id == prototype_id,
            PrototypeRow.project_id == project_id,
            PrototypeRow.prototype_state == "ACTIVE",
            PrototypeRow.lock_version == expected_lock_version,
        ).values(
            updated_by=actor_id,
            updated_at=text("statement_timestamp()"),
            lock_version=expected_lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise PrototypeVersionCreateError("CONFLICT_VERSION")
        session.execute(insert(PrototypeVersionRow).values(
            prototype_version_id=version_id, prototype_id=prototype_id,
            project_id=project_id, version_no=number, version_state="DRAFT",
            template_ref=template_id, template_version_ref=template_version_id,
            coverage_summary=coverage, content_fingerprint=content_fingerprint,
            declared_artifact_count=len(artifacts),
            declared_requirement_count=len(requirements),
            declared_interaction_count=1, supersedes_version_ref=supersedes,
            review_ref=None, review_round_ref=None, created_by=actor_id))
        for ordinal, item in enumerate(artifacts, 1):
            session.execute(insert(PrototypeVersionArtifactRefRow).values(
                prototype_version_id=version_id, prototype_id=prototype_id,
                project_id=project_id, artifact_kind=item.artifact_kind,
                target_id=item.target_id, ordinal=ordinal))
        for ordinal, item in enumerate(requirements, 1):
            session.execute(insert(PrototypeVersionRequirementRefRow).values(
                prototype_version_id=version_id, prototype_id=prototype_id,
                project_id=project_id, requirement_id=item.requirement_id,
                requirement_version_id=item.requirement_version_id, ordinal=ordinal))
        session.execute(insert(PrototypeInteractionSpecRow).values(
            prototype_version_id=version_id, prototype_id=prototype_id,
            project_id=project_id, schema_version=1, specification=interaction,
            content_fingerprint=interaction_fingerprint))
        session.execute(insert(PrototypeVersionCreateResultRow).values(
            result_id=result_id, prototype_version_id=version_id,
            prototype_id=prototype_id, project_id=project_id,
            version_no=number, prototype_lock_version=expected_lock_version + 1,
            content_fingerprint=content_fingerprint,
            declared_artifact_count=len(artifacts),
            declared_requirement_count=len(requirements),
            declared_interaction_count=1))
        view = self.result(transaction, result_id=result_id,
                           project_id=project_id, prototype_id=prototype_id)
        if view is None:
            raise RuntimeError("PrototypeVersion result was not persisted")
        return view

    def result(self, transaction: object, *, result_id: uuid.UUID,
               project_id: uuid.UUID,
               prototype_id: uuid.UUID) -> PrototypeVersionInitialView | None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in
               (result_id, project_id, prototype_id)):
            return None
        session = _session(transaction)
        row = session.execute(select(
            PrototypeVersionCreateResultRow, PrototypeVersionRow,
            PrototypeInteractionSpecRow,
        ).join(
            PrototypeVersionRow,
            PrototypeVersionRow.prototype_version_id
            == PrototypeVersionCreateResultRow.prototype_version_id,
        ).join(
            PrototypeInteractionSpecRow,
            PrototypeInteractionSpecRow.prototype_version_id
            == PrototypeVersionCreateResultRow.prototype_version_id,
        ).where(
            PrototypeVersionCreateResultRow.result_id == result_id,
            PrototypeVersionCreateResultRow.project_id == project_id,
            PrototypeVersionCreateResultRow.prototype_id == prototype_id,
            PrototypeVersionRow.project_id == project_id,
            PrototypeVersionRow.prototype_id == prototype_id,
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        result, version, spec = row
        artifacts = tuple(VersionArtifactRef(x.artifact_kind, x.target_id) for x in
            session.execute(select(PrototypeVersionArtifactRefRow).where(
                PrototypeVersionArtifactRefRow.prototype_version_id
                == version.prototype_version_id).order_by(
                PrototypeVersionArtifactRefRow.ordinal)).scalars())
        requirements = tuple(VersionRequirementRef(x.requirement_id, x.requirement_version_id)
            for x in session.execute(select(PrototypeVersionRequirementRefRow).where(
                PrototypeVersionRequirementRefRow.prototype_version_id
                == version.prototype_version_id).order_by(
                PrototypeVersionRequirementRefRow.ordinal)).scalars())
        if (len(artifacts) != result.declared_artifact_count
            or len(requirements) != result.declared_requirement_count):
            return None
        return PrototypeVersionInitialView(
            version.prototype_version_id, version.prototype_id, version.project_id,
            version.version_no, version.supersedes_version_ref, version.template_ref,
            version.template_version_ref, artifacts, requirements,
            dict(spec.specification), dict(version.coverage_summary),
            bytes(version.content_fingerprint).hex(), result.created_at,
            version_state=version.version_state,
            expected_lock_version=(None if result.prototype_lock_version is None
                                   else result.prototype_lock_version - 1))
