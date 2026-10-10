"""Locked PrototypeTemplate revision persistence and immutable replay."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update

from plm_assistant.modules.prototype.application.create_template import (
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.revise_template import (
    CurrentPrototypeTemplate, PrototypeTemplateRevisionView,
)

from .orm import (
    PrototypeTemplateArtifactRefRow, PrototypeTemplateCommandResultRow,
    PrototypeTemplateRow, PrototypeTemplateVersionRow,
)
from .template_create_repository import _session


class SqlAlchemyPrototypeTemplateReviseRepository:
    def current_for_update(
        self, transaction: object, *, template_id: uuid.UUID,
        scope: str, project_id: uuid.UUID | None,
    ) -> CurrentPrototypeTemplate | None:
        session = _session(transaction)
        row = session.execute(select(
            PrototypeTemplateRow, PrototypeTemplateVersionRow.version_no,
        ).join(
            PrototypeTemplateVersionRow,
            PrototypeTemplateVersionRow.prototype_template_version_id
            == PrototypeTemplateRow.current_template_version_ref,
        ).where(
            PrototypeTemplateRow.prototype_template_id == template_id,
            PrototypeTemplateRow.scope == scope,
            PrototypeTemplateRow.project_id.is_(None) if project_id is None else
            PrototypeTemplateRow.project_id == project_id,
            PrototypeTemplateVersionRow.prototype_template_id == template_id,
        ).with_for_update(of=PrototypeTemplateRow).execution_options(
            populate_existing=True,
        )).one_or_none()
        if row is None:
            return None
        root = row[0]
        return CurrentPrototypeTemplate(
            root.prototype_template_id, root.scope, root.project_id, root.name,
            root.template_state, root.current_template_version_ref,
            row.version_no, root.lock_version,
        )

    def revise(
        self, transaction: object, *, result_id: uuid.UUID,
        current: CurrentPrototypeTemplate, version_id: uuid.UUID,
        layout_contract: dict[str, object], component_contract: dict[str, object],
        applicable_terminals: tuple[str, ...],
        artifact_refs: tuple[TemplateArtifactRef, ...],
        content_fingerprint: bytes, actor_id: uuid.UUID,
    ) -> PrototypeTemplateRevisionView:
        session = _session(transaction)
        version_no = current.current_version_no + 1
        next_lock = current.lock_version + 1
        session.execute(insert(PrototypeTemplateVersionRow).values(
            prototype_template_version_id=version_id,
            prototype_template_id=current.prototype_template_id,
            scope=current.scope, project_id=current.project_id,
            version_no=version_no, version_state="PUBLISHED",
            content_fingerprint=content_fingerprint,
            supersedes_version_id=current.current_template_version_ref,
            layout_contract=layout_contract,
            component_contract=component_contract,
            applicable_terminals=list(applicable_terminals),
            declared_artifact_count=len(artifact_refs), created_by=actor_id,
        ))
        for ordinal, artifact in enumerate(artifact_refs, 1):
            session.execute(insert(PrototypeTemplateArtifactRefRow).values(
                prototype_template_version_id=version_id,
                prototype_template_id=current.prototype_template_id,
                scope=current.scope, project_id=current.project_id,
                artifact_kind=artifact.artifact_kind,
                target_id=artifact.target_id, ordinal=ordinal,
            ))
        changed = session.execute(update(PrototypeTemplateRow).where(
            PrototypeTemplateRow.prototype_template_id
            == current.prototype_template_id,
            PrototypeTemplateRow.scope == current.scope,
            PrototypeTemplateRow.project_id.is_(None)
            if current.project_id is None else
            PrototypeTemplateRow.project_id == current.project_id,
            PrototypeTemplateRow.template_state == "ACTIVE",
            PrototypeTemplateRow.current_template_version_ref
            == current.current_template_version_ref,
            PrototypeTemplateRow.lock_version == current.lock_version,
        ).values(
            current_template_version_ref=version_id,
            updated_by=actor_id, updated_at=func.statement_timestamp(),
            lock_version=next_lock,
        ))
        if changed.rowcount != 1:
            raise RuntimeError("PrototypeTemplate revision lost current version")
        session.execute(insert(PrototypeTemplateCommandResultRow).values(
            result_id=result_id,
            prototype_template_id=current.prototype_template_id,
            prototype_template_version_id=version_id,
            scope=current.scope, project_id=current.project_id,
            operation="REVISE", name=current.name, version_no=version_no,
            content_fingerprint=content_fingerprint,
            declared_artifact_count=len(artifact_refs), lock_version=next_lock,
        ))
        view = self.result(transaction, result_id=result_id)
        if view is None:
            raise RuntimeError("PrototypeTemplate revision result was not persisted")
        return view

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
    ) -> PrototypeTemplateRevisionView | None:
        if type(result_id) is not uuid.UUID or result_id.int == 0:
            return None
        session = _session(transaction)
        row = session.execute(select(
            PrototypeTemplateCommandResultRow,
            PrototypeTemplateVersionRow.supersedes_version_id,
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
            PrototypeTemplateCommandResultRow.operation == "REVISE",
            PrototypeTemplateCommandResultRow.version_no > 1,
            PrototypeTemplateCommandResultRow.lock_version
            == PrototypeTemplateCommandResultRow.version_no - 1,
            PrototypeTemplateVersionRow.prototype_template_id
            == PrototypeTemplateCommandResultRow.prototype_template_id,
        ).execution_options(populate_existing=True)).one_or_none()
        if row is None or row.supersedes_version_id is None:
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
            ).order_by(PrototypeTemplateArtifactRefRow.ordinal)).scalars()
        )
        if len(artifacts) != result.declared_artifact_count:
            return None
        return PrototypeTemplateRevisionView(
            result.prototype_template_id,
            result.prototype_template_version_id,
            row.supersedes_version_id,
            result.scope, result.project_id, result.name, result.version_no,
            dict(row.layout_contract), dict(row.component_contract),
            tuple(row.applicable_terminals), artifacts,
            bytes(result.content_fingerprint).hex(), result.lock_version,
            result.created_at, version_state=row.version_state,
        )
