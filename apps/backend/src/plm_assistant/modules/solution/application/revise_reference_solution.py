"""Authorized immutable Reference revision; no public route is installed here."""

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
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .create_reference_solution import GlobalAccessPort, LicensePort, ProjectAccessPort, ReceiptPort
from .reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
)


_OPERATION = "V1_SOL_REFERENCE_REVISE"


class ReferenceReviseError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviseReferenceSolution:
    sources: ReferenceSourceRequest = field(repr=False)
    csrf_token: bytes = field(repr=False)
    reference_solution_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentReference:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    version_no: int
    lock_version: int
    eligibility_state: str


@dataclass(frozen=True, slots=True)
class ReferenceRevisionView:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    version_no: int
    supersedes_version_ref: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    source_fingerprint: bytes = field(repr=False)
    created_at: datetime


class SourcePort(Protocol):
    def qualify(self, transaction: object,
                request: ReferenceSourceRequest) -> QualifiedReferenceSources: ...


class RepositoryPort(Protocol):
    def current(self, transaction: object, *, root_id: uuid.UUID, scope: str,
                project_id: uuid.UUID | None) -> CurrentReference | None: ...

    def revise(self, transaction: object, *, current: CurrentReference,
               version_id: uuid.UUID, actor_id: uuid.UUID,
               sources: ReferenceSourceRequest, qualified: QualifiedReferenceSources,
               content_fingerprint: bytes) -> ReferenceRevisionView: ...

    def result(self, transaction: object, *, version_id: uuid.UUID, scope: str,
               project_id: uuid.UUID | None) -> ReferenceRevisionView | None: ...


class ReferenceReviseService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 global_access: GlobalAccessPort, project_access: ProjectAccessPort,
                 project_authorization: ProjectAuthorizationService,
                 license_guard: LicensePort, sources: SourcePort,
                 repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, global_access, project_access, project_authorization,
                license_guard, sources, repository, receipts, audit)):
            raise ValueError("Reference revise dependencies required")
        self._uow, self._global, self._project = unit_of_work, global_access, project_access
        self._authorization, self._guard = project_authorization, license_guard
        self._sources, self._repo, self._receipts, self._audit = (
            sources, repository, receipts, audit)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revise(self, command: ReviseReferenceSolution) -> ReferenceRevisionView:
        if (type(command) is not ReviseReferenceSolution
                or type(command.sources) is not ReferenceSourceRequest
                or type(command.sources.session_token) is not bytes
                or len(command.sources.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.sources.trace_id) is not uuid.UUID
                or command.sources.trace_id.int == 0
                or type(command.reference_solution_id) is not uuid.UUID
                or command.reference_solution_id.int == 0
                or type(command.expected_lock_version) is not int
                or command.expected_lock_version < 0):
            raise ReferenceReviseError("VALIDATION_FAILED")
        request = command.sources
        try:
            validate_idempotency_key(command.idempotency_key)
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=request.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                key_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=request.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                fingerprint = canonical_payload_fingerprint({
                    "reference_solution_id": str(command.reference_solution_id),
                    "scope": request.scope,
                    "project_id": str(request.project_id) if request.project_id else None,
                    "expected_lock_version": command.expected_lock_version,
                    "documents": [str(item) for item in request.document_version_ids],
                    "evidence": [str(item) for item in request.evidence_ids],
                    "source_project_class": request.source_project_class,
                    "deidentification_class": request.deidentification_class,
                    "applicability": request.applicability,
                })
                replay = self._receipts.reserve(
                    tx, scope=key_scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise ReferenceReviseError()
                    view = self._repo.result(tx, version_id=replay.ref_id,
                                             scope=request.scope,
                                             project_id=request.project_id)
                    if view is None or view.reference_solution_id != command.reference_solution_id:
                        raise ReferenceReviseError()
                    return view
                current = self._repo.current(
                    tx, root_id=command.reference_solution_id,
                    scope=request.scope, project_id=request.project_id)
                if current is None:
                    raise ReferenceReviseError("RESOURCE_NOT_FOUND")
                if current.lock_version != command.expected_lock_version:
                    raise ReferenceReviseError("VERSION_CONFLICT")
                qualified = self._sources.qualify(tx, request)
                if (type(qualified) is not QualifiedReferenceSources
                        or qualified.scope != request.scope
                        or qualified.project_id != request.project_id
                        or type(qualified.content_fingerprint) is not bytes
                        or len(qualified.content_fingerprint) != 32
                        or tuple(i.document_version_id for i in qualified.document_versions)
                        != request.document_version_ids
                        or tuple(i.evidence_id for i in qualified.evidence) != request.evidence_ids
                        or request.scope == "GLOBAL" and (
                            type(qualified.deidentification_confirmation_id) is not uuid.UUID
                            or qualified.deidentification_confirmation_id.int == 0)
                        or request.scope == "PROJECT" and
                        qualified.deidentification_confirmation_id is not None):
                    raise ReferenceReviseError()
                content = canonical_payload_fingerprint({
                    "name": current.name, "scope": request.scope,
                    "project_id": str(request.project_id) if request.project_id else None,
                    "source_fingerprint": qualified.content_fingerprint.hex(),
                    "documents": [str(i.document_version_id) for i in qualified.document_versions],
                    "evidence": [str(i.evidence_id) for i in qualified.evidence],
                    "source_project_class": request.source_project_class,
                    "deidentification_class": request.deidentification_class,
                    "applicability": request.applicability,
                    "supersedes_version_ref": str(current.reference_version_id),
                })
                version_id = uuid.UUID(new_uuid7())
                view = self._repo.revise(
                    tx, current=current, version_id=version_id, actor_id=actor,
                    sources=request, qualified=qualified, content_fingerprint=content)
                if (view.reference_version_id != version_id
                        or view.reference_solution_id != current.reference_solution_id
                        or view.version_no != current.version_no+1
                        or view.supersedes_version_ref != current.reference_version_id
                        or view.content_fingerprint != content
                        or view.source_fingerprint != qualified.content_fingerprint):
                    raise ReferenceReviseError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id, event_scope=(
                        "DEPLOYMENT" if request.scope == "GLOBAL" else "PROJECT"),
                    target_project_id=request.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action="SOL_REFERENCE_REVISED",
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-01", target_object_id=current.reference_solution_id,
                    after_state=current.eligibility_state,
                ))
                self._receipts.complete(tx, scope=key_scope, result=IdempotencyResult(
                    _OPERATION, version_id, 201))
                tx.commit()
                return view
        except ReferenceReviseError:
            raise
        except (ProjectAuthorizationError, ReferenceSourceError, IdempotencyError) as error:
            raise ReferenceReviseError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceReviseError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReferenceReviseError() from None

    def _actor(self, tx: object, command: ReviseReferenceSolution) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceReviseError()
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
                auth = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=request.project_id,
                    operation="SOL_REFERENCE_REVISE")
                if (auth.user_id != actor or auth.project_id != request.project_id
                        or auth.operation != "SOL_REFERENCE_REVISE"):
                    raise ReferenceReviseError("RESOURCE_NOT_FOUND")
        else:
            raise ReferenceReviseError("VALIDATION_FAILED")
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ReferenceReviseError("AUTH_ACCESS_DENIED")
        return actor
