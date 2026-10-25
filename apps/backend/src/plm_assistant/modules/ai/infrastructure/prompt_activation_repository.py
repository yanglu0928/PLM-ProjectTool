"""AI-owned atomic PromptVersion activation and historical result lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.activate_prompt_version import (
    ActivatedPromptVersion, PromptActivationError, PromptActivationTarget,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft, PromptVersionError
from plm_assistant.modules.ai.infrastructure.prompt_orm import (
    PromptActivationResultRow, PromptTemplateRow, PromptVersionRow,
)
from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Prompt activation transaction required")
    return session


class SqlAlchemyPromptActivationRepository:
    def locked_target(self, transaction: object, *, template_id: uuid.UUID,
                      version_no: int) -> PromptActivationTarget | None:
        if (type(template_id) is not uuid.UUID or template_id.int == 0
                or type(version_no) is not int or version_no < 1):
            raise PromptActivationError("VALIDATION_FAILED")
        session = _session(transaction)
        root = session.execute(select(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == template_id,
        ).with_for_update().execution_options(autoflush=False)).scalar_one_or_none()
        if root is None:
            return None
        version = session.execute(select(PromptVersionRow).where(
            PromptVersionRow.prompt_template_id == template_id,
            PromptVersionRow.version_no == version_no,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        draft = None
        if version is not None:
            try:
                draft = PromptVersionDraft(
                    template_id, PromptTaskType(root.task_type),
                    version.system_template, version.user_template,
                    version.output_schema_ref, version.schema_version,
                    version.rag_policy_ref, version.provider_policy_ref,
                )
            except (PromptVersionError, ValueError):
                raise PromptActivationError("AI_PROMPT_CONTENT_UNAPPROVED") from None
            if (draft.system_hash != version.system_template_hash
                    or draft.user_hash != version.user_template_hash
                    or draft.system_template != version.system_template
                    or draft.user_template != version.user_template):
                raise PromptActivationError("AI_PROMPT_CONTENT_UNAPPROVED")
        return PromptActivationTarget(
            root.prompt_template_id, root.template_state, root.active_version_no,
            root.lock_version, draft,
        )

    def activate(self, transaction: object, *, template_id: uuid.UUID,
                 version_no: int, expected_lock_version: int) -> int:
        if (type(template_id) is not uuid.UUID or template_id.int == 0
                or type(version_no) is not int or version_no < 1
                or type(expected_lock_version) is not int
                or not 0 <= expected_lock_version <= 9223372036854775806):
            raise PromptActivationError("VALIDATION_FAILED")
        changed = _session(transaction).execute(update(PromptTemplateRow).where(
            PromptTemplateRow.prompt_template_id == template_id,
            PromptTemplateRow.template_state.in_(("DRAFT", "ACTIVE")),
            PromptTemplateRow.lock_version == expected_lock_version,
            (PromptTemplateRow.template_state == "DRAFT")
            | (PromptTemplateRow.active_version_no != version_no),
        ).values(template_state="ACTIVE", active_version_no=version_no,
                 lock_version=PromptTemplateRow.lock_version + 1)
          .returning(PromptTemplateRow.lock_version)).scalar_one_or_none()
        if changed is None:
            raise PromptActivationError("CONFLICT_VERSION")
        return changed

    def save_result(self, transaction: object, *, result: ActivatedPromptVersion) -> None:
        if type(result) is not ActivatedPromptVersion:
            raise PromptActivationError("VALIDATION_FAILED")
        result.__post_init__()
        _session(transaction).execute(insert(PromptActivationResultRow).values(
            result_id=result.result_id, prompt_template_id=result.prompt_template_id,
            version_no=result.version_no, actor_id=result.actor_id,
            audit_event_id=result.audit_event_id, trace_id=result.trace_id,
            state=result.state, expected_lock_version=result.expected_lock_version,
            lock_version=result.lock_version,
        ))

    def get_result(self, transaction: object, *, result_id: uuid.UUID,
                   template_id: uuid.UUID, version_no: int, actor_id: uuid.UUID,
                   expected_lock_version: int) -> ActivatedPromptVersion | None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                result_id, template_id, actor_id))
                or type(version_no) is not int or version_no < 1
                or type(expected_lock_version) is not int or expected_lock_version < 0):
            raise PromptActivationError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.execute(select(PromptActivationResultRow).where(
            PromptActivationResultRow.result_id == result_id,
            PromptActivationResultRow.prompt_template_id == template_id,
            PromptActivationResultRow.version_no == version_no,
            PromptActivationResultRow.actor_id == actor_id,
            PromptActivationResultRow.expected_lock_version == expected_lock_version,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if row is None:
            return None
        version = session.execute(select(PromptVersionRow).where(
            PromptVersionRow.prompt_template_id == template_id,
            PromptVersionRow.version_no == version_no,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        audit = session.execute(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == row.audit_event_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        if (version is None or audit is None
                or audit.trace_id != row.trace_id or audit.actor_id != actor_id
                or audit.event_scope != "DEPLOYMENT" or audit.actor_type != "USER"
                or audit.action != "AI_PROMPT_VERSION_ACTIVATE" or audit.outcome != "SUCCESS"
                or audit.target_owner_module != "ai" or audit.target_object_type != "AI-03"
                or audit.target_object_id != template_id
                or audit.before_state not in ("DRAFT", "ACTIVE")
                or audit.after_state != "ACTIVE"):
            raise PromptActivationError()
        return ActivatedPromptVersion(
            row.result_id, row.prompt_template_id, row.version_no, row.actor_id,
            row.audit_event_id, row.trace_id, row.state,
            row.expected_lock_version, row.lock_version,
        )
