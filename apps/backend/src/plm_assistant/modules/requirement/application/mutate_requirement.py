"""Authorized Requirement identity mutations."""

from __future__ import annotations

import re
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

_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
_STATES = frozenset({"ACTIVE", "DEFERRED", "REJECTED", "ARCHIVED"})
_OPERATIONS = {
    "PATCH": ("V1_REQ_PATCH", "REQ_PATCH", "REQUIREMENT_PATCHED"),
    "DEFER": ("V1_REQ_DEFER", "REQ_DEFER", "REQUIREMENT_DEFERRED"),
    "REJECT": ("V1_REQ_REJECT", "REQ_REJECT", "REQUIREMENT_REJECTED"),
    "ARCHIVE": ("V1_REQ_ARCHIVE", "REQ_ARCHIVE", "REQUIREMENT_ARCHIVED"),
}


class RequirementMutationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchRequirementIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    expected_version: int
    requirement_code: str


@dataclass(frozen=True, slots=True)
class DecideRequirementIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    expected_version: int
    reason: str
    impact: str
    evidence_ids: tuple[uuid.UUID, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ArchiveRequirementIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    expected_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementIdentityView:
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    requirement_code: str
    requirement_state: str
    decision_ref: uuid.UUID | None
    reason: str | None
    impact: str | None
    evidence_refs: tuple[uuid.UUID, ...]
    etag: str

    def __post_init__(self) -> None:
        decision = self.requirement_state in {"DEFERRED", "REJECTED"}
        valid_etag = (type(self.etag) is str and self.etag.startswith('"v')
                      and self.etag.endswith('"') and self.etag[2:-1].isdigit())
        if (type(self.requirement_id) is not uuid.UUID or self.requirement_id.int == 0
                or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
                or type(self.requirement_code) is not str
                or _CODE.fullmatch(self.requirement_code) is None
                or self.requirement_state not in _STATES
                or type(self.evidence_refs) is not tuple
                or tuple(sorted(self.evidence_refs, key=str)) != self.evidence_refs
                or len(set(self.evidence_refs)) != len(self.evidence_refs)
                or any(type(item) is not uuid.UUID or item.int == 0 for item in self.evidence_refs)
                or not valid_etag
                or (decision and (type(self.decision_ref) is not uuid.UUID
                                  or self.decision_ref.int == 0 or not self.reason
                                  or not self.impact or not self.evidence_refs))
                or (not decision and (self.decision_ref is not None or self.reason is not None
                                      or self.impact is not None or self.evidence_refs))):
            raise ValueError("invalid Requirement identity view")


class RequirementMutationRepositoryPort(Protocol):
    def mutate(self, transaction: object, *, result_id: uuid.UUID,
               decision_id: uuid.UUID | None, operation: str, project_id: uuid.UUID,
               requirement_id: uuid.UUID, expected_version: int, actor_id: uuid.UUID,
               requirement_code: str | None, reason: str | None, impact: str | None,
               evidence_ids: tuple[uuid.UUID, ...]) -> RequirementIdentityView: ...
    def result(self, transaction: object, *, result_id: uuid.UUID, project_id: uuid.UUID,
               requirement_id: uuid.UUID, operation: str) -> RequirementIdentityView | None: ...


class RequirementMutationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access, license_guard,
                 authorization: ProjectAuthorizationService,
                 repository: RequirementMutationRepositoryPort, receipts,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard, authorization,
                                         repository, receipts, audit)):
            raise ValueError("Requirement mutation dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchRequirementIdentity) -> RequirementIdentityView:
        self._common(command, PatchRequirementIdentity)
        return self._execute_patch(command, self._code(command.requirement_code))

    def defer(self, command: DecideRequirementIdentity) -> RequirementIdentityView:
        reason, impact, evidence = self._decision(command)
        return self._execute(command, "DEFER", None, reason, impact, evidence)

    def reject(self, command: DecideRequirementIdentity) -> RequirementIdentityView:
        reason, impact, evidence = self._decision(command)
        return self._execute(command, "REJECT", None, reason, impact, evidence)

    def archive(self, command: ArchiveRequirementIdentity) -> RequirementIdentityView:
        self._common(command, ArchiveRequirementIdentity)
        return self._execute(command, "ARCHIVE", None, None, None, ())

    def _execute_patch(
        self, command: PatchRequirementIdentity, code: str,
    ) -> RequirementIdentityView:
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            result_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="REQ_PATCH")
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "REQ_PATCH"):
                    raise RequirementMutationError("RESOURCE_NOT_FOUND")
                result = self._repository.mutate(
                    tx, result_id=result_id, decision_id=None, operation="PATCH",
                    project_id=command.project_id,
                    requirement_id=command.requirement_id,
                    expected_version=command.expected_version, actor_id=actor,
                    requirement_code=code, reason=None, impact=None,
                    evidence_ids=())
                self._append_audit(tx, command, actor, result, "PATCH")
                tx.commit()
                return result
        except RequirementMutationError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementMutationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementMutationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementMutationError("REQUIREMENT_UNAVAILABLE") from None

    def _execute(self, command, operation: str, code: str | None, reason: str | None,
                 impact: str | None, evidence: tuple[uuid.UUID, ...]) -> RequirementIdentityView:
        receipt_operation, auth_operation, _ = _OPERATIONS[operation]
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "requirement_id": str(command.requirement_id),
                "expected_version": command.expected_version, "requirement_code": code,
                "reason": reason, "impact": impact,
                "evidence_ids": [str(item) for item in evidence],
            })
            self._guard.require_valid(trace_id=command.trace_id)
            result_id, decision_id = uuid.UUID(new_uuid7()), None
            if operation in {"DEFER", "REJECT"}:
                decision_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id, operation=auth_operation)
                if authorized.user_id != actor or authorized.project_id != command.project_id:
                    raise RequirementMutationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=receipt_operation, key=command.idempotency_key)
                previous = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
                if previous is not None:
                    if previous.ref_type != receipt_operation or previous.status_code != 200:
                        raise RequirementMutationError("REQUIREMENT_UNAVAILABLE")
                    replay = self._repository.result(
                        tx, result_id=previous.ref_id, project_id=command.project_id,
                        requirement_id=command.requirement_id, operation=operation)
                    if replay is None:
                        raise RequirementMutationError("REQUIREMENT_UNAVAILABLE")
                    return replay
                result = self._repository.mutate(
                    tx, result_id=result_id, decision_id=decision_id, operation=operation,
                    project_id=command.project_id, requirement_id=command.requirement_id,
                    expected_version=command.expected_version, actor_id=actor,
                    requirement_code=code, reason=reason, impact=impact, evidence_ids=evidence)
                self._append_audit(tx, command, actor, result, operation)
                self._receipts.complete(tx, scope=scope,
                    result=IdempotencyResult(receipt_operation, result_id, 200))
                tx.commit()
                return result
        except RequirementMutationError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementMutationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementMutationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise RequirementMutationError(error.code) from None
        except Exception:
            raise RequirementMutationError("REQUIREMENT_UNAVAILABLE") from None

    def _append_audit(
        self, tx: object,
        command: PatchRequirementIdentity | DecideRequirementIdentity
        | ArchiveRequirementIdentity,
        actor: uuid.UUID, result: RequirementIdentityView, operation: str,
    ) -> None:
        action = _OPERATIONS[operation][2]
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",
            target_project_id=command.project_id, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None, action=action,
            outcome="SUCCESS", target_owner_module="requirement",
            target_object_type="REQ-02", target_object_id=command.requirement_id,
            before_state=None, after_state=result.requirement_state))

    @staticmethod
    def _common(command: object, expected: type) -> None:
        if (type(command) is not expected
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.requirement_id) is not uuid.UUID or command.requirement_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise RequirementMutationError("VALIDATION_FAILED")

    @staticmethod
    def _text(value: object) -> str:
        if type(value) is not str:
            raise RequirementMutationError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(result) <= 2000 or any(unicodedata.category(c)[0] == "C" for c in result):
            raise RequirementMutationError("VALIDATION_FAILED")
        return result

    @staticmethod
    def _code(value: object) -> str:
        if type(value) is not str:
            raise RequirementMutationError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if _CODE.fullmatch(result) is None:
            raise RequirementMutationError("VALIDATION_FAILED")
        return result

    def _decision(self, command: DecideRequirementIdentity):
        self._common(command, DecideRequirementIdentity)
        evidence = command.evidence_ids
        if (type(evidence) is not tuple or not 1 <= len(evidence) <= 100
                or any(type(item) is not uuid.UUID or item.int == 0 for item in evidence)
                or len(set(evidence)) != len(evidence)):
            raise RequirementMutationError("VALIDATION_FAILED")
        return self._text(command.reason), self._text(command.impact), tuple(sorted(evidence, key=str))

    def _actor(self, tx: object, command) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementMutationError("REQUIREMENT_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise RequirementMutationError("AUTH_ACCESS_DENIED")
        return actor
