"""Internal project Egress Authorization and one-way revocation services."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.egress_preview import EgressPreviewView
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)


_AUTHORIZE = "V1_EGRESS_AUTHORIZE"
_REVOKE = "V1_EGRESS_REVOKE"
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ROLE = {
    "PROJECT_MANAGER": "ProjectManager",
    "CUSTOMER_MANAGER": "CustomerManager",
}


class EgressAuthorizationError(RuntimeError):
    def __init__(self, code: str = "AI_EGRESS_AUTHORIZATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AuthorizeEgress:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    preview_id: uuid.UUID
    expected_preview_fingerprint: bytes = field(repr=False)
    allowed_data_categories: tuple[str, ...]
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class RevokeEgress:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    authorization_id: uuid.UUID
    expected_lock_version: int
    reason_code: str
    reason_summary: str


@dataclass(frozen=True, slots=True)
class EgressAuthorizationView:
    authorization_id: uuid.UUID
    preview_id: uuid.UUID
    project_id: uuid.UUID
    purpose_ref: str
    operation_type: str
    provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    model_id: uuid.UUID
    data_region: str
    allowed_data_categories: tuple[str, ...]
    minimal_payload_policy_ref: str
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    approved_by: uuid.UUID
    approved_role: str
    approved_at: datetime
    valid_until: datetime
    state: str
    lock_version: int


@dataclass(frozen=True, slots=True)
class EgressAuthorizeResult:
    result_id: uuid.UUID
    authorization: EgressAuthorizationView
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class EgressRevokeResult:
    result_id: uuid.UUID
    authorization_id: uuid.UUID
    revocation_id: uuid.UUID
    actor_id: uuid.UUID
    revoked_role: str
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    state: str
    lock_version: int
    revoked_at: datetime


@dataclass(frozen=True, slots=True)
class EgressApprovalFacts:
    actor_id: uuid.UUID
    project_role: str
    preview: EgressPreviewView
    allowed_data_categories: tuple[str, ...]
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class EgressAuthorizationCreate:
    authorization_id: uuid.UUID
    preview: EgressPreviewView
    allowed_data_categories: tuple[str, ...]
    max_record_count: int
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    approved_by: uuid.UUID
    approved_role: str
    valid_until: datetime


class EgressApprovalPolicyPort(Protocol):
    def permits(self, transaction: object, *, facts: EgressApprovalFacts) -> bool: ...


class EgressAuthorizationAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class EgressAuthorizationLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EgressAuthorizationRepositoryPort(Protocol):
    def preview_for_authorize(self, transaction: object, *, preview_id: uuid.UUID,
                              project_id: uuid.UUID) -> EgressPreviewView | None: ...
    def create_authorization(self, transaction: object, *,
                             request: EgressAuthorizationCreate) -> EgressAuthorizationView: ...
    def save_authorize_result(self, transaction: object, *, result_id: uuid.UUID,
                              authorization: EgressAuthorizationView,
                              audit_event_id: uuid.UUID, trace_id: uuid.UUID) -> None: ...
    def get_authorize_result(self, transaction: object, *, result_id: uuid.UUID,
                             preview_id: uuid.UUID, project_id: uuid.UUID,
                             actor_id: uuid.UUID) -> EgressAuthorizeResult | None: ...
    def authorization_for_revoke(self, transaction: object, *, authorization_id: uuid.UUID,
                                 project_id: uuid.UUID) -> EgressAuthorizationView | None: ...
    def revoke(self, transaction: object, *, authorization: EgressAuthorizationView,
               actor_id: uuid.UUID, revoked_role: str, reason_code: str,
               reason_summary: str, audit_event_id: uuid.UUID,
               trace_id: uuid.UUID) -> EgressRevokeResult: ...
    def get_revoke_result(self, transaction: object, *, result_id: uuid.UUID,
                          authorization_id: uuid.UUID, project_id: uuid.UUID,
                          actor_id: uuid.UUID) -> EgressRevokeResult | None: ...


class EgressAuthorizationReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class EgressAuthorizationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: EgressAuthorizationAccessPort,
                 license_guard: EgressAuthorizationLicensePort,
                 authorization: ProjectAuthorizationService,
                 approval_policy: EgressApprovalPolicyPort,
                 repository: EgressAuthorizationRepositoryPort,
                 receipts: EgressAuthorizationReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, approval_policy,
            repository, receipts, audit,
        )):
            raise ValueError("Egress Authorization dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._policy = authorization, approval_policy
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def authorize(self, command: AuthorizeEgress, *, idempotency_key: str) -> EgressAuthorizeResult:
        self._validate_authorize(command)
        try:
            validate_idempotency_key(idempotency_key)
            categories = tuple(sorted(command.allowed_data_categories))
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "preview_id": str(command.preview_id),
                "preview_fingerprint": command.expected_preview_fingerprint.hex(),
                "allowed_data_categories": list(categories),
                "max_record_count": command.max_record_count,
                "max_payload_bytes": command.max_payload_bytes,
                "max_input_tokens": command.max_input_tokens,
                "max_retry_attempts": command.max_retry_attempts,
                "valid_until": command.valid_until.astimezone(timezone.utc).isoformat(),
            })
            with self._uow() as tx:
                self._actor_action(tx, command.session_token, command.csrf_token,
                                   command.project_id, "EGRESS_AUTHORIZE")
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now, action = self._actor_action(
                    tx, command.session_token, command.csrf_token,
                    command.project_id, "EGRESS_AUTHORIZE",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=action.user_id, project_id=command.project_id,
                    operation=_AUTHORIZE, key=idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _AUTHORIZE or replay.status_code != 201:
                        raise EgressAuthorizationError()
                    original = self._repository.get_authorize_result(
                        tx, result_id=replay.ref_id, preview_id=command.preview_id,
                        project_id=command.project_id, actor_id=action.user_id,
                    )
                    if type(original) is not EgressAuthorizeResult:
                        raise EgressAuthorizationError()
                    return original
                preview = self._repository.preview_for_authorize(
                    tx, preview_id=command.preview_id, project_id=command.project_id,
                )
                if type(preview) is not EgressPreviewView:
                    raise EgressAuthorizationError("RESOURCE_NOT_FOUND")
                if preview.preview_fingerprint != command.expected_preview_fingerprint:
                    raise EgressAuthorizationError("CONFLICT_VERSION")
                valid_until = command.valid_until.astimezone(timezone.utc)
                facts = EgressApprovalFacts(
                    action.user_id, action.project_role, preview, categories,
                    command.max_record_count, command.max_payload_bytes,
                    command.max_input_tokens, command.max_retry_attempts, valid_until,
                )
                if (now >= preview.expires_at.astimezone(timezone.utc)
                        or valid_until <= now
                        or valid_until > preview.expires_at.astimezone(timezone.utc)
                        or not set(categories).issubset(preview.allowed_data_categories)
                        or command.max_record_count > preview.estimated_record_count
                        or command.max_payload_bytes > preview.max_payload_bytes
                        or command.max_input_tokens > preview.max_input_tokens
                        or command.max_retry_attempts > preview.max_retry_attempts
                        or self._policy.permits(tx, facts=facts) is not True):
                    raise EgressAuthorizationError("AI_EGRESS_APPROVAL_DENIED")
                approved_role = _ROLE.get(action.project_role)
                if approved_role is None:
                    raise EgressAuthorizationError("RESOURCE_NOT_FOUND")
                authorization = self._repository.create_authorization(
                    tx, request=EgressAuthorizationCreate(
                        uuid.UUID(new_uuid7()), preview, categories,
                        command.max_record_count, command.max_payload_bytes,
                        command.max_input_tokens, command.max_retry_attempts,
                        action.user_id, approved_role, valid_until,
                    ),
                )
                if type(authorization) is not EgressAuthorizationView:
                    raise EgressAuthorizationError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=action.user_id, original_actor_id=None,
                    actor_hint_digest=None, action="AI_EGRESS_AUTHORIZED",
                    outcome="SUCCESS", target_owner_module="ai",
                    target_object_type="AI-04",
                    target_object_id=authorization.authorization_id,
                    target_version_id=command.preview_id,
                    after_state="AUTHORIZED",
                ))
                result_id = uuid.UUID(new_uuid7())
                self._repository.save_authorize_result(
                    tx, result_id=result_id, authorization=authorization,
                    audit_event_id=audit_id, trace_id=command.trace_id,
                )
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_AUTHORIZE, result_id, 201),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return EgressAuthorizeResult(
                    result_id, authorization, audit_id, command.trace_id,
                )
        except EgressAuthorizationError:
            raise
        except ProjectAuthorizationError as error:
            raise EgressAuthorizationError(error.code) from None
        except RuntimeLicenseError:
            raise EgressAuthorizationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise EgressAuthorizationError(error.code) from None
        except Exception:
            raise EgressAuthorizationError() from None

    def revoke(self, command: RevokeEgress, *, idempotency_key: str) -> EgressRevokeResult:
        self._validate_revoke(command)
        summary = command.reason_summary.strip()
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "authorization_id": str(command.authorization_id),
                "expected_lock_version": command.expected_lock_version,
                "reason_code": command.reason_code, "reason_summary": summary,
            })
            with self._uow() as tx:
                self._actor_action(tx, command.session_token, command.csrf_token,
                                   command.project_id, "EGRESS_REVOKE")
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                _, action = self._actor_action(
                    tx, command.session_token, command.csrf_token,
                    command.project_id, "EGRESS_REVOKE",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=action.user_id, project_id=command.project_id,
                    operation=_REVOKE, key=idempotency_key,
                )
                replay = self._receipts.reserve(tx, scope=scope,
                                                request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _REVOKE or replay.status_code != 200:
                        raise EgressAuthorizationError()
                    original = self._repository.get_revoke_result(
                        tx, result_id=replay.ref_id,
                        authorization_id=command.authorization_id,
                        project_id=command.project_id, actor_id=action.user_id,
                    )
                    if type(original) is not EgressRevokeResult:
                        raise EgressAuthorizationError()
                    return original
                authorization = self._repository.authorization_for_revoke(
                    tx, authorization_id=command.authorization_id,
                    project_id=command.project_id,
                )
                if type(authorization) is not EgressAuthorizationView:
                    raise EgressAuthorizationError("RESOURCE_NOT_FOUND")
                if (authorization.state != "AUTHORIZED"
                        or authorization.lock_version != command.expected_lock_version):
                    raise EgressAuthorizationError("CONFLICT_VERSION")
                mapped_role = _ROLE.get(action.project_role)
                if mapped_role is None:
                    raise EgressAuthorizationError("RESOURCE_NOT_FOUND")
                revoked_role = (
                    "OriginalApprover"
                    if action.user_id == authorization.approved_by else mapped_role
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=action.user_id, original_actor_id=None,
                    actor_hint_digest=None, action="AI_EGRESS_REVOKED",
                    outcome="SUCCESS", target_owner_module="ai",
                    target_object_type="AI-04",
                    target_object_id=authorization.authorization_id,
                    before_state="AUTHORIZED", after_state="REVOKED",
                ))
                result = self._repository.revoke(
                    tx, authorization=authorization, actor_id=action.user_id,
                    revoked_role=revoked_role, reason_code=command.reason_code,
                    reason_summary=summary, audit_event_id=audit_id,
                    trace_id=command.trace_id,
                )
                if type(result) is not EgressRevokeResult:
                    raise EgressAuthorizationError()
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_REVOKE, result.result_id, 200),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except EgressAuthorizationError:
            raise
        except ProjectAuthorizationError as error:
            raise EgressAuthorizationError(error.code) from None
        except RuntimeLicenseError:
            raise EgressAuthorizationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise EgressAuthorizationError(error.code) from None
        except Exception:
            raise EgressAuthorizationError() from None

    @staticmethod
    def _validate_authorize(command: AuthorizeEgress) -> None:
        if (type(command) is not AuthorizeEgress
                or not EgressAuthorizationService._valid_common(command)
                or type(command.preview_id) is not uuid.UUID or not command.preview_id.int
                or type(command.expected_preview_fingerprint) is not bytes
                or len(command.expected_preview_fingerprint) != 32
                or type(command.allowed_data_categories) is not tuple
                or not 1 <= len(command.allowed_data_categories) <= 64
                or len(set(command.allowed_data_categories)) != len(command.allowed_data_categories)
                or any(type(item) is not str or _CODE.fullmatch(item) is None
                       for item in command.allowed_data_categories)
                or type(command.max_record_count) is not int
                or not 0 <= command.max_record_count <= 1_000_000_000
                or type(command.max_payload_bytes) is not int
                or not 1 <= command.max_payload_bytes <= 1_073_741_824
                or type(command.max_input_tokens) is not int
                or not 1 <= command.max_input_tokens <= 1_048_576
                or type(command.max_retry_attempts) is not int
                or not 1 <= command.max_retry_attempts <= 10
                or not isinstance(command.valid_until, datetime)
                or command.valid_until.tzinfo is None
                or command.valid_until.utcoffset() is None):
            raise EgressAuthorizationError("VALIDATION_FAILED")

    @staticmethod
    def _validate_revoke(command: RevokeEgress) -> None:
        if (type(command) is not RevokeEgress
                or not EgressAuthorizationService._valid_common(command)
                or type(command.authorization_id) is not uuid.UUID
                or not command.authorization_id.int
                or command.expected_lock_version != 0
                or type(command.reason_code) is not str
                or _CODE.fullmatch(command.reason_code) is None
                or type(command.reason_summary) is not str
                or not 1 <= len(command.reason_summary.strip()) <= 2000):
            raise EgressAuthorizationError("VALIDATION_FAILED")

    @staticmethod
    def _valid_common(command: object) -> bool:
        return (type(getattr(command, "session_token", None)) is bytes
                and len(command.session_token) == 32
                and type(getattr(command, "csrf_token", None)) is bytes
                and len(command.csrf_token) == 32
                and type(getattr(command, "trace_id", None)) is uuid.UUID
                and bool(command.trace_id.int)
                and type(getattr(command, "project_id", None)) is uuid.UUID
                and bool(command.project_id.int))

    def _actor_action(self, tx: object, session_token: bytes, csrf_token: bytes,
                      project_id: uuid.UUID,
                      operation: str) -> tuple[datetime, AuthorizedProjectAction]:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise EgressAuthorizationError()
        now = now.astimezone(timezone.utc)
        actor = self._access.authenticated_user(
            tx, session_token=session_token, csrf_token=csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise EgressAuthorizationError("AUTH_ACCESS_DENIED")
        action = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id, operation=operation,
        )
        if type(action) is not AuthorizedProjectAction:
            raise EgressAuthorizationError("RESOURCE_NOT_FOUND")
        return now, action
