"""Authorized, idempotent AIModel registration; never routes or contacts a model."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.exc import IntegrityError

from plm_assistant.modules.ai.domain.model_definition import (
    AIModelDefinition, AIModelDefinitionError, AIModelKind,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class AIModelCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateAIModel:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    provider_id: uuid.UUID
    provider_model_key: str
    kind: AIModelKind
    revision: str
    embedding_dimension: int | None
    structured_output: bool
    context_window_tokens: int | None
    quality_profile_refs: tuple[str, ...]
    idempotency_key: str = field(repr=False)


class AIModelCreateAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class AIModelLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class AIModelCreateRepositoryPort(Protocol):
    def provider_accepts(self, transaction: object, *, definition: AIModelDefinition) -> bool: ...

    def create(self, transaction: object, *, definition: AIModelDefinition,
               actor_id: uuid.UUID) -> None: ...

    def belongs_to_provider(self, transaction: object, *, model_id: uuid.UUID,
                            provider_id: uuid.UUID) -> bool: ...


class AIModelReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AIModelCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AIModelCreateAccessPort,
                 license_guard: AIModelLicensePort, repository: AIModelCreateRepositoryPort,
                 receipts: AIModelReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, repository,
                                         receipts, audit)):
            raise ValueError("AI Model dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateAIModel) -> uuid.UUID:
        if (type(command) is not CreateAIModel
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.quality_profile_refs) is not tuple
                or any(type(item) is not str for item in command.quality_profile_refs)):
            raise AIModelCreateError("VALIDATION_FAILED")
        if command.quality_profile_refs:
            raise AIModelCreateError("AI_MODEL_QUALITY_UNVERIFIED")
        try:
            validate_idempotency_key(command.idempotency_key)
            definition = AIModelDefinition(
                model_id=uuid.UUID(new_uuid7()), provider_id=command.provider_id,
                provider_model_key=command.provider_model_key, kind=command.kind,
                revision=command.revision, embedding_dimension=command.embedding_dimension,
                structured_output=command.structured_output,
                context_window_tokens=command.context_window_tokens,
            )
            fingerprint = canonical_payload_fingerprint({
                "provider_id": str(definition.provider_id),
                "provider_model_key": definition.provider_model_key,
                "kind": definition.kind.value, "revision": definition.revision,
                "embedding_dimension": definition.embedding_dimension,
                "structured_output": definition.structured_output,
                "context_window_tokens": definition.context_window_tokens,
                "quality_profile_refs": [],
            })
        except (IdempotencyError, AIModelDefinitionError):
            raise AIModelCreateError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_AI_MODEL_CREATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != "V1_AI_MODEL_CREATE" or replay.status_code != 201
                            or not self._repo.belongs_to_provider(
                                tx, model_id=replay.ref_id, provider_id=definition.provider_id)):
                        raise AIModelCreateError("AI_MODEL_UNAVAILABLE")
                    return replay.ref_id
                if not self._repo.provider_accepts(tx, definition=definition):
                    raise AIModelCreateError("AI_MODEL_PROVIDER_UNAVAILABLE")
                self._repo.create(tx, definition=definition, actor_id=actor_id)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="AI_MODEL_CREATE", outcome="SUCCESS",
                    target_owner_module="ai", target_object_type="AI-02",
                    target_object_id=definition.model_id, after_state="SUSPENDED",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    "V1_AI_MODEL_CREATE", definition.model_id, 201,
                ))
                tx.commit()
                return definition.model_id
        except AIModelCreateError:
            raise
        except RuntimeLicenseError:
            raise AIModelCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise AIModelCreateError(exc.code) from None
        except IntegrityError as exc:
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_ai_models__semantic_identity":
                raise AIModelCreateError("AI_MODEL_ALREADY_EXISTS") from None
            raise AIModelCreateError("AI_MODEL_UNAVAILABLE") from None
        except Exception:
            raise AIModelCreateError("AI_MODEL_UNAVAILABLE") from None

    def _require_admin(self, tx: object, command: CreateAIModel) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AIModelCreateError("AI_MODEL_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise AIModelCreateError("AUTH_ACCESS_DENIED")
        return actor_id
