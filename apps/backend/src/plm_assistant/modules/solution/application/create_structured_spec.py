"""Authorized atomic SOL-06 DRAFT creation with durable exact replay."""

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

from .prove_structured_spec_sources import (
    ProvenStructuredSpecSources, StructuredSpecSourceError,
    StructuredSpecSourceProofService,
)
from .structured_spec_input import (
    StructuredSpecDraftInput, StructuredSpecInputError,
    validate_structured_spec_draft,
)
from .structured_spec_result import StructuredSpecInitialView


_OPERATION = "V1_SOL_STRUCTURED_SPEC_CREATE"
_POLICY = "SOL_STRUCTURED_SPEC_CREATE"


class StructuredSpecCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateStructuredSpec:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    draft: StructuredSpecDraftInput = field(repr=False)
    idempotency_key: str = field(repr=False)


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenStructuredSpecSources) -> StructuredSpecInitialView: ...

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> StructuredSpecInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class StructuredSpecCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 sources: StructuredSpecSourceProofService,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                sources, repository, receipts, audit)):
            raise ValueError("StructuredSpec create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources = authorization, sources
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateStructuredSpec) -> StructuredSpecInitialView:
        if (type(command) is not CreateStructuredSpec
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0):
            raise StructuredSpecCreateError("VALIDATION_FAILED")
        try:
            draft = validate_structured_spec_draft(command.draft)
            validate_idempotency_key(command.idempotency_key)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=draft.project_id,
                    operation=_POLICY)
                if (authorized.user_id != actor
                        or authorized.project_id != draft.project_id
                        or authorized.operation != _POLICY):
                    raise StructuredSpecCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=draft.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope,
                    request_fingerprint=draft.request_fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise StructuredSpecCreateError()
                    result = self._repository.first_result(
                        tx, version_id=previous.ref_id,
                        project_id=draft.project_id)
                    if (type(result) is not StructuredSpecInitialView
                            or result.created_by != actor
                            or result.spec_type != draft.spec_type
                            or result.payload_fingerprint != draft.payload_fingerprint
                            or result.requirement_refs != draft.requirement_refs
                            or result.section_refs != draft.section_refs
                            or result.evidence_ids != draft.evidence_ids
                            or result.artifact_ids != draft.artifact_ids
                            or result.supersedes_version_ref
                            != draft.supersedes_version_ref
                            or (draft.spec_series_id is not None
                                and result.spec_series_id != draft.spec_series_id)):
                        raise StructuredSpecCreateError()
                    return result
                proof = self._sources.prove(
                    tx, session_token=command.session_token,
                    trace_id=command.trace_id, draft=command.draft)
                if (type(proof) is not ProvenStructuredSpecSources
                        or proof.draft != draft
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    raise StructuredSpecCreateError()
                version_id = uuid.UUID(new_uuid7())
                result = self._repository.create(
                    tx, version_id=version_id, actor_id=actor, proof=proof)
                if (type(result) is not StructuredSpecInitialView
                        or result.structured_solution_spec_id != version_id
                        or result.project_id != draft.project_id
                        or result.spec_type != draft.spec_type
                        or result.content_fingerprint != proof.content_fingerprint
                        or result.payload_json != draft.payload_json
                        or result.payload_fingerprint != draft.payload_fingerprint
                        or result.requirement_refs != draft.requirement_refs
                        or result.section_refs != draft.section_refs
                        or result.evidence_ids != draft.evidence_ids
                        or result.artifact_ids != draft.artifact_ids
                        or result.supersedes_version_ref
                        != draft.supersedes_version_ref
                        or (draft.spec_series_id is not None
                            and result.spec_series_id != draft.spec_series_id)
                        or (draft.spec_series_id is None and result.version_no != 1)
                        or result.created_by != actor):
                    raise StructuredSpecCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=draft.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None,
                    action="SOL_STRUCTURED_SPEC_CREATED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-06",
                    target_object_id=result.spec_series_id,
                    target_version_id=version_id, after_state="DRAFT",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201))
                tx.commit()
                return result
        except StructuredSpecCreateError:
            raise
        except (StructuredSpecInputError, IdempotencyError) as error:
            raise StructuredSpecCreateError(error.code) from None
        except ProjectAuthorizationError as error:
            raise StructuredSpecCreateError(error.code) from None
        except RuntimeLicenseError:
            raise StructuredSpecCreateError("LICENSE_OPERATION_DENIED") from None
        except StructuredSpecSourceError as error:
            raise StructuredSpecCreateError(error.code) from None
        except Exception:
            raise StructuredSpecCreateError() from None

    def _actor(self, tx: object, command: CreateStructuredSpec) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise StructuredSpecCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise StructuredSpecCreateError("AUTH_ACCESS_DENIED")
        return actor
