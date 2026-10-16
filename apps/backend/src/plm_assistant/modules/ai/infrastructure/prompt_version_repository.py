"""AI-owned PromptVersion append and immutable first-result lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendedPromptVersion, PromptTemplateLock, PromptVersionAppendError,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptTemplateRow, PromptVersionCreateResultRow, PromptVersionRow,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active PromptVersion transaction required")
    return session


class SqlAlchemyPromptVersionRepository:
    def lock_template(self, transaction: object, *, prompt_template_id: uuid.UUID) -> PromptTemplateLock | None:
        if type(prompt_template_id) is not uuid.UUID or prompt_template_id.int == 0:
            return None
        session = _session(transaction)
        row = session.execute(select(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == prompt_template_id,
        ).with_for_update().execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        highest = session.execute(select(func.coalesce(func.max(PromptVersionRow.version_no), 0)).where(
            PromptVersionRow.prompt_template_id == prompt_template_id,
        ).execution_options(autoflush=False)).scalar_one()
        return PromptTemplateLock(
            row.prompt_template_id, PromptTaskType(row.task_type), row.template_state,
            row.lock_version, highest,
        )

    def append(self, transaction: object, *, draft: PromptVersionDraft, version_no: int,
               expected_lock_version: int, actor_id: uuid.UUID) -> None:
        if (type(draft) is not PromptVersionDraft
                or type(version_no) is not int or version_no < 1
                or type(expected_lock_version) is not int or expected_lock_version < 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            raise PromptVersionAppendError("VALIDATION_FAILED")
        session = _session(transaction)
        changed = session.execute(update(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == draft.prompt_template_id,
            PromptTemplateRow.task_type == draft.task_type.value,
            PromptTemplateRow.template_state.in_(("DRAFT", "ACTIVE")),
            PromptTemplateRow.lock_version == expected_lock_version,
        ).values(lock_version=PromptTemplateRow.lock_version + 1)
          .returning(PromptTemplateRow.lock_version)).scalar_one_or_none()
        if changed != expected_lock_version + 1:
            raise PromptVersionAppendError("CONFLICT_VERSION")
        session.execute(insert(PromptVersionRow).values(
            prompt_template_id=draft.prompt_template_id, version_no=version_no,
            system_template=draft.system_template, user_template=draft.user_template,
            system_template_hash=draft.system_hash, user_template_hash=draft.user_hash,
            output_schema_ref=draft.output_schema_ref, schema_version=draft.schema_version,
            rag_policy_ref=draft.rag_policy_ref, provider_policy_ref=draft.provider_policy_ref,
            created_by=actor_id,
        ))

    def save_result(self, transaction: object, *, result: AppendedPromptVersion) -> None:
        if type(result) is not AppendedPromptVersion:
            raise PromptVersionAppendError("VALIDATION_FAILED")
        result.__post_init__()
        _session(transaction).execute(insert(PromptVersionCreateResultRow).values(
            result_id=result.result_id, prompt_template_id=result.prompt_template_id,
            version_no=result.version_no, actor_id=result.actor_id,
            audit_event_id=result.audit_event_id, trace_id=result.trace_id,
            content_fingerprint=result.content_fingerprint,
            expected_lock_version=result.expected_lock_version,
            lock_version=result.lock_version,
        ))

    def get_result(self, transaction: object, *, result_id: uuid.UUID, template_id: uuid.UUID,
                   actor_id: uuid.UUID, expected_lock_version: int) -> AppendedPromptVersion | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                result_id, template_id, actor_id,
            )) or type(expected_lock_version) is not int or expected_lock_version < 0):
            raise PromptVersionAppendError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.execute(select(PromptVersionCreateResultRow).where(
            PromptVersionCreateResultRow.result_id == result_id,
            PromptVersionCreateResultRow.prompt_template_id == template_id,
            PromptVersionCreateResultRow.actor_id == actor_id,
            PromptVersionCreateResultRow.expected_lock_version == expected_lock_version,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        version = session.execute(select(PromptVersionRow).where(
            PromptVersionRow.prompt_template_id == row.prompt_template_id,
            PromptVersionRow.version_no == row.version_no,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        audit = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == row.audit_event_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if (version is None or audit is None
                or audit.trace_id != row.trace_id or audit.actor_id != actor_id
                or audit.event_scope != "DEPLOYMENT" or audit.actor_type != "USER"
                or audit.action != "AI_PROMPT_VERSION_CREATE" or audit.outcome != "SUCCESS"
                or audit.target_owner_module != "ai" or audit.target_object_type != "AI-03"
                or audit.target_object_id != template_id or audit.before_state != audit.after_state
                or audit.before_state not in ("DRAFT", "ACTIVE")):
            raise PromptVersionAppendError()
        return AppendedPromptVersion(
            row.result_id, row.prompt_template_id, row.version_no, row.actor_id,
            row.audit_event_id, row.trace_id, bytes(row.content_fingerprint),
            version.system_template_hash, version.user_template_hash,
            version.output_schema_ref, version.schema_version,
            version.rag_policy_ref, version.provider_policy_ref,
            row.expected_lock_version, row.lock_version,
        )
