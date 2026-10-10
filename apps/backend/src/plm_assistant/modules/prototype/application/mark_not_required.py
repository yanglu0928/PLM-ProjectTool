"""Authorized atomic Prototype NOT_REQUIRED scope decision."""

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


class PrototypeScopeDecisionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MarkPrototypeNotRequired:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    expected_version: int
    affected_requirement_version_refs: tuple[uuid.UUID, ...]
    reason: str
    impact: str
    review_id: uuid.UUID | None
    review_round_id: uuid.UUID | None
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrototypeScopeDecisionView:
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prototype_state: str
    scope_decision_id: uuid.UUID
    reason: str
    impact: str
    confirmed_by: uuid.UUID
    review_id: uuid.UUID | None
    review_round_id: uuid.UUID | None
    affected_requirement_version_refs: tuple[uuid.UUID, ...]
    decided_at: datetime
    etag: str

    def __post_init__(self) -> None:
        valid_etag = (
            type(self.etag) is str and self.etag.startswith('"v')
            and self.etag.endswith('"') and self.etag[2:-1].isdigit()
        )
        refs = self.affected_requirement_version_refs
        if (
            any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.prototype_id, self.project_id, self.scope_decision_id,
                self.confirmed_by,
            ))
            or type(self.name) is not str or not self.name
            or self.prototype_state != "NOT_REQUIRED"
            or type(self.reason) is not str or not self.reason
            or type(self.impact) is not str or not self.impact
            or type(refs) is not tuple or not refs
            or tuple(sorted(refs, key=str)) != refs or len(set(refs)) != len(refs)
            or any(type(item) is not uuid.UUID or item.int == 0 for item in refs)
            or (self.review_id is None) != (self.review_round_id is None)
            or self.review_id is not None and (
                type(self.review_id) is not uuid.UUID or self.review_id.int == 0
                or type(self.review_round_id) is not uuid.UUID
                or self.review_round_id.int == 0
            )
            or type(self.decided_at) is not datetime or self.decided_at.tzinfo is None
            or self.decided_at.utcoffset() is None or not valid_etag
        ):
            raise ValueError("invalid Prototype scope decision view")


class AccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes, csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def decide(
        self, transaction: object, *, result_id: uuid.UUID,
        scope_decision_id: uuid.UUID, project_id: uuid.UUID,
        prototype_id: uuid.UUID, expected_version: int, actor_id: uuid.UUID,
        reason: str, impact: str, decision_fingerprint: bytes,
        requirement_version_refs: tuple[uuid.UUID, ...],
        review_id: uuid.UUID | None, review_round_id: uuid.UUID | None,
    ) -> PrototypeScopeDecisionView: ...

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
        project_id: uuid.UUID, prototype_id: uuid.UUID,
    ) -> PrototypeScopeDecisionView | None: ...


class ReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class PrototypeScopeDecisionService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: AccessPort,
        license_guard: LicensePort, authorization: ProjectAuthorizationService,
        repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository, receipts, audit,
        )):
            raise ValueError("Prototype scope decision dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def mark_not_required(
        self, command: MarkPrototypeNotRequired,
    ) -> PrototypeScopeDecisionView:
        self._validate(command)
        reason, impact = self._text(command.reason), self._text(command.impact)
        refs = self._refs(command.affected_requirement_version_refs)
        review_id, review_round_id = self._review_pair(
            command.review_id, command.review_round_id,
        )
        decision_fingerprint = canonical_payload_fingerprint({
            "project_id": str(command.project_id),
            "prototype_id": str(command.prototype_id),
            "expected_version": command.expected_version,
            "decision_type": "NOT_REQUIRED",
            "reason": reason,
            "impact": impact,
            "affected_requirement_version_refs": [str(item) for item in refs],
        })
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "decision_fingerprint": decision_fingerprint.hex(),
                "review_id": None if review_id is None else str(review_id),
                "review_round_id": (
                    None if review_round_id is None else str(review_round_id)
                ),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            result_id, decision_id = uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PRT_MARK_NOT_REQUIRED",
                )
                if (
                    authorized.user_id != actor
                    or authorized.project_id != command.project_id
                    or authorized.operation != "PRT_MARK_NOT_REQUIRED"
                ):
                    raise PrototypeScopeDecisionError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation="V1_PRT_MARK_NOT_REQUIRED", key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if previous is not None:
                    if (
                        previous.ref_type != "V1_PRT_MARK_NOT_REQUIRED"
                        or previous.status_code != 200
                    ):
                        raise PrototypeScopeDecisionError("PROTOTYPE_UNAVAILABLE")
                    replay = self._repository.result(
                        tx, result_id=previous.ref_id, project_id=command.project_id,
                        prototype_id=command.prototype_id,
                    )
                    if replay is None:
                        raise PrototypeScopeDecisionError("PROTOTYPE_UNAVAILABLE")
                    return replay
                result = self._repository.decide(
                    tx, result_id=result_id, scope_decision_id=decision_id,
                    project_id=command.project_id, prototype_id=command.prototype_id,
                    expected_version=command.expected_version, actor_id=actor,
                    reason=reason, impact=impact,
                    decision_fingerprint=decision_fingerprint,
                    requirement_version_refs=refs, review_id=review_id,
                    review_round_id=review_round_id,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="PROTOTYPE_MARKED_NOT_REQUIRED", outcome="SUCCESS",
                    target_owner_module="prototype", target_object_type="PRT-02",
                    target_object_id=command.prototype_id, before_state="ACTIVE",
                    after_state="NOT_REQUIRED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(
                        "V1_PRT_MARK_NOT_REQUIRED", result_id, 200,
                    ),
                )
                tx.commit()
                return result
        except PrototypeScopeDecisionError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeScopeDecisionError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeScopeDecisionError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeScopeDecisionError(error.code) from None
        except Exception:
            raise PrototypeScopeDecisionError("PROTOTYPE_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: object) -> None:
        if (
            type(command) is not MarkPrototypeNotRequired
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
            or type(command.prototype_id) is not uuid.UUID or command.prototype_id.int == 0
            or type(command.expected_version) is not int or command.expected_version < 0
        ):
            raise PrototypeScopeDecisionError("VALIDATION_FAILED")

    @staticmethod
    def _text(value: object) -> str:
        if type(value) is not str:
            raise PrototypeScopeDecisionError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(result) <= 2000 or any(
            unicodedata.category(char)[0] == "C" for char in result
        ):
            raise PrototypeScopeDecisionError("VALIDATION_FAILED")
        return result

    @staticmethod
    def _refs(values: object) -> tuple[uuid.UUID, ...]:
        if (
            type(values) is not tuple or not 1 <= len(values) <= 200
            or any(type(item) is not uuid.UUID or item.int == 0 for item in values)
            or len(set(values)) != len(values)
        ):
            raise PrototypeScopeDecisionError("VALIDATION_FAILED")
        return tuple(sorted(values, key=str))

    @staticmethod
    def _review_pair(
        review_id: object, review_round_id: object,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        if review_id is None and review_round_id is None:
            return None, None
        if (
            type(review_id) is not uuid.UUID or review_id.int == 0
            or type(review_round_id) is not uuid.UUID or review_round_id.int == 0
        ):
            raise PrototypeScopeDecisionError("VALIDATION_FAILED")
        return review_id, review_round_id

    def _actor(self, tx: object, command: MarkPrototypeNotRequired) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeScopeDecisionError("PROTOTYPE_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeScopeDecisionError("AUTH_ACCESS_DENIED")
        return actor
