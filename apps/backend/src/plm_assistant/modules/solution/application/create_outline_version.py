"""Authorized, atomic first DRAFT OutlineVersion creation and replay."""

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
    validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .outline_version_input import (
    OutlineVersionDraftInput, OutlineVersionInputError,
    validate_outline_version_draft,
)
from .prove_outline_version_input import (
    OutlineVersionInputProofError, OutlineVersionInputProofService,
    ProvenOutlineVersionInput,
)


_OPERATION = "V1_SOL_OUTLINE_VERSION_CREATE"


class OutlineVersionCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateOutlineVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    draft: OutlineVersionDraftInput = field(repr=False)
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class OutlineVersionInitialView:
    solution_outline_version_id: uuid.UUID
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    content_fingerprint: bytes = field(repr=False)
    missing_declarations: tuple[dict[str, object], ...] = field(repr=False)
    conflict_declarations: tuple[dict[str, object], ...] = field(repr=False)
    declared_section_count: int
    declared_requirement_count: int
    declared_reference_count: int
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    version_state: str = "DRAFT"
    review_ref: None = None
    review_round_ref: None = None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.solution_outline_version_id, self.solution_outline_id,
                self.project_id, self.created_by))
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.missing_declarations) is not tuple
                or type(self.conflict_declarations) is not tuple
                or any(type(item) is not dict for item in (
                    *self.missing_declarations, *self.conflict_declarations))
                or any(type(value) is not int or value < 0 for value in (
                    self.declared_section_count, self.declared_requirement_count,
                    self.declared_reference_count))
                or self.declared_section_count < 1
                or (self.supersedes_version_ref is not None and (
                    type(self.supersedes_version_ref) is not uuid.UUID
                    or self.supersedes_version_ref.int == 0))
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None
                or self.created_at.utcoffset() is None
                or self.version_state != "DRAFT"
                or self.review_ref is not None or self.review_round_ref is not None):
            raise ValueError("invalid initial OutlineVersion view")


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenOutlineVersionInput) -> OutlineVersionInitialView: ...

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> OutlineVersionInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class OutlineVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 inputs: OutlineVersionInputProofService,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                inputs, repository, receipts, audit)):
            raise ValueError("OutlineVersion create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._inputs = authorization, inputs
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateOutlineVersion) -> OutlineVersionInitialView:
        if (type(command) is not CreateOutlineVersion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0):
            raise OutlineVersionCreateError("VALIDATION_FAILED")
        try:
            draft = validate_outline_version_draft(command.draft)
            validate_idempotency_key(command.idempotency_key)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=draft.project_id,
                    operation="SOL_OUTLINE_VERSION_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != draft.project_id
                        or authorized.operation != "SOL_OUTLINE_VERSION_CREATE"):
                    raise OutlineVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=draft.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=draft.request_fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise OutlineVersionCreateError()
                    result = self._repository.first_result(
                        tx, version_id=previous.ref_id, project_id=draft.project_id)
                    if (type(result) is not OutlineVersionInitialView
                            or result.solution_outline_id != draft.solution_outline_id
                            or result.created_by != actor):
                        raise OutlineVersionCreateError()
                    return result
                proof = self._inputs.prove(tx, trace_id=command.trace_id,
                                           draft=command.draft)
                if (type(proof) is not ProvenOutlineVersionInput
                        or proof.draft.request_fingerprint != draft.request_fingerprint
                        or proof.draft.project_id != draft.project_id
                        or proof.draft.solution_outline_id != draft.solution_outline_id
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    raise OutlineVersionCreateError()
                version_id = uuid.UUID(new_uuid7())
                result = self._repository.create(
                    tx, version_id=version_id, actor_id=actor, proof=proof)
                if (type(result) is not OutlineVersionInitialView
                        or result.solution_outline_version_id != version_id
                        or result.solution_outline_id != draft.solution_outline_id
                        or result.project_id != draft.project_id
                        or result.version_no != proof.next_version_no
                        or result.content_fingerprint != proof.content_fingerprint
                        or result.created_by != actor):
                    raise OutlineVersionCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=draft.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SOL_OUTLINE_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-02",
                    target_object_id=draft.solution_outline_id,
                    target_version_id=version_id, after_state="DRAFT",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201))
                tx.commit()
                return result
        except OutlineVersionCreateError:
            raise
        except (OutlineVersionInputError, IdempotencyError) as error:
            raise OutlineVersionCreateError(error.code) from None
        except ProjectAuthorizationError as error:
            raise OutlineVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except OutlineVersionInputProofError as error:
            raise OutlineVersionCreateError(error.code) from None
        except Exception:
            raise OutlineVersionCreateError() from None

    def _actor(self, tx: object, command: CreateOutlineVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise OutlineVersionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise OutlineVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
