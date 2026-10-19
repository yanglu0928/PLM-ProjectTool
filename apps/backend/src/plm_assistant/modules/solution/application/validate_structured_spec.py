"""Authorized first-observation validation for one immutable SOL-06 version."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .evaluate_structured_spec_validation import (
    StructuredSpecCurrentFactsError, StructuredSpecCurrentFactEvaluator,
)
from .structured_spec_validation_contract import (
    AUDIT_ACTION, OPERATION, StructuredSpecValidationContractError,
    StructuredSpecValidationObservation, StructuredSpecValidationReport,
    ValidateStructuredSpec, audit_reason_for_observation,
    build_structured_spec_validation_report, observation_from_audit_reason,
)
from .structured_spec_validation_source import StructuredSpecValidationSource


_POLICY = "SOL_STRUCTURED_SPEC_VALIDATE"


class StructuredSpecValidationError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StructuredSpecValidationAudit:
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    observed_at: datetime
    reason_code: str
    before_state: str


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def lock_source(
        self, transaction: object, *, project_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> StructuredSpecValidationSource | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AuditSourcePort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            series_id: uuid.UUID,
            spec_id: uuid.UUID) -> StructuredSpecValidationAudit | None: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class StructuredSpecValidationService:
    """Authorize, observe and persist one stable SOL-06 validation result."""

    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RepositoryPort,
                 evaluator: StructuredSpecCurrentFactEvaluator,
                 receipts: ReceiptPort, audit: AuditService,
                 audit_source: AuditSourcePort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository,
                evaluator, receipts, audit, audit_source)):
            raise ValueError("StructuredSpec validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._evaluator, self._receipts = evaluator, receipts
        self._audit, self._audit_source = audit, audit_source
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(
        self, command: ValidateStructuredSpec,
    ) -> StructuredSpecValidationReport:
        if type(command) is not ValidateStructuredSpec:
            raise StructuredSpecValidationError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as transaction:
                actor = self._actor(transaction, command)
                authorized = self._authorization.require_in_transaction(
                    transaction, user_id=actor, project_id=command.project_id,
                    operation=_POLICY)
                if (authorized.user_id, authorized.project_id,
                    authorized.operation) != (actor, command.project_id, _POLICY):
                    raise StructuredSpecValidationError("RESOURCE_NOT_FOUND")
                scope = command.scope(actor)
                previous = self._receipts.reserve(
                    transaction, scope=scope,
                    request_fingerprint=command.request_fingerprint())
                source = self._repository.lock_source(
                    transaction, project_id=command.project_id,
                    spec_id=command.structured_solution_spec_id)
                if type(source) is not StructuredSpecValidationSource:
                    raise StructuredSpecValidationError("RESOURCE_NOT_FOUND")
                if previous is not None:
                    return self._replay(
                        transaction, command=command, actor=actor,
                        source=source, previous=previous)
                observation = self._evaluator.evaluate(
                    transaction, command=command, source=source)
                if type(observation) is not StructuredSpecValidationObservation:
                    raise StructuredSpecValidationError()
                reason = audit_reason_for_observation(observation)
                audit_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action=AUDIT_ACTION,
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-06",
                    target_object_id=source.snapshot.spec_series_id,
                    target_version_id=command.structured_solution_spec_id,
                    reason_code=reason,
                    before_state=source.snapshot.version_state,
                    after_state=source.snapshot.version_state))
                if not _id(audit_id):
                    raise StructuredSpecValidationError()
                self._receipts.complete(
                    transaction, scope=scope,
                    result=IdempotencyResult(OPERATION, audit_id, 200))
                audit = self._audit_source.get(
                    transaction, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    series_id=source.snapshot.spec_series_id,
                    spec_id=command.structured_solution_spec_id)
                if (type(audit) is not StructuredSpecValidationAudit
                        or audit.trace_id != command.trace_id
                        or audit.reason_code != reason
                        or audit.before_state != source.snapshot.version_state):
                    raise StructuredSpecValidationError()
                report = build_structured_spec_validation_report(
                    command, source.snapshot, observation,
                    audit_event_id=audit_id, observed_at=audit.observed_at)
                self._guard.require_valid(trace_id=command.trace_id)
                transaction.commit()
                return report
        except StructuredSpecValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise StructuredSpecValidationError(error.code) from None
        except RuntimeLicenseError:
            raise StructuredSpecValidationError(
                "LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise StructuredSpecValidationError(error.code) from None
        except StructuredSpecCurrentFactsError as error:
            raise StructuredSpecValidationError(error.code) from None
        except StructuredSpecValidationContractError:
            raise StructuredSpecValidationError() from None
        except Exception:
            raise StructuredSpecValidationError() from None

    def _actor(self, transaction: object,
               command: ValidateStructuredSpec) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise StructuredSpecValidationError()
        actor = self._access.authenticated_user(
            transaction, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if not _id(actor):
            raise StructuredSpecValidationError("AUTH_ACCESS_DENIED")
        return actor

    def _replay(
        self, transaction: object, *, command: ValidateStructuredSpec,
        actor: uuid.UUID, source: StructuredSpecValidationSource,
        previous: IdempotencyResult,
    ) -> StructuredSpecValidationReport:
        if previous.ref_type != OPERATION or previous.status_code != 200:
            raise StructuredSpecValidationError()
        audit = self._audit_source.get(
            transaction, audit_event_id=previous.ref_id, actor_id=actor,
            project_id=command.project_id,
            series_id=source.snapshot.spec_series_id,
            spec_id=command.structured_solution_spec_id)
        if type(audit) is not StructuredSpecValidationAudit:
            raise StructuredSpecValidationError()
        observation = observation_from_audit_reason(audit.reason_code)
        return build_structured_spec_validation_report(
            replace(command, trace_id=audit.trace_id),
            replace(source.snapshot, version_state=audit.before_state),
            observation, audit_event_id=audit.audit_event_id,
            observed_at=audit.observed_at)
