"""PrototypeTemplate create persistence and immutable replay view."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.prototype.application.create_template import (
    PrototypeTemplateInitialView, TemplateArtifactRef,
)

from .orm import (
    PrototypeTemplateArtifactRefRow, PrototypeTemplateCommandResultRow,
    PrototypeTemplateRow, PrototypeTemplateVersionRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active PrototypeTemplate transaction is required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active PrototypeTemplate transaction is required")
    return session


class SqlAlchemyPrototypeTemplateCreateRepository:
    def create(
        self, transaction: object, *, result_id: uuid.UUID,
        template_id: uuid.UUID, version_id: uuid.UUID, scope: str,
        project_id: uuid.UUID | None, name: str,
        layout_contract: dict[str, object], component_contract: dict[str, object],
        applicable_terminals: tuple[str, ...],
        artifact_refs: tuple[TemplateArtifactRef, ...],
        content_fingerprint: bytes, actor_id: uuid.UUID,
    ) -> PrototypeTemplateInitialView:
        session = _session(transaction)
        session.execute(insert(PrototypeTemplateRow).values(
            prototype_template_id=template_id, scope=scope, project_id=project_id,
            name=name, template_state="ACTIVE",
            current_template_version_ref=version_id, created_by=actor_id,
            updated_by=None, lock_version=0,
        ))
        session.execute(insert(PrototypeTemplateVersionRow).values(
            prototype_template_version_id=version_id,
            prototype_template_id=template_id, scope=scope, project_id=project_id,
            version_no=1, version_state="PUBLISHED",
            content_fingerprint=content_fingerprint,
            supersedes_version_id=None, layout_contract=layout_contract,
            component_contract=component_contract,
            applicable_terminals=list(applicable_terminals),
            declared_artifact_count=len(artifact_refs), created_by=actor_id,
        ))
        for ordinal, artifact in enumerate(artifact_refs, 1):
            session.execute(insert(PrototypeTemplateArtifactRefRow).values(
                prototype_template_version_id=version_id,
                prototype_template_id=template_id, scope=scope,
                project_id=project_id, artifact_kind=artifact.artifact_kind,
                target_id=artifact.target_id, ordinal=ordinal,
            ))
        session.execute(insert(PrototypeTemplateCommandResultRow).values(
            result_id=result_id, prototype_template_id=template_id,
            prototype_template_version_id=version_id, scope=scope,
            project_id=project_id, operation="CREATE", name=name,
            version_no=1, content_fingerprint=content_fingerprint,
            declared_artifact_count=len(artifact_refs), lock_version=0,
        ))
        view = self.result(transaction, result_id=result_id)
        if view is None:
            raise RuntimeError("PrototypeTemplate result was not persisted")
        return view

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
    ) -> PrototypeTemplateInitialView | None:
        if type(result_id) is not uuid.UUID or result_id.int == 0:
            return None
        session = _session(transaction)
        row = session.execute(select(
            PrototypeTemplateCommandResultRow,
            PrototypeTemplateVersionRow.layout_contract,
            PrototypeTemplateVersionRow.component_contract,
            PrototypeTemplateVersionRow.applicable_terminals,
            PrototypeTemplateVersionRow.version_state,
        ).join(
            PrototypeTemplateVersionRow,
            PrototypeTemplateVersionRow.prototype_template_version_id
            == PrototypeTemplateCommandResultRow.prototype_template_version_id,
        ).where(
            PrototypeTemplateCommandResultRow.result_id == result_id,
            PrototypeTemplateCommandResultRow.operation == "CREATE",
            PrototypeTemplateCommandResultRow.version_no == 1,
            PrototypeTemplateCommandResultRow.lock_version == 0,
            PrototypeTemplateVersionRow.prototype_template_id
            == PrototypeTemplateCommandResultRow.prototype_template_id,
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None:
            return None
        result = row[0]
        artifacts = tuple(
            TemplateArtifactRef(item.artifact_kind, item.target_id)
            for item in session.execute(select(
                PrototypeTemplateArtifactRefRow,
            ).where(
                PrototypeTemplateArtifactRefRow.prototype_template_version_id
                == result.prototype_template_version_id,
                PrototypeTemplateArtifactRefRow.prototype_template_id
                == result.prototype_template_id,
            ).order_by(
                PrototypeTemplateArtifactRefRow.ordinal,
            )).scalars()
        )
        if len(artifacts) != result.declared_artifact_count:
            return None
        return PrototypeTemplateInitialView(
            result.prototype_template_id,
            result.prototype_template_version_id,
            result.scope, result.project_id, result.name, result.version_no,
            dict(row.layout_contract), dict(row.component_contract),
            tuple(row.applicable_terminals), artifacts,
            bytes(result.content_fingerprint).hex(), result.created_at,
            version_state=row.version_state,
        )
