"""Reference human qualification with locked current source and first-result replay."""

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
from plm_assistant.modules.solution.domain.reference_eligibility import (
    ReferenceEligibilityError, decide_reference_eligibility,
)


_OPERATION = "V1_SOL_REFERENCE_SET_ELIGIBILITY"


class ReferenceEligibilityCommandError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SetReferenceEligibility:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    reference_solution_id: uuid.UUID
    expected_lock_version: int
    requested_state: str
    reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class LockedReferenceEligibility:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    eligibility_state: str
    lock_version: int
    source_project_class: str
    deidentification_class: str
    applicability: dict[str, object] = field(repr=False)
    document_version_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_fingerprint: bytes = field(repr=False)
    deidentification_confirmation_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ReferenceEligibilityResult:
    eligibility_event_id: uuid.UUID
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    eligibility_state: str
    eligibility_reason: str
    result_lock_version: int

    @property
    def etag(self) -> str:
        return f'"v{self.result_lock_version}"'


class SourcePort(Protocol):
    def qualify(self, transaction: object,
                request: ReferenceSourceRequest) -> QualifiedReferenceSources: ...


class RepositoryPort(Protocol):
    def current(self, transaction: object, *, root_id: uuid.UUID, scope: str,
                project_id: uuid.UUID | None) -> LockedReferenceEligibility | None: ...
    def decide(self, transaction: object, *, current: LockedReferenceEligibility,
               actor_id: uuid.UUID, event_id: uuid.UUID, state: str,
               reason: str) -> ReferenceEligibilityResult: ...
    def result(self, transaction: object, *, event_id: uuid.UUID, scope: str,
               project_id: uuid.UUID | None) -> ReferenceEligibilityResult | None: ...


class ReferenceEligibilityService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 global_access: GlobalAccessPort, project_access: ProjectAccessPort,
                 project_authorization: ProjectAuthorizationService,
                 license_guard: LicensePort, sources: SourcePort,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, global_access, project_access, project_authorization,
                license_guard, sources, repository, receipts, audit)):
            raise ValueError("Reference eligibility dependencies required")
        self._uow, self._global, self._project = unit_of_work, global_access, project_access
        self._authorization, self._guard = project_authorization, license_guard
        self._sources, self._repo, self._receipts, self._audit = (
            sources, repository, receipts, audit)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def set(self, command: SetReferenceEligibility) -> ReferenceEligibilityResult:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            decide_reference_eligibility(
                current_state="REFERENCE_ONLY", requested_state=command.requested_state,
                reason=command.reason,
            )
            with self._uow() as tx:
                self._actor(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                key_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                fingerprint = canonical_payload_fingerprint({
                    "reference_solution_id": str(command.reference_solution_id),
                    "scope": command.scope,
                    "project_id": str(command.project_id) if command.project_id else None,
                    "expected_lock_version": command.expected_lock_version,
                    "requested_state": command.requested_state,
                    "reason": command.reason,
                })
                replay = self._receipts.reserve(
                    tx, scope=key_scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise ReferenceEligibilityCommandError()
                    result = self._repo.result(
                        tx, event_id=replay.ref_id, scope=command.scope,
                        project_id=command.project_id)
                    if result is None or result.reference_solution_id != command.reference_solution_id:
                        raise ReferenceEligibilityCommandError()
                    return result
                current = self._repo.current(
                    tx, root_id=command.reference_solution_id,
                    scope=command.scope, project_id=command.project_id)
                if current is None:
                    raise ReferenceEligibilityCommandError("RESOURCE_NOT_FOUND")
                if current.lock_version != command.expected_lock_version:
                    raise ReferenceEligibilityCommandError("VERSION_CONFLICT")
                decide_reference_eligibility(
                    current_state=current.eligibility_state,
                    requested_state=command.requested_state,
                    reason=command.reason)
                if command.requested_state == "ELIGIBLE":
                    request = ReferenceSourceRequest(
                        session_token=command.session_token,
                        trace_id=command.trace_id,
                        scope=command.scope, project_id=command.project_id,
                        document_version_ids=current.document_version_ids,
                        evidence_ids=current.evidence_ids,
                        source_project_class=current.source_project_class,
                        deidentification_class=current.deidentification_class,
                        applicability=current.applicability)
                    proof = self._sources.qualify(tx, request)
                    if (type(proof) is not QualifiedReferenceSources
                            or proof.scope != current.scope
                            or proof.project_id != current.project_id
                            or proof.content_fingerprint != current.source_fingerprint
                            or tuple(i.document_version_id for i in proof.document_versions)
                            != current.document_version_ids
                            or tuple(i.evidence_id for i in proof.evidence)
                            != current.evidence_ids
                            or proof.deidentification_confirmation_id
                            != current.deidentification_confirmation_id):
                        raise ReferenceEligibilityCommandError("CONFLICT_STATE")
                event_id = uuid.UUID(new_uuid7())
                result = self._repo.decide(
                    tx, current=current, actor_id=actor, event_id=event_id,
                    state=command.requested_state, reason=command.reason)
                if (result.eligibility_event_id != event_id
                        or result.reference_solution_id != current.reference_solution_id
                        or result.reference_version_id != current.reference_version_id
                        or result.eligibility_state != command.requested_state
                        or result.eligibility_reason != command.reason
                        or result.result_lock_version != current.lock_version+1):
                    raise ReferenceEligibilityCommandError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="DEPLOYMENT" if command.scope == "GLOBAL" else "PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action="SOL_REFERENCE_ELIGIBILITY_SET",
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-01",
                    target_object_id=current.reference_solution_id,
                    before_state=current.eligibility_state,
                    after_state=command.requested_state,
                ))
                self._receipts.complete(tx, scope=key_scope,
                                        result=IdempotencyResult(_OPERATION, event_id, 200))
                tx.commit()
                return result
        except ReferenceEligibilityCommandError:
            raise
        except (IdempotencyError, ProjectAuthorizationError, ReferenceEligibilityError,
                ReferenceSourceError) as error:
            raise ReferenceEligibilityCommandError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceEligibilityCommandError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReferenceEligibilityCommandError() from None

    @staticmethod
    def _validate(command: SetReferenceEligibility) -> None:
        if (type(command) is not SetReferenceEligibility
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.reference_solution_id) is not uuid.UUID
                or command.reference_solution_id.int == 0
                or command.scope not in ("PROJECT", "GLOBAL")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0)
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version < 2**63-1
                or command.requested_state not in ("ELIGIBLE", "RESTRICTED", "REVOKED")
                or type(command.reason) is not str):
            raise ReferenceEligibilityCommandError("VALIDATION_FAILED")

    def _actor(self, tx: object, command: SetReferenceEligibility) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceEligibilityCommandError()
        now = now.astimezone(timezone.utc)
        if command.scope == "GLOBAL":
            actor = self._global.authorized_admin(
                tx, session_token=command.session_token,
                csrf_token=command.csrf_token, now=now)
        else:
            actor = self._project.authenticated_user(
                tx, session_token=command.session_token,
                csrf_token=command.csrf_token, now=now)
            if type(actor) is uuid.UUID and actor.int != 0:
                auth = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_REFERENCE_SET_ELIGIBILITY")
                if (auth.user_id != actor or auth.project_id != command.project_id
                        or auth.operation != "SOL_REFERENCE_SET_ELIGIBILITY"):
                    raise ReferenceEligibilityCommandError("RESOURCE_NOT_FOUND")
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ReferenceEligibilityCommandError("AUTH_ACCESS_DENIED")
        return actor
