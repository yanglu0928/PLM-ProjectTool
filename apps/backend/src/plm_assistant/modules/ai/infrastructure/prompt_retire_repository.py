"""AI-owned atomic Prompt retirement and immutable first-result lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.retire_prompt_template import (
    PromptRetireError, PromptRetireTarget, RetiredPromptTemplate,
)
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptRetireResultRow, PromptTemplateRow, PromptVersionRow,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prompt retirement transaction required")
    return session


class SqlAlchemyPromptRetireRepository:
    def locked_target(self, transaction: object, *, template_id: uuid.UUID) -> PromptRetireTarget | None:
        if type(template_id) is not uuid.UUID or template_id.int == 0:
            raise PromptRetireError("VALIDATION_FAILED")
        root = _session(transaction).execute(select(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == template_id,
        ).with_for_update().execution_options(autoflush=False)).scalar_one_or_none()
        if root is None:
            return None
        return PromptRetireTarget(root.prompt_template_id, root.template_state,
                                  root.active_version_no, root.lock_version)

    def retire(self, transaction: object, *, template_id: uuid.UUID,
               expected_lock_version: int) -> int:
        if (type(template_id) is not uuid.UUID or template_id.int == 0
                or type(expected_lock_version) is not int
                or not 0 <= expected_lock_version <= 9223372036854775806):
            raise PromptRetireError("VALIDATION_FAILED")
        changed = _session(transaction).execute(update(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == template_id,
            PromptTemplateRow.template_state.in_(("DRAFT", "ACTIVE")),
            PromptTemplateRow.lock_version == expected_lock_version,
        ).values(template_state="RETIRED",
                 lock_version=PromptTemplateRow.lock_version + 1)
          .returning(PromptTemplateRow.lock_version)).scalar_one_or_none()
        if changed is None:
            raise PromptRetireError("CONFLICT_VERSION")
        return changed

    def save_result(self, transaction: object, *, result: RetiredPromptTemplate) -> None:
        if type(result) is not RetiredPromptTemplate:
            raise PromptRetireError("VALIDATION_FAILED")
        result.__post_init__()
        _session(transaction).execute(insert(PromptRetireResultRow).values(
            result_id=result.result_id, prompt_template_id=result.prompt_template_id,
            actor_id=result.actor_id, audit_event_id=result.audit_event_id,
            trace_id=result.trace_id, prior_state=result.prior_state,
            prior_active_version_no=result.prior_active_version_no,
            state=result.state, expected_lock_version=result.expected_lock_version,
            lock_version=result.lock_version,
        ))

    def get_result(self, transaction: object, *, result_id: uuid.UUID,
                   template_id: uuid.UUID, actor_id: uuid.UUID,
                   expected_lock_version: int) -> RetiredPromptTemplate | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                result_id, template_id, actor_id))
                or type(expected_lock_version) is not int or expected_lock_version < 0):
            raise PromptRetireError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.execute(select(PromptRetireResultRow).where(
            PromptRetireResultRow.result_id == result_id,
            PromptRetireResultRow.prompt_template_id == template_id,
            PromptRetireResultRow.actor_id == actor_id,
            PromptRetireResultRow.expected_lock_version == expected_lock_version,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        audit = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == row.audit_event_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if (audit is None
                or audit.trace_id != row.trace_id or audit.actor_id != actor_id
                or audit.event_scope != "DEPLOYMENT" or audit.actor_type != "USER"
                or audit.action != "AI_PROMPT_RETIRE" or audit.outcome != "SUCCESS"
                or audit.target_owner_module != "ai" or audit.target_object_type != "AI-03"
                or audit.target_object_id != template_id
                or audit.before_state != row.prior_state or audit.after_state != "RETIRED"):
            raise PromptRetireError()
        if row.prior_active_version_no is not None:
            version = session.execute(select(PromptVersionRow).where(
                PromptVersionRow.prompt_template_id == template_id,
                PromptVersionRow.version_no == row.prior_active_version_no,
            ).execution_options(autoflush=False)).scalar_one_or_none()
            if version is None:
                raise PromptRetireError()
        return RetiredPromptTemplate(
            row.result_id, row.prompt_template_id, row.actor_id,
            row.audit_event_id, row.trace_id, row.prior_state,
            row.prior_active_version_no, row.state,
            row.expected_lock_version, row.lock_version,
        )
