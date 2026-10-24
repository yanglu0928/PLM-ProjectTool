"""Bounded Prompt metadata projection; SQL never selects template bodies."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import and_, select, tuple_

from plm_assistant.modules.ai.application.prompt_metadata import PromptMetadataView
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.infrastructure.prompt_create_repository import _session
from plm_assistant.modules.ai.infrastructure.prompt_orm import PromptTemplateRow, PromptVersionRow


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _statement():
    return select(
        PromptTemplateRow,
        PromptVersionRow.output_schema_ref,
        PromptVersionRow.schema_version,
        PromptVersionRow.rag_policy_ref,
        PromptVersionRow.provider_policy_ref,
        PromptVersionRow.system_template_hash,
        PromptVersionRow.user_template_hash,
    ).outerjoin(
        PromptVersionRow,
        and_(PromptTemplateRow.template_state == "ACTIVE",
             PromptTemplateRow.prompt_template_id == PromptVersionRow.prompt_template_id,
             PromptTemplateRow.active_version_no == PromptVersionRow.version_no),
    )


def _view(row: object) -> PromptMetadataView:
    root, output_ref, schema_version, rag_ref, provider_ref, system_hash, user_hash = row
    if (root.scope != "DEPLOYMENT" or root.template_state not in {"DRAFT", "ACTIVE", "RETIRED"}
            or type(root.lock_version) is not int or root.lock_version < 0
            or not isinstance(root.created_at, datetime) or root.created_at.tzinfo is None
            or root.created_at.utcoffset() is None):
        raise RuntimeError("invalid Prompt metadata")
    active = root.template_state == "ACTIVE"
    fields = (output_ref, schema_version, rag_ref, provider_ref, system_hash, user_hash)
    if active:
        if (type(root.active_version_no) is not int or root.active_version_no < 1
                or type(schema_version) is not int or schema_version < 1
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       for value in (output_ref, rag_ref, provider_ref))
                or any(type(value) is not str or _HASH.fullmatch(value) is None
                       for value in (system_hash, user_hash))):
            raise RuntimeError("incomplete active Prompt metadata")
    elif any(value is not None for value in fields):
        raise RuntimeError("inactive Prompt exposed version metadata")
    if root.template_state == "DRAFT" and root.active_version_no is not None:
        raise RuntimeError("draft Prompt has active pointer")
    return PromptMetadataView(
        template_id=root.prompt_template_id, task_type=PromptTaskType(root.task_type),
        state=root.template_state, active_version_no=root.active_version_no if active else None,
        output_schema_ref=output_ref, schema_version=schema_version,
        rag_policy_ref=rag_ref, provider_policy_ref=provider_ref,
        system_template_hash=system_hash, user_template_hash=user_hash,
        lock_version=root.lock_version, created_at=root.created_at,
    )


class SqlAlchemyPromptMetadataRepository:
    def get(self, transaction: object, *, template_id: uuid.UUID) -> PromptMetadataView | None:
        if type(template_id) is not uuid.UUID or template_id.int == 0:
            return None
        row = _session(transaction).execute(
            _statement().where(PromptTemplateRow.prompt_template_id == template_id)
            .execution_options(autoflush=False)
        ).one_or_none()
        return _view(row) if row is not None else None

    def list_page(self, transaction: object, *, after: tuple[datetime, uuid.UUID] | None,
                  limit: int) -> list[PromptMetadataView]:
        if (type(limit) is not int or not 1 <= limit <= 201
                or after is not None and (
                    type(after) is not tuple or len(after) != 2
                    or not isinstance(after[0], datetime) or after[0].tzinfo is None
                    or after[0].utcoffset() is None
                    or type(after[1]) is not uuid.UUID or after[1].int == 0)):
            raise ValueError("invalid Prompt list page")
        statement = _statement()
        if after is not None:
            statement = statement.where(
                tuple_(PromptTemplateRow.created_at, PromptTemplateRow.prompt_template_id) < after,
            )
        rows = _session(transaction).execute(statement.order_by(
            PromptTemplateRow.created_at.desc(), PromptTemplateRow.prompt_template_id.desc(),
        ).limit(limit).execution_options(autoflush=False)).all()
        return [_view(row) for row in rows]
