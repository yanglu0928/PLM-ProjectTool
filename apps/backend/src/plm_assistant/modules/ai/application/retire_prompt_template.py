"""Authorized atomic retirement of a PromptTemplate identity."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


_OPERATION = "V1_AI_PROMPT_RETIRE"


class PromptRetireError(RuntimeError):
    def __init__(self, code: str = "AI_PROMPT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RetirePromptTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    prompt_template_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PromptRetireTarget:
    prompt_template_id: uuid.UUID
    state: str
    active_version_no: int | None
    lock_version: int


@dataclass(frozen=True, slots=True)
class RetiredPromptTemplate:
    result_id: uuid.UUID
    prompt_template_id: uuid.UUID
    actor_id: uuid.UUID
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    prior_state: str
    prior_active_version_no: int | None
    state: str
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.result_id, self.prompt_template_id, self.actor_id,
                self.audit_event_id, self.trace_id))
                or self.state != "RETIRED"
                or not ((self.prior_state == "DRAFT" and self.prior_active_version_no is None)
                        or (self.prior_state == "ACTIVE"
                            and type(self.prior_active_version_no) is int
                            and self.prior_active_version_no > 0))
                or type(self.expected_lock_version) is not int
                or not 0 <= self.expected_lock_version <= 9223372036854775806
                or type(self.lock_version) is not int
                or self.lock_version != self.expected_lock_version + 1):
            raise PromptRetireError()

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'


class _Access(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _Repository(Protocol):
    def locked_target(self, transaction: object, *, template_id: uuid.UUID) -> PromptRetireTarget | None: ...
    def retire(self, transaction: object, *, template_id: uuid.UUID,
               expected_lock_version: int) -> int: ...
    def save_result(self, transaction: object, *, result: RetiredPromptTemplate) -> None: ...
    def get_result(self, transaction: object, *, result_id: uuid.UUID,
                   template_id: uuid.UUID, actor_id: uuid.UUID,
                   expected_lock_version: int) -> RetiredPromptTemplate | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class PromptTemplateRetireService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object, repository: _Repository, receipts: _Receipts,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                           repository, receipts, audit)):
            raise ValueError("Prompt retirement dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def retire(self, command: RetirePromptTemplate) -> RetiredPromptTemplate:
        if (type(command) is not RetirePromptTemplate
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.prompt_template_id) is not uuid.UUID or command.prompt_template_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806):
            raise PromptRetireError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "prompt_template_id": str(command.prompt_template_id),
                "expected_lock_version": command.expected_lock_version,
            })
        except IdempotencyError:
            raise PromptRetireError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation=_OPERATION,
                    key=command.idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise PromptRetireError()
                    original = self._repo.get_result(
                        tx, result_id=replay.ref_id, template_id=command.prompt_template_id,
                        actor_id=actor, expected_lock_version=command.expected_lock_version,
                    )
                    if type(original) is not RetiredPromptTemplate:
                        raise PromptRetireError()
                    original.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                target = self._repo.locked_target(tx, template_id=command.prompt_template_id)
                if type(target) is not PromptRetireTarget:
                    raise PromptRetireError("AI_PROMPT_NOT_FOUND")
                if target.lock_version != command.expected_lock_version:
                    raise PromptRetireError("CONFLICT_VERSION")
                if target.state == "RETIRED":
                    raise PromptRetireError("AI_PROMPT_STATE_CONFLICT")
                if not ((target.state == "DRAFT" and target.active_version_no is None)
                        or (target.state == "ACTIVE" and type(target.active_version_no) is int
                            and target.active_version_no > 0)):
                    raise PromptRetireError()
                changed = self._repo.retire(
                    tx, template_id=command.prompt_template_id,
                    expected_lock_version=command.expected_lock_version,
                )
                if changed != command.expected_lock_version + 1:
                    raise PromptRetireError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_PROMPT_RETIRE", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-03",
                    target_object_id=command.prompt_template_id,
                    before_state=target.state, after_state="RETIRED",
                ))
                result = RetiredPromptTemplate(
                    uuid.UUID(new_uuid7()), command.prompt_template_id, actor,
                    audit_id, command.trace_id, target.state, target.active_version_no,
                    "RETIRED", command.expected_lock_version, changed,
                )
                self._repo.save_result(tx, result=result)
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, result.result_id, 200,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except PromptRetireError:
            raise
        except RuntimeLicenseError:
            raise PromptRetireError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise PromptRetireError(exc.code) from None
        except Exception:
            raise PromptRetireError() from None

    def _require_admin(self, tx: object, command: RetirePromptTemplate) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PromptRetireError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PromptRetireError("AUTH_ACCESS_DENIED")
        return actor
