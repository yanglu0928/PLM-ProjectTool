"""Authorized OPEN to IN_PROGRESS Handover Action command."""

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
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


_OPERATION = "V1_HND_ACTION_START"


class HandoverActionStartError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StartHandoverAction:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    action_item_id: uuid.UUID
    expected_version: int
    reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverActionStartView:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    action_state_event_id: uuid.UUID
    action_state: str
    occurred_at: datetime
    etag: str


class HandoverActionStartRepositoryPort(Protocol):
    def start(self, transaction: object, *, command: StartHandoverAction,
              actor_id: uuid.UUID, actor_role: str,
              occurred_at: datetime) -> HandoverActionStartView: ...
    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID, actor_role: str) -> HandoverActionStartView | None: ...


class HandoverActionStartService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: HandoverActionStartRepositoryPort, receipts: object,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        values = (unit_of_work, access, license_guard, authorization,
                  repository, receipts, audit)
        if any(value is None for value in values):
            raise ValueError("Handover Action start dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start(self, command: StartHandoverAction) -> HandoverActionStartView:
        self._validate(command)
        payload = {
            "project_id": str(command.project_id),
            "action_item_id": str(command.action_item_id),
            "expected_version": command.expected_version,
            "reason": command.reason,
        }
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint(payload)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._now()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now,
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise HandoverActionStartError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="HND_ACTION_START",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise HandoverActionStartError()
                    view = self._repository.replay(
                        tx, action_item_id=command.action_item_id,
                        project_id=command.project_id, event_id=replay.ref_id,
                        actor_id=actor, actor_role=authorized.project_role,
                    )
                    if view is None:
                        raise HandoverActionStartError()
                    return view
                view = self._repository.start(
                    tx, command=command, actor_id=actor,
                    actor_role=authorized.project_role, occurred_at=now,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="HND_ACTION_STARTED", outcome="SUCCESS",
                    target_owner_module="handover", target_object_type="HND-03",
                    target_object_id=command.action_item_id,
                    before_state="OPEN", after_state="IN_PROGRESS",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, view.action_state_event_id, 200),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except HandoverActionStartError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverActionStartError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverActionStartError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverActionStartError(error.code) from None
        except Exception:
            raise HandoverActionStartError() from None

    @staticmethod
    def _validate(command: StartHandoverAction) -> None:
        if (type(command) is not StartHandoverAction
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.action_item_id) is not uuid.UUID or command.action_item_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0
                or type(command.reason) is not str or not 1 <= len(command.reason) <= 2000
                or command.reason != command.reason.strip()):
            raise HandoverActionStartError("VALIDATION_FAILED")

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverActionStartError()
        return now.astimezone(timezone.utc)
