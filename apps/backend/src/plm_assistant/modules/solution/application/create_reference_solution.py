"""Atomic initial ReferenceSolution and fixed-source version creation."""

from __future__ import annotations

import unicodedata
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
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
)


_OPERATION = "V1_SOL_REFERENCE_CREATE"


class ReferenceCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateReferenceSolution:
    sources: ReferenceSourceRequest = field(repr=False)
    csrf_token: bytes = field(repr=False)
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReferenceInitialView:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    source_fingerprint: bytes = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    deidentification_confirmation_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    eligibility_state: str = "REFERENCE_ONLY"
    version_state: str = "DRAFT"
    etag: str = '"v0"'


class GlobalAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class ProjectAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SourcePort(Protocol):
    def qualify(self, transaction: object,
                request: ReferenceSourceRequest) -> QualifiedReferenceSources: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, root_id: uuid.UUID, version_id: uuid.UUID,
               name: str, actor_id: uuid.UUID, sources: ReferenceSourceRequest,
               qualified: QualifiedReferenceSources,
               content_fingerprint: bytes) -> ReferenceInitialView: ...

    def view(self, transaction: object, *, root_id: uuid.UUID, scope: str,
             project_id: uuid.UUID | None) -> ReferenceInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class ReferenceCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 global_access: GlobalAccessPort, project_access: ProjectAccessPort,
                 project_authorization: ProjectAuthorizationService,
                 license_guard: LicensePort, sources: SourcePort,
                 repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, global_access, project_access, project_authorization,
                license_guard, sources, repository, receipts, audit)):
            raise ValueError("Reference create dependencies required")
        self._uow, self._global, self._project = unit_of_work, global_access, project_access
        self._authorization, self._guard = project_authorization, license_guard
        self._sources, self._repo, self._receipts, self._audit = (
            sources, repository, receipts, audit)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateReferenceSolution) -> ReferenceInitialView:
        if (type(command) is not CreateReferenceSolution
                or type(command.sources) is not ReferenceSourceRequest
                or type(command.sources.session_token) is not bytes
                or len(command.sources.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.sources.trace_id) is not uuid.UUID
                or command.sources.trace_id.int == 0):
            raise ReferenceCreateError("VALIDATION_FAILED")
        name = self._name(command.name)
        request = command.sources
        try:
            validate_idempotency_key(command.idempotency_key)
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=request.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                qualified = self._sources.qualify(tx, request)
                self._validate_qualified(request, qualified)
                content = canonical_payload_fingerprint({
                    "name": name, "scope": request.scope,
                    "project_id": str(request.project_id) if request.project_id else None,
                    "source_fingerprint": qualified.content_fingerprint.hex(),
                    "documents": [str(item.document_version_id)
                                  for item in qualified.document_versions],
                    "evidence": [str(item.evidence_id) for item in qualified.evidence],
                    "source_project_class": request.source_project_class,
                    "deidentification_class": request.deidentification_class,
                    "applicability": request.applicability,
                })
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=request.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=content)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise ReferenceCreateError()
                    view = self._repo.view(
                        tx, root_id=replay.ref_id, scope=request.scope,
                        project_id=request.project_id)
                    if not self._matches(view, actor, name, qualified, content):
                        raise ReferenceCreateError()
                    return view
                root_id, version_id = uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7())
                view = self._repo.create(
                    tx, root_id=root_id, version_id=version_id,
                    name=name, actor_id=actor, sources=request,
                    qualified=qualified, content_fingerprint=content)
                if (not self._matches(view, actor, name, qualified, content)
                        or view.reference_solution_id != root_id
                        or view.reference_version_id != version_id):
                    raise ReferenceCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id, event_scope=(
                        "DEPLOYMENT" if request.scope == "GLOBAL" else "PROJECT"),
                    target_project_id=request.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action="SOL_REFERENCE_CREATED",
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-01", target_object_id=root_id,
                    after_state="REFERENCE_ONLY",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, root_id, 201))
                tx.commit()
                return view
        except ReferenceCreateError:
            raise
        except (ProjectAuthorizationError, ReferenceSourceError, IdempotencyError) as error:
            raise ReferenceCreateError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReferenceCreateError() from None

    def _actor(self, tx: object, command: CreateReferenceSolution) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceCreateError()
        now = now.astimezone(timezone.utc)
        request = command.sources
        if request.scope == "GLOBAL" and request.project_id is None:
            actor = self._global.authorized_admin(
                tx, session_token=request.session_token,
                csrf_token=command.csrf_token, now=now)
        elif (request.scope == "PROJECT" and type(request.project_id) is uuid.UUID
              and request.project_id.int != 0):
            actor = self._project.authenticated_user(
                tx, session_token=request.session_token,
                csrf_token=command.csrf_token, now=now)
            if type(actor) is uuid.UUID and actor.int != 0:
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=request.project_id,
                    operation="SOL_REFERENCE_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != request.project_id
                        or authorized.operation != "SOL_REFERENCE_CREATE"):
                    raise ReferenceCreateError("RESOURCE_NOT_FOUND")
        else:
            raise ReferenceCreateError("VALIDATION_FAILED")
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ReferenceCreateError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _name(value: str) -> str:
        if (type(value) is not str or not 1 <= len(value) <= 255
                or value != value.strip() or not value
                or unicodedata.normalize("NFC", value) != value
                or any(ord(character) < 32 for character in value)):
            raise ReferenceCreateError("VALIDATION_FAILED")
        return value

    @staticmethod
    def _validate_qualified(request: ReferenceSourceRequest,
                            qualified: QualifiedReferenceSources) -> None:
        if (type(qualified) is not QualifiedReferenceSources
                or qualified.scope != request.scope
                or qualified.project_id != request.project_id
                or type(qualified.content_fingerprint) is not bytes
                or len(qualified.content_fingerprint) != 32
                or tuple(item.document_version_id for item in qualified.document_versions)
                != request.document_version_ids
                or tuple(item.evidence_id for item in qualified.evidence)
                != request.evidence_ids
                or (request.scope == "GLOBAL" and (
                    type(qualified.deidentification_confirmation_id) is not uuid.UUID
                    or qualified.deidentification_confirmation_id.int == 0))
                or (request.scope == "PROJECT"
                    and qualified.deidentification_confirmation_id is not None)):
            raise ReferenceCreateError()

    @staticmethod
    def _matches(view: ReferenceInitialView | None, actor: uuid.UUID, name: str,
                 qualified: QualifiedReferenceSources, content: bytes) -> bool:
        return (type(view) is ReferenceInitialView
                and type(view.reference_solution_id) is uuid.UUID
                and view.reference_solution_id.int != 0
                and type(view.reference_version_id) is uuid.UUID
                and view.reference_version_id.int != 0
                and view.scope == qualified.scope and view.project_id == qualified.project_id
                and view.name == name and view.created_by == actor
                and view.source_fingerprint == qualified.content_fingerprint
                and view.content_fingerprint == content
                and view.deidentification_confirmation_id
                == qualified.deidentification_confirmation_id
                and view.eligibility_state == "REFERENCE_ONLY"
                and view.version_state == "DRAFT" and view.etag == '"v0"'
                and type(view.created_at) is datetime and view.created_at.tzinfo is not None)
