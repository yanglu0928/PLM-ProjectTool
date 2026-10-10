"""Authorized partial metadata update for an open Handover Action."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .create_action import HandoverActionCreateError, HandoverVersionCreateService


class HandoverActionPatchError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchHandoverAction:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    action_item_id: uuid.UUID
    expected_version: int
    title: str | None = None
    requested_input_spec: dict[str, object] | None = None
    owner_ref: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: str | None = None


@dataclass(frozen=True, slots=True)
class HandoverActionPatchView:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    requested_input_spec: dict[str, object]
    owner_ref: uuid.UUID
    due_at: datetime
    priority: str
    action_state: str
    updated_at: datetime
    etag: str


class HandoverActionPatchRepositoryPort(Protocol):
    def patch(self, transaction: object, *, command: PatchHandoverAction,
              actor_id: uuid.UUID, actor_role: str,
              occurred_at: datetime) -> tuple[HandoverActionPatchView, bool]: ...


class HandoverActionPatchService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 assignees: object, repository: HandoverActionPatchRepositoryPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        values = (unit_of_work, access, license_guard, authorization,
                  assignees, repository, audit)
        if any(value is None for value in values):
            raise ValueError("Handover Action patch dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._assignees = authorization, assignees
        self._repository, self._audit = repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchHandoverAction) -> HandoverActionPatchView:
        self._validate(command)
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._now()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now,
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise HandoverActionPatchError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="HND_ACTION_PATCH",
                )
                if command.owner_ref is not None and not self._assignees.is_current_member(
                    tx, project_id=command.project_id, user_id=command.owner_ref,
                ):
                    raise HandoverActionPatchError("RESOURCE_NOT_FOUND")
                if command.due_at is not None and command.due_at.astimezone(timezone.utc) <= now:
                    raise HandoverActionPatchError("VALIDATION_FAILED")
                view, changed = self._repository.patch(
                    tx, command=command, actor_id=actor,
                    actor_role=authorized.project_role, occurred_at=now,
                )
                if changed:
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="PROJECT",
                        target_project_id=command.project_id, actor_type="USER",
                        actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                        action="HND_ACTION_PATCHED", outcome="SUCCESS",
                        target_owner_module="handover", target_object_type="HND-03",
                        target_object_id=command.action_item_id,
                        before_state=view.action_state, after_state=view.action_state,
                    ))
                    self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except HandoverActionPatchError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverActionPatchError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverActionPatchError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise HandoverActionPatchError() from None

    @staticmethod
    def _validate(command: PatchHandoverAction) -> None:
        if type(command) is not PatchHandoverAction:
            raise HandoverActionPatchError("VALIDATION_FAILED")
        supplied = (
            command.title, command.requested_input_spec, command.owner_ref,
            command.due_at, command.priority,
        )
        fields = (command.requested_input_spec.get("fields")
                  if type(command.requested_input_spec) is dict else None)
        if (type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.action_item_id) is not uuid.UUID or command.action_item_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0
                or all(value is None for value in supplied)
                or command.title is not None and (
                    type(command.title) is not str or not 1 <= len(command.title) <= 255
                    or command.title != command.title.strip())
                or command.requested_input_spec is not None and (
                    type(command.requested_input_spec) is not dict
                    or set(command.requested_input_spec) != {"fields"}
                    or not isinstance(fields, list) or not 1 <= len(fields) <= 32
                    or any(not HandoverVersionCreateService._valid_input_field(value)
                           for value in fields))
                or command.owner_ref is not None and (
                    type(command.owner_ref) is not uuid.UUID or command.owner_ref.int == 0)
                or command.due_at is not None and (
                    type(command.due_at) is not datetime or command.due_at.tzinfo is None
                    or command.due_at.utcoffset() is None)
                or command.priority is not None and command.priority not in (
                    "LOW", "MEDIUM", "HIGH", "URGENT")):
            raise HandoverActionPatchError("VALIDATION_FAILED")

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverActionPatchError()
        return now.astimezone(timezone.utc)
