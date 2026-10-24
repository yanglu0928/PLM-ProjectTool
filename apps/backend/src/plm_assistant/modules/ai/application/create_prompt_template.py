"""Internal, idempotent PromptTemplate identity creation; never stores prompt body."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.domain.prompt_identity import (
    PromptIdentityError, PromptTaskType, PromptTemplateIdentity,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class PromptTemplateCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreatePromptTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    task_type: PromptTaskType
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PromptTemplateInitialView:
    prompt_template_id: uuid.UUID
    task_type: PromptTaskType
    state: str = "DRAFT"
    active_version_no: None = None
    lock_version: int = 0

    def __post_init__(self) -> None:
        if (type(self.prompt_template_id) is not uuid.UUID or self.prompt_template_id.int == 0
                or type(self.task_type) is not PromptTaskType
                or self.state != "DRAFT" or self.active_version_no is not None
                or self.lock_version != 0):
            raise ValueError("invalid initial PromptTemplate view")


class PromptCreateAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class PromptCreateLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class PromptCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, identity: PromptTemplateIdentity,
               actor_id: uuid.UUID) -> None: ...

    def initial_view(self, transaction: object, *, prompt_template_id: uuid.UUID,
                     actor_id: uuid.UUID) -> PromptTemplateInitialView | None: ...


class PromptCreateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class PromptTemplateCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: PromptCreateAccessPort,
                 license_guard: PromptCreateLicensePort, repository: PromptCreateRepositoryPort,
                 receipts: PromptCreateReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard,
                                         repository, receipts, audit)):
            raise ValueError("PromptTemplate dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreatePromptTemplate) -> uuid.UUID:
        return self.create_view(command).prompt_template_id

    def create_view(self, command: CreatePromptTemplate) -> PromptTemplateInitialView:
        if (type(command) is not CreatePromptTemplate
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise PromptTemplateCreateError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            identity = PromptTemplateIdentity(uuid.UUID(new_uuid7()), command.task_type)
            fingerprint = canonical_payload_fingerprint({"task_type": identity.task_type.value})
        except (IdempotencyError, PromptIdentityError):
            raise PromptTemplateCreateError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_PROMPT_CREATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != "V1_AI_PROMPT_CREATE" or replay.status_code != 201:
                        raise PromptTemplateCreateError("AI_PROMPT_UNAVAILABLE")
                    view = self._repo.initial_view(
                        tx, prompt_template_id=replay.ref_id, actor_id=actor_id,
                    )
                    if type(view) is not PromptTemplateInitialView or view.task_type is not identity.task_type:
                        raise PromptTemplateCreateError("AI_PROMPT_UNAVAILABLE")
                    return view
                self._repo.create(tx, identity=identity, actor_id=actor_id)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROMPT_CREATE", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-03",
                    target_object_id=identity.prompt_template_id, after_state="DRAFT",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_PROMPT_CREATE", identity.prompt_template_id, 201,
                ))
                view = self._repo.initial_view(
                    tx, prompt_template_id=identity.prompt_template_id, actor_id=actor_id,
                )
                if type(view) is not PromptTemplateInitialView:
                    raise PromptTemplateCreateError("AI_PROMPT_UNAVAILABLE")
                tx.commit()
                return view
        except PromptTemplateCreateError:
            raise
        except RuntimeLicenseError:
            raise PromptTemplateCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise PromptTemplateCreateError(exc.code) from None
        except Exception:
            raise PromptTemplateCreateError("AI_PROMPT_UNAVAILABLE") from None

    def _require_admin(self, tx: object, command: CreatePromptTemplate) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PromptTemplateCreateError("AI_PROMPT_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise PromptTemplateCreateError("AUTH_ACCESS_DENIED")
        return actor_id
