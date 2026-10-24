"""AI-owned PromptTemplate DRAFT identity write; no version content."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.create_prompt_template import PromptTemplateInitialView
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType, PromptTemplateIdentity
from plm_assistant.modules.ai.infrastructure.prompt_orm import PromptTemplateRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prompt transaction is required")
    return session


class SqlAlchemyPromptCreateRepository:
    def create(self, transaction: object, *, identity: PromptTemplateIdentity,
               actor_id: uuid.UUID) -> None:
        if (type(identity) is not PromptTemplateIdentity
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise ValueError("invalid PromptTemplate identity write")
        _session(transaction).execute(insert(PromptTemplateRow).values(
            prompt_template_id=identity.prompt_template_id, task_type=identity.task_type.value,
            scope="DEPLOYMENT", template_state="DRAFT", active_version_no=None,
            lock_version=0, created_by=actor_id,
        ))

    def initial_view(self, transaction: object, *, prompt_template_id: uuid.UUID,
                     actor_id: uuid.UUID) -> PromptTemplateInitialView | None:
        if (type(prompt_template_id) is not uuid.UUID or prompt_template_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            return None
        row = _session(transaction).execute(
            select(PromptTemplateRow.task_type).where(
                PromptTemplateRow.prompt_template_id == prompt_template_id,
                PromptTemplateRow.created_by == actor_id,
            ).execution_options(autoflush=False)
        ).one_or_none()
        if row is None:
            return None
        return PromptTemplateInitialView(prompt_template_id, PromptTaskType(row.task_type))
