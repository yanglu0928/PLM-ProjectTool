"""PostgreSQL PrototypeTemplate current-list and immutable-version reads."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.prototype.application.create_template import (
    TemplateArtifactRef,
)
from plm_assistant.modules.prototype.application.read_templates import (
    PrototypeTemplateVersionView,
)

from .orm import (
    PrototypeTemplateArtifactRefRow, PrototypeTemplateRow,
    PrototypeTemplateVersionRow,
)
from .template_create_repository import _session


class SqlAlchemyPrototypeTemplateReadRepository:
    def list_current(
        self, transaction: object, *, project_id: uuid.UUID | None,
        global_only: bool, after_updated_at: datetime | None,
        after_template_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypeTemplateVersionView, ...]:
        session = _session(transaction)
        scope_filter = (
            and_(PrototypeTemplateRow.scope == "GLOBAL",
                 PrototypeTemplateRow.project_id.is_(None))
            if global_only else or_(
                and_(PrototypeTemplateRow.scope == "GLOBAL",
                     PrototypeTemplateRow.project_id.is_(None)),
                and_(PrototypeTemplateRow.scope == "PROJECT",
                     PrototypeTemplateRow.project_id == project_id),
            )
        )
        statement = select(
            PrototypeTemplateRow, PrototypeTemplateVersionRow,
        ).join(
            PrototypeTemplateVersionRow,
            and_(
                PrototypeTemplateVersionRow.prototype_template_version_id
                == PrototypeTemplateRow.current_template_version_ref,
                PrototypeTemplateVersionRow.prototype_template_id
                == PrototypeTemplateRow.prototype_template_id,
            ),
        ).where(
            scope_filter, PrototypeTemplateRow.template_state == "ACTIVE",
        )
        if after_updated_at is not None and after_template_id is not None:
            statement = statement.where(or_(
                PrototypeTemplateRow.updated_at < after_updated_at,
                and_(
                    PrototypeTemplateRow.updated_at == after_updated_at,
                    PrototypeTemplateRow.prototype_template_id < after_template_id,
                ),
            ))
        rows = session.execute(statement.order_by(
            PrototypeTemplateRow.updated_at.desc(),
            PrototypeTemplateRow.prototype_template_id.desc(),
        ).limit(limit).execution_options(populate_existing=True)).all()
        return tuple(self._view(session, root, version) for root, version in rows)

    def get_version(
        self, transaction: object, *, project_id: uuid.UUID | None,
        global_only: bool, template_id: uuid.UUID, version_id: uuid.UUID,
    ) -> PrototypeTemplateVersionView | None:
        session = _session(transaction)
        scope_filter = (
            and_(PrototypeTemplateRow.scope == "GLOBAL",
                 PrototypeTemplateRow.project_id.is_(None))
            if global_only else or_(
                and_(PrototypeTemplateRow.scope == "GLOBAL",
                     PrototypeTemplateRow.project_id.is_(None)),
                and_(PrototypeTemplateRow.scope == "PROJECT",
                     PrototypeTemplateRow.project_id == project_id),
            )
        )
        row = session.execute(select(
            PrototypeTemplateRow, PrototypeTemplateVersionRow,
        ).join(
            PrototypeTemplateVersionRow,
            PrototypeTemplateVersionRow.prototype_template_id
            == PrototypeTemplateRow.prototype_template_id,
        ).where(
            PrototypeTemplateRow.prototype_template_id == template_id,
            PrototypeTemplateVersionRow.prototype_template_version_id == version_id,
            scope_filter,
        ).execution_options(populate_existing=True)).one_or_none()
        return None if row is None else self._view(session, row[0], row[1])

    @staticmethod
    def _view(session, root, version) -> PrototypeTemplateVersionView:
        artifacts = tuple(
            TemplateArtifactRef(row.artifact_kind, row.target_id)
            for row in session.execute(select(
                PrototypeTemplateArtifactRefRow,
            ).where(
                PrototypeTemplateArtifactRefRow.prototype_template_version_id
                == version.prototype_template_version_id,
                PrototypeTemplateArtifactRefRow.prototype_template_id
                == root.prototype_template_id,
            ).order_by(PrototypeTemplateArtifactRefRow.ordinal)).scalars()
        )
        if len(artifacts) != version.declared_artifact_count:
            raise RuntimeError("PrototypeTemplate ArtifactRef set is incomplete")
        return PrototypeTemplateVersionView(
            root.prototype_template_id, version.prototype_template_version_id,
            root.scope, root.project_id, root.name, root.template_state,
            version.version_no, version.version_state,
            version.supersedes_version_id, dict(version.layout_contract),
            dict(version.component_contract), tuple(version.applicable_terminals),
            artifacts, bytes(version.content_fingerprint).hex(), root.lock_version,
            root.current_template_version_ref
            == version.prototype_template_version_id,
            root.updated_at, version.created_at,
        )
