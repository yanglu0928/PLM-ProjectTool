"""Current-authorized explicit retry for one terminal AI Task generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.exc import DBAPIError

from plm_assistant.modules.ai.application.create_task import (
    AuthorizedEgressSnapshot,
    EgressAuthorizationOwnerError,
    EgressAuthorizationQuery,
)
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.retry_request import (
    JobRetryError,
    JobRetryResult,
    RequestJobRetry,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationError


_OPERATION = "V1_AI_TASK_USER_RETRY"


class AITaskRetryError(RuntimeError):
    def __init__(self, code: str = "AI_TASK_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AITaskRetryEgressProof:
    authorization_ref: uuid.UUID
    purpose_ref: str
    ai_provider_id: uuid.UUID
    provider_config_version_id: uuid.UUID
    ai_model_id: uuid.UUID
    data_region: str
    allowed_data_categories: tuple[str, ...]
    authorization_fingerprint: bytes = field(repr=False)
    preview_payload_fingerprint: bytes = field(repr=False)
    source_refs_fingerprint: bytes = field(repr=False)
    approved_by: uuid.UUID
    approved_role: str
    approved_at: datetime
    valid_until: datetime
    content_plan_ref: uuid.UUID
    max_payload_bytes: int
    max_input_tokens: int
    max_retry_attempts: int
    authorization_state: str

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.authorization_ref, self.ai_provider_id,
                self.provider_config_version_id, self.ai_model_id,
                self.approved_by, self.content_plan_ref,
            )) or any(type(value) is not bytes or len(value) != 32 for value in (
                self.authorization_fingerprint, self.preview_payload_fingerprint,
                self.source_refs_fingerprint,
            )) or type(self.allowed_data_categories) is not tuple
                or not self.allowed_data_categories
                or any(type(value) is not str or not value for value in (
                    self.purpose_ref, self.data_region, self.approved_role,
                    self.authorization_state, *self.allowed_data_categories,
                )) or not isinstance(self.approved_at, datetime)
                or self.approved_at.tzinfo is None
                or not isinstance(self.valid_until, datetime)
                or self.valid_until.tzinfo is None
                or self.approved_at >= self.valid_until
                or type(self.max_payload_bytes) is not int
                or self.max_payload_bytes < 1
                or type(self.max_input_tokens) is not int
                or self.max_input_tokens < 1
                or type(self.max_retry_attempts) is not int
                or not 1 <= self.max_retry_attempts <= 10
                or self.authorization_state != "AUTHORIZED"):
            raise AITaskRetryError("JOB_NOT_RETRYABLE")


@dataclass(frozen=True, slots=True)
class AITaskRetryBinding:
    ai_task_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    task_type: str
    task_state: str
    retryable: bool | None
    input_fingerprint: bytes = field(repr=False)
    task_lock_version: int
    job_lock_version: int
    egress: AITaskRetryEgressProof

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.ai_task_id, self.job_id, self.project_id, self.requested_by))
                or self.task_state not in {"FAILED", "CANCELLED"}
                or (self.task_state == "FAILED" and self.retryable is not True)
                or type(self.task_type) is not str or not self.task_type
                or type(self.input_fingerprint) is not bytes
                or len(self.input_fingerprint) != 32
                or any(type(value) is not int or value < 0 for value in (
                    self.task_lock_version, self.job_lock_version,
                )) or type(self.egress) is not AITaskRetryEgressProof):
            raise AITaskRetryError("JOB_NOT_RETRYABLE")
        self.egress.__post_init__()


@dataclass(frozen=True, slots=True)
class AITaskRetryGeneration:
    source_ai_task_id: uuid.UUID
    source_job_id: uuid.UUID
    new_ai_task_id: uuid.UUID
    new_job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    root_ai_task_id: uuid.UUID
    generation_no: int
    expected_source_version: int
    retry_audit_event_id: uuid.UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.source_ai_task_id, self.source_job_id, self.new_ai_task_id,
                self.new_job_id, self.project_id, self.requested_by,
                self.root_ai_task_id, self.retry_audit_event_id,
            )) or self.source_ai_task_id == self.new_ai_task_id
                or self.source_job_id == self.new_job_id
                or type(self.generation_no) is not int
                or not 1 <= self.generation_no <= 10
                or type(self.expected_source_version) is not int
                or self.expected_source_version < 0
                or not isinstance(self.created_at, datetime)
                or self.created_at.tzinfo is None
                or self.created_at.utcoffset() is None):
            raise AITaskRetryError()


class AITaskJobRetryOwner:
    """AI Owner adapter for the frozen Project Job retry endpoint."""

    def __init__(self, *, unit_of_work, repository, session_access, projects,
                 license_guard, egress_owner, receipts, audit, clock=None) -> None:
        if any(value is None for value in (
                unit_of_work, repository, session_access, projects, license_guard,
                egress_owner, receipts, audit)):
            raise ValueError("Current AI retry dependencies required")
        self._uow, self._repo = unit_of_work, repository
        self._access, self._projects = session_access, projects
        self._guard, self._egress = license_guard, egress_owner
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _deadlock(error: BaseException) -> bool:
        seen: set[int] = set()
        for _ in range(16):
            if id(error) in seen:
                return False
            seen.add(id(error))
            if isinstance(error, DBAPIError) and getattr(error.orig, "sqlstate", None) == "40P01":
                return True
            nested = error.__cause__ or error.__context__
            if not isinstance(nested, BaseException):
                return False
            error = nested
        return False

    def _authorize(self, tx, command: RequestJobRetry,
                   binding: AITaskRetryBinding) -> tuple[uuid.UUID, datetime]:
        self._guard.require_valid(trace_id=command.trace_id)
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AITaskRetryError()
        now = now.astimezone(timezone.utc)
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise JobRetryError("RESOURCE_NOT_FOUND")
        proof = self._projects.require_in_transaction(
            tx, user_id=actor, project_id=binding.project_id,
            operation="JOB_PROJECT_RETRY",
        )
        if (proof.user_id != actor or proof.project_id != binding.project_id
                or (actor != binding.requested_by
                    and proof.project_role != "PROJECT_MANAGER")):
            raise JobRetryError("RESOURCE_NOT_FOUND")
        return actor, now

    @staticmethod
    def _current_egress_matches(binding: AITaskRetryBinding,
                                current: AuthorizedEgressSnapshot) -> bool:
        old = binding.egress
        return type(current) is AuthorizedEgressSnapshot and (
            current.authorization_ref, current.project_id, current.purpose_ref,
            current.ai_provider_id, current.provider_config_version_id,
            current.ai_model_id, current.data_region,
            current.allowed_data_categories, current.authorization_fingerprint,
            current.preview_payload_fingerprint, current.source_refs_fingerprint,
            current.approved_by, current.approved_role, current.approved_at,
            current.valid_until, current.content_plan_ref,
            current.max_payload_bytes, current.max_input_tokens,
            current.max_retry_attempts, current.authorization_state,
        ) == (
            old.authorization_ref, binding.project_id, old.purpose_ref,
            old.ai_provider_id, old.provider_config_version_id,
            old.ai_model_id, old.data_region, old.allowed_data_categories,
            old.authorization_fingerprint, old.preview_payload_fingerprint,
            old.source_refs_fingerprint, old.approved_by, old.approved_role,
            old.approved_at, old.valid_until, old.content_plan_ref,
            old.max_payload_bytes, old.max_input_tokens,
            old.max_retry_attempts, old.authorization_state,
        )

    def _resolve_egress(self, tx, binding: AITaskRetryBinding,
                        now: datetime) -> AuthorizedEgressSnapshot:
        current = self._egress.resolve_authorized(
            tx, query=EgressAuthorizationQuery(
                binding.egress.authorization_ref, binding.project_id,
                binding.task_type, binding.egress.source_refs_fingerprint, now,
            ),
        )
        if not self._current_egress_matches(binding, current):
            raise AITaskRetryError("JOB_NOT_RETRYABLE")
        return current

    def retry(self, command: RequestJobRetry, *, idempotency_key: str) -> JobRetryResult:
        if type(command) is not RequestJobRetry or command.project_id is None:
            raise JobRetryError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc:
            raise JobRetryError(exc.code) from None
        for attempt in range(3):
            try:
                return self._retry_once(command, idempotency_key)
            except Exception as exc:
                if self._deadlock(exc):
                    if attempt < 2:
                        continue
                    raise JobRetryError() from None
                if isinstance(exc, JobRetryError):
                    raise
                if isinstance(exc, (IdempotencyError, ProjectAuthorizationError)):
                    code = exc.code if isinstance(exc, IdempotencyError) else "RESOURCE_NOT_FOUND"
                    raise JobRetryError(code) from None
                if isinstance(exc, RuntimeLicenseError):
                    raise JobRetryError("LICENSE_OPERATION_DENIED") from None
                if isinstance(exc, EgressAuthorizationOwnerError):
                    raise JobRetryError("JOB_NOT_RETRYABLE") from None
                if isinstance(exc, AITaskRetryError):
                    code = exc.code if exc.code in {
                        "RESOURCE_NOT_FOUND", "CONFLICT_VERSION",
                        "JOB_NOT_RETRYABLE", "VALIDATION_FAILED",
                    } else "JOB_UNAVAILABLE"
                    raise JobRetryError(code) from None
                raise JobRetryError() from None
        raise JobRetryError()

    def _retry_once(self, command: RequestJobRetry, key: str) -> JobRetryResult:
        with self._uow() as tx:
            binding = self._repo.binding(
                tx, job_id=command.job_id, project_id=command.project_id,
            )
            if type(binding) is not AITaskRetryBinding:
                raise JobRetryError("RESOURCE_NOT_FOUND")
            binding.__post_init__()
            actor, now = self._authorize(tx, command, binding)
            scope = IdempotencyScope.from_key(
                actor_id=actor, project_id=command.project_id,
                operation=_OPERATION, key=key,
            )
            fingerprint = canonical_payload_fingerprint({
                "source_ai_task_id": str(binding.ai_task_id),
                "source_job_id": str(binding.job_id),
                "expected_version": command.expected_version,
            })
            replay = self._receipts.reserve(
                tx, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                if (type(replay) is not IdempotencyResult
                        or replay.ref_type != _OPERATION or replay.status_code != 202):
                    raise AITaskRetryError()
                result = self._repo.replay(
                    tx, new_ai_task_id=replay.ref_id,
                    source_job_id=command.job_id,
                    project_id=command.project_id, requested_by=actor,
                )
            else:
                if binding.job_lock_version != command.expected_version:
                    raise AITaskRetryError("CONFLICT_VERSION")
                self._resolve_egress(tx, binding, now)
                draft = self._repo.create(
                    tx, binding=binding, requested_by=actor,
                    trace_id=command.trace_id,
                    expected_source_version=command.expected_version,
                )
                event_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="AI_TASK_USER_RETRY_REQUESTED", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-04",
                    target_object_id=draft.new_ai_task_id,
                    target_version_id=binding.ai_task_id,
                    reason_code="USER_RETRY", before_state=binding.task_state,
                    after_state="QUEUED",
                ))
                result = self._repo.record_lineage(
                    tx, draft=draft, retry_audit_event_id=event_id,
                )
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, result.new_ai_task_id, 202),
                )
            if type(result) is not AITaskRetryGeneration:
                raise AITaskRetryError()
            result.__post_init__()
            if ((result.source_ai_task_id, result.source_job_id,
                 result.project_id, result.requested_by,
                 result.expected_source_version) !=
                    (binding.ai_task_id, binding.job_id, binding.project_id,
                     actor, command.expected_version)):
                raise AITaskRetryError()
            actor_again, now_again = self._authorize(tx, command, binding)
            if actor_again != actor:
                raise JobRetryError("RESOURCE_NOT_FOUND")
            self._resolve_egress(tx, binding, now_again)
            if replay is None:
                tx.commit()
            return JobRetryResult(
                result.source_job_id, result.new_job_id, result.project_id,
                "PROJECT", result.created_at,
            )
