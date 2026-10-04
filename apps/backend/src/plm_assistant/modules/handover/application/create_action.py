"""Authorized human creation of one Handover ActionItem."""

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

from .create_version import HandoverVersionCreateService


_ACTIONS = frozenset({
    "PROVIDE_INFO", "CONFIRM_DECISION", "RESOLVE_CONFLICT",
    "MITIGATE_RISK", "DEFINE_SCOPE", "OTHER",
})
_PRIORITIES = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
_OPERATION = "V1_HND_ACTION_CREATE"


class HandoverActionCreateError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateHandoverAction:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    source_analysis_version_ref: uuid.UUID | None
    source_item_id: uuid.UUID | None
    human_source_reason: str | None
    action_type: str
    title: str
    requested_input_spec: dict[str, object]
    owner_ref: uuid.UUID
    due_at: datetime
    priority: str
    created_reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverActionSource:
    project_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    analysis_item_id: uuid.UUID
    version_state: str
    item_state: str


@dataclass(frozen=True, slots=True)
class HandoverActionInitialView:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    source_kind: str
    source_analysis_version_ref: uuid.UUID | None
    source_item_id: uuid.UUID | None
    human_source_reason: str | None
    action_type: str
    title: str
    requested_input_spec: dict[str, object]
    owner_ref: uuid.UUID
    due_at: datetime
    priority: str
    created_by: uuid.UUID
    created_reason: str
    created_at: datetime
    initial_event_id: uuid.UUID
    action_state: str = "OPEN"
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        ids = (self.action_item_id, self.project_id, self.owner_ref,
               self.created_by, self.initial_event_id)
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
                or self.source_kind not in ("ANALYSIS_ITEM", "HUMAN")
                or self.action_state != "OPEN" or self.etag != '"v0"'
                or any(type(value) is not datetime or value.tzinfo is None
                       for value in (self.due_at, self.created_at))):
            raise ValueError("invalid initial Handover Action view")


class HandoverActionAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class HandoverActionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class HandoverActionAssigneePort(Protocol):
    def is_current_member(self, transaction: object, *, project_id: uuid.UUID,
                          user_id: uuid.UUID) -> bool: ...


class HandoverActionRepositoryPort(Protocol):
    def lock_source(self, transaction: object, *, project_id: uuid.UUID,
                    handover_analysis_version_id: uuid.UUID,
                    analysis_item_id: uuid.UUID) -> HandoverActionSource | None: ...
    def create(self, transaction: object, *, action_item_id: uuid.UUID,
               initial_event_id: uuid.UUID, command: CreateHandoverAction,
               actor_id: uuid.UUID, source_kind: str,
               occurred_at: datetime) -> None: ...
    def initial_view(self, transaction: object, *, action_item_id: uuid.UUID,
                     project_id: uuid.UUID,
                     actor_id: uuid.UUID) -> HandoverActionInitialView | None: ...


class HandoverActionReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class HandoverActionCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: HandoverActionAccessPort,
        license_guard: HandoverActionLicensePort,
        authorization: ProjectAuthorizationService,
        assignees: HandoverActionAssigneePort,
        repository: HandoverActionRepositoryPort,
        receipts: HandoverActionReceiptPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        dependencies = (
            unit_of_work, access, license_guard, authorization, assignees,
            repository, receipts, audit,
        )
        if any(value is None for value in dependencies):
            raise ValueError("Handover Action dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._assignees = authorization, assignees
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateHandoverAction) -> HandoverActionInitialView:
        self._validate(command)
        source_kind = ("ANALYSIS_ITEM"
                       if command.source_analysis_version_ref is not None else "HUMAN")
        payload = self._payload(command, source_kind)
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint(payload)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._now()
                if command.due_at.astimezone(timezone.utc) <= now:
                    raise HandoverActionCreateError("VALIDATION_FAILED")
                actor_id = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now,
                )
                if type(actor_id) is not uuid.UUID or actor_id.int == 0:
                    raise HandoverActionCreateError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor_id, project_id=command.project_id,
                    operation="HND_ACTION_CREATE",
                )
                if (authorized.user_id != actor_id
                        or authorized.project_id != command.project_id
                        or authorized.operation != "HND_ACTION_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
                    raise HandoverActionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise HandoverActionCreateError()
                    view = self._repository.initial_view(
                        tx, action_item_id=replay.ref_id,
                        project_id=command.project_id, actor_id=actor_id,
                    )
                    if not self._matches(view, command, source_kind):
                        raise HandoverActionCreateError()
                    return view
                if not self._assignees.is_current_member(
                    tx, project_id=command.project_id, user_id=command.owner_ref,
                ):
                    raise HandoverActionCreateError("RESOURCE_NOT_FOUND")
                if source_kind == "ANALYSIS_ITEM":
                    source = self._repository.lock_source(
                        tx, project_id=command.project_id,
                        handover_analysis_version_id=command.source_analysis_version_ref,
                        analysis_item_id=command.source_item_id,
                    )
                    if (type(source) is not HandoverActionSource
                            or source.project_id != command.project_id
                            or source.handover_analysis_version_id
                               != command.source_analysis_version_ref
                            or source.analysis_item_id != command.source_item_id
                            or (source.version_state, source.item_state) not in (
                                ("DRAFT", "CANDIDATE"),
                                ("APPROVED", "CONFIRMED"),
                            )):
                        raise HandoverActionCreateError("RESOURCE_NOT_FOUND")
                action_id = uuid.UUID(new_uuid7())
                event_id = uuid.UUID(new_uuid7())
                self._repository.create(
                    tx, action_item_id=action_id, initial_event_id=event_id,
                    command=command, actor_id=actor_id,
                    source_kind=source_kind, occurred_at=now,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor_id, original_actor_id=None,
                    actor_hint_digest=None, action="HND_ACTION_CREATED",
                    outcome="SUCCESS", target_owner_module="handover",
                    target_object_type="HND-03", target_object_id=action_id,
                    before_state=None, after_state="OPEN",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, action_id, 201),
                )
                view = self._repository.initial_view(
                    tx, action_item_id=action_id,
                    project_id=command.project_id, actor_id=actor_id,
                )
                if not self._matches(view, command, source_kind):
                    raise HandoverActionCreateError()
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except HandoverActionCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverActionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverActionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverActionCreateError(error.code) from None
        except Exception:
            raise HandoverActionCreateError() from None

    @staticmethod
    def _validate(command: CreateHandoverAction) -> None:
        if type(command) is not CreateHandoverAction:
            raise HandoverActionCreateError("VALIDATION_FAILED")
        def text(value: object, maximum: int) -> bool:
            return (type(value) is str and 1 <= len(value) <= maximum
                    and value == value.strip())
        item_source = (type(command.source_analysis_version_ref) is uuid.UUID
                       and command.source_analysis_version_ref.int != 0
                       and type(command.source_item_id) is uuid.UUID
                       and command.source_item_id.int != 0
                       and command.human_source_reason is None)
        human_source = (command.source_analysis_version_ref is None
                        and command.source_item_id is None
                        and text(command.human_source_reason, 2000))
        fields = (command.requested_input_spec.get("fields")
                  if type(command.requested_input_spec) is dict else None)
        if (type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID
                or command.project_id.int == 0
                or not (item_source or human_source)
                or command.action_type not in _ACTIONS
                or not text(command.title, 255)
                or type(command.requested_input_spec) is not dict
                or set(command.requested_input_spec) != {"fields"}
                or not isinstance(fields, list) or not 1 <= len(fields) <= 32
                or any(not HandoverVersionCreateService._valid_input_field(value)
                       for value in fields)
                or type(command.owner_ref) is not uuid.UUID
                or command.owner_ref.int == 0
                or type(command.due_at) is not datetime
                or command.due_at.tzinfo is None
                or command.due_at.utcoffset() is None
                or command.priority not in _PRIORITIES
                or not text(command.created_reason, 2000)):
            raise HandoverActionCreateError("VALIDATION_FAILED")

    @staticmethod
    def _payload(command: CreateHandoverAction, source_kind: str) -> dict[str, object]:
        return {
            "project_id": str(command.project_id),
            "source_kind": source_kind,
            "source_analysis_version_ref": (
                str(command.source_analysis_version_ref)
                if command.source_analysis_version_ref else None
            ),
            "source_item_id": str(command.source_item_id) if command.source_item_id else None,
            "human_source_reason": command.human_source_reason,
            "action_type": command.action_type,
            "title": command.title,
            "requested_input_spec": command.requested_input_spec,
            "owner_ref": str(command.owner_ref),
            "due_at": command.due_at.astimezone(timezone.utc).isoformat(),
            "priority": command.priority,
            "created_reason": command.created_reason,
        }

    @staticmethod
    def _matches(view: HandoverActionInitialView | None,
                 command: CreateHandoverAction, source_kind: str) -> bool:
        return (type(view) is HandoverActionInitialView
                and view.project_id == command.project_id
                and view.source_kind == source_kind
                and view.source_analysis_version_ref
                   == command.source_analysis_version_ref
                and view.source_item_id == command.source_item_id
                and view.human_source_reason == command.human_source_reason
                and view.action_type == command.action_type
                and view.title == command.title
                and view.requested_input_spec == command.requested_input_spec
                and view.owner_ref == command.owner_ref
                and view.due_at == command.due_at.astimezone(timezone.utc)
                and view.priority == command.priority
                and view.created_reason == command.created_reason)

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverActionCreateError()
        return now.astimezone(timezone.utc)
