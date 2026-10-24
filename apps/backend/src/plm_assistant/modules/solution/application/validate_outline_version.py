"""Authorized, audited first-observation OutlineVersion validation command."""

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

from .outline_version_history import OutlineVersionHistoryView
from .outline_version_validation_contract import (
    AUDIT_ACTION, OPERATION, OutlineVersionValidationFacts,
    OutlineVersionValidationReport, OutlineVersionValidationSnapshot,
    ValidateOutlineVersion, audit_reason_for_facts,
    build_outline_version_validation_report, facts_from_audit_reason,
)
from .read_outline import OutlineCurrentView


class OutlineVersionValidationError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineVersionValidationAudit:
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


class OutlinePort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID) -> OutlineCurrentView | None: ...


class VersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            outline_id: uuid.UUID,
            version_id: uuid.UUID) -> OutlineVersionHistoryView | None: ...


class CurrentPort(Protocol):
    def facts(self, transaction: object, *, command: ValidateOutlineVersion,
              version: OutlineVersionHistoryView) -> OutlineVersionValidationFacts: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class AuditSourcePort(Protocol):
    def get(self, transaction: object, *, audit_event_id: uuid.UUID,
            actor_id: uuid.UUID, project_id: uuid.UUID,
            outline_id: uuid.UUID,
            version_id: uuid.UUID) -> OutlineVersionValidationAudit | None: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


class OutlineVersionValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 outlines: OutlinePort, versions: VersionPort,
                 current: CurrentPort, receipts: ReceiptPort,
                 audit: AuditService, audit_source: AuditSourcePort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(port is None for port in (
                unit_of_work, access, license_guard, authorization,
                outlines, versions, current, receipts, audit, audit_source)):
            raise ValueError("OutlineVersion validation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._outlines, self._versions = (
            authorization, outlines, versions)
        self._current, self._receipts, self._audit = current, receipts, audit
        self._audit_source = audit_source
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate(self, command: ValidateOutlineVersion) -> OutlineVersionValidationReport:
        if type(command) is not ValidateOutlineVersion:
            raise OutlineVersionValidationError("VALIDATION_FAILED")
        try:
            command.__post_init__()
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise OutlineVersionValidationError()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token,
                    now=now.astimezone(timezone.utc),
                )
                if not _id(actor):
                    raise OutlineVersionValidationError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_OUTLINE_VERSION_VALIDATE",
                )
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SOL_OUTLINE_VERSION_VALIDATE"):
                    raise OutlineVersionValidationError("RESOURCE_NOT_FOUND")
                outline = self._outlines.get_current(
                    tx, project_id=command.project_id,
                    outline_id=command.solution_outline_id,
                )
                if (type(outline) is not OutlineCurrentView
                        or outline.project_id != command.project_id
                        or outline.solution_outline_id != command.solution_outline_id
                        or outline.outline_state != "ACTIVE"):
                    raise OutlineVersionValidationError("RESOURCE_NOT_FOUND")
                scope = command.scope(actor)
                previous = self._receipts.reserve(
                    tx, scope=scope,
                    request_fingerprint=command.request_fingerprint(),
                )
                version = self._versions.get(
                    tx, project_id=command.project_id,
                    outline_id=command.solution_outline_id,
                    version_id=command.solution_outline_version_id,
                )
                if (type(version) is not OutlineVersionHistoryView
                        or version.project_id != command.project_id
                        or version.solution_outline_id != command.solution_outline_id
                        or version.solution_outline_version_id
                           != command.solution_outline_version_id):
                    raise OutlineVersionValidationError("RESOURCE_NOT_FOUND")
                fixed = OutlineVersionValidationSnapshot(
                    version.project_id, version.solution_outline_id,
                    version.solution_outline_version_id, version.version_no,
                    version.version_state, version.content_fingerprint,
                    len(version.section_ids), len(version.requirement_refs),
                    len(version.reference_refs),
                )
                if previous is not None:
                    if previous.ref_type != OPERATION or previous.status_code != 200:
                        raise OutlineVersionValidationError()
                    observation = self._audit_source.get(
                        tx, audit_event_id=previous.ref_id, actor_id=actor,
                        project_id=command.project_id,
                        outline_id=command.solution_outline_id,
                        version_id=command.solution_outline_version_id,
                    )
                    if type(observation) is not OutlineVersionValidationAudit:
                        raise OutlineVersionValidationError()
                    facts = facts_from_audit_reason(observation.reason_code)
                    return build_outline_version_validation_report(
                        replace(command, trace_id=observation.trace_id),
                        replace(fixed, version_state=observation.before_state),
                        facts, audit_event_id=observation.audit_event_id,
                        observed_at=observation.observed_at,
                    )
                facts = self._current.facts(
                    tx, command=command, version=version,
                )
                if type(facts) is not OutlineVersionValidationFacts:
                    raise OutlineVersionValidationError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action=AUDIT_ACTION,
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-02",
                    target_object_id=command.solution_outline_id,
                    target_version_id=command.solution_outline_version_id,
                    reason_code=audit_reason_for_facts(facts),
                    before_state=version.version_state,
                    after_state=version.version_state,
                ))
                if not _id(audit_id):
                    raise OutlineVersionValidationError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    OPERATION, audit_id, 200,
                ))
                observation = self._audit_source.get(
                    tx, audit_event_id=audit_id, actor_id=actor,
                    project_id=command.project_id,
                    outline_id=command.solution_outline_id,
                    version_id=command.solution_outline_version_id,
                )
                if (type(observation) is not OutlineVersionValidationAudit
                        or observation.trace_id != command.trace_id
                        or observation.reason_code != audit_reason_for_facts(facts)
                        or observation.before_state != version.version_state):
                    raise OutlineVersionValidationError()
                report = build_outline_version_validation_report(
                    command, fixed, facts, audit_event_id=audit_id,
                    observed_at=observation.observed_at,
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return report
        except OutlineVersionValidationError:
            raise
        except ProjectAuthorizationError as error:
            raise OutlineVersionValidationError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineVersionValidationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise OutlineVersionValidationError(error.code) from None
        except Exception:
            raise OutlineVersionValidationError() from None
