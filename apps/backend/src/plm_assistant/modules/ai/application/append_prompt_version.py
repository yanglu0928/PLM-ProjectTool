"""Internal append-only PromptVersion command; no production content admission wired."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft, PromptVersionError
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class PromptVersionAppendError(RuntimeError):
    def __init__(self, code: str = "AI_PROMPT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AppendPromptVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    prompt_template_id: uuid.UUID
    task_type: PromptTaskType
    system_template: str = field(repr=False)
    user_template: str = field(repr=False)
    output_schema_ref: str
    schema_version: int
    rag_policy_ref: str
    provider_policy_ref: str
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PromptTemplateLock:
    prompt_template_id: uuid.UUID
    task_type: PromptTaskType
    state: str
    lock_version: int
    highest_version_no: int


@dataclass(frozen=True, slots=True)
class AppendedPromptVersion:
    result_id: uuid.UUID
    prompt_template_id: uuid.UUID
    version_no: int
    actor_id: uuid.UUID
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    system_hash: str
    user_hash: str
    output_schema_ref: str
    schema_version: int
    rag_policy_ref: str
    provider_policy_ref: str
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.result_id, self.prompt_template_id, self.actor_id,
                self.audit_event_id, self.trace_id,
            ))
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.content_fingerprint) is not bytes or len(self.content_fingerprint) != 32
                or type(self.expected_lock_version) is not int or self.expected_lock_version < 0
                or self.lock_version != self.expected_lock_version + 1):
            raise PromptVersionAppendError()


class PromptVersionAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class PromptVersionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PromptContentAdmissionPort(Protocol):
    def approved_fingerprint(self, transaction: object, *, actor_id: uuid.UUID,
                             draft: PromptVersionDraft) -> bytes | None: ...


class PromptVersionRepositoryPort(Protocol):
    def lock_template(self, transaction: object, *, prompt_template_id: uuid.UUID) -> PromptTemplateLock | None: ...

    def append(self, transaction: object, *, draft: PromptVersionDraft,
               version_no: int, expected_lock_version: int, actor_id: uuid.UUID) -> None: ...

    def save_result(self, transaction: object, *, result: AppendedPromptVersion) -> None: ...

    def get_result(self, transaction: object, *, result_id: uuid.UUID,
                   template_id: uuid.UUID, actor_id: uuid.UUID,
                   expected_lock_version: int) -> AppendedPromptVersion | None: ...


class PromptVersionReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class PromptVersionAppendService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: PromptVersionAccessPort,
                 license_guard: PromptVersionLicensePort, admission: PromptContentAdmissionPort,
                 repository: PromptVersionRepositoryPort, receipts: PromptVersionReceiptPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, admission,
                                         repository, receipts, audit)):
            raise ValueError("PromptVersion dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._admission, self._repo, self._receipts, self._audit = admission, repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def append(self, command: AppendPromptVersion) -> AppendedPromptVersion:
        if (type(command) is not AppendPromptVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806):
            raise PromptVersionAppendError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            draft = PromptVersionDraft(
                command.prompt_template_id, command.task_type,
                command.system_template, command.user_template,
                command.output_schema_ref, command.schema_version,
                command.rag_policy_ref, command.provider_policy_ref,
            )
            fingerprint = canonical_payload_fingerprint({
                "draft": draft.fingerprint.hex(),
                "expected_lock_version": command.expected_lock_version,
            })
        except (IdempotencyError, PromptVersionError):
            raise PromptVersionAppendError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation="V1_AI_PROMPT_CREATE_VERSION", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != "V1_AI_PROMPT_CREATE_VERSION" or replay.status_code != 201:
                        raise PromptVersionAppendError()
                    original = self._repo.get_result(
                        tx, result_id=replay.ref_id, template_id=draft.prompt_template_id,
                        actor_id=actor, expected_lock_version=command.expected_lock_version,
                    )
                    if (type(original) is not AppendedPromptVersion
                            or not hmac.compare_digest(original.content_fingerprint, draft.fingerprint)):
                        raise PromptVersionAppendError()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                locked = self._repo.lock_template(tx, prompt_template_id=draft.prompt_template_id)
                if type(locked) is not PromptTemplateLock:
                    raise PromptVersionAppendError("AI_PROMPT_NOT_FOUND")
                if locked.task_type is not draft.task_type or locked.state == "RETIRED":
                    raise PromptVersionAppendError("AI_PROMPT_STATE_CONFLICT")
                if locked.lock_version != command.expected_lock_version:
                    raise PromptVersionAppendError("CONFLICT_VERSION")
                approved = self._admission.approved_fingerprint(tx, actor_id=actor, draft=draft)
                if (type(approved) is not bytes or len(approved) != 32
                        or not hmac.compare_digest(approved, draft.fingerprint)):
                    raise PromptVersionAppendError("AI_PROMPT_CONTENT_UNAPPROVED")
                version_no = locked.highest_version_no + 1
                self._repo.append(
                    tx, draft=draft, version_no=version_no,
                    expected_lock_version=command.expected_lock_version, actor_id=actor,
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROMPT_VERSION_CREATE", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-03",
                    target_object_id=draft.prompt_template_id,
                    before_state=locked.state, after_state=locked.state,
                ))
                result = AppendedPromptVersion(
                    uuid.UUID(new_uuid7()), draft.prompt_template_id, version_no,
                    actor, audit_id, command.trace_id, draft.fingerprint,
                    draft.system_hash, draft.user_hash, draft.output_schema_ref,
                    draft.schema_version, draft.rag_policy_ref, draft.provider_policy_ref,
                    command.expected_lock_version, command.expected_lock_version + 1,
                )
                self._repo.save_result(tx, result=result)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROMPT_CREATE_VERSION", result.result_id, 201,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except PromptVersionAppendError:
            raise
        except RuntimeLicenseError:
            raise PromptVersionAppendError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise PromptVersionAppendError(exc.code) from None
        except Exception:
            raise PromptVersionAppendError() from None

    def _require_admin(self, tx: object, command: AppendPromptVersion) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PromptVersionAppendError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PromptVersionAppendError("AUTH_ACCESS_DENIED")
        return actor
