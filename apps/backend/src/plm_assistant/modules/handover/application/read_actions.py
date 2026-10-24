"""Current authorized Handover Action list and detail projections."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class HandoverActionReadError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HandoverActionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class HandoverActionSummaryView:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    source_kind: str
    action_type: str
    title: str
    owner_ref: uuid.UUID
    due_at: datetime
    priority: str
    action_state: str
    submitted_at: datetime | None
    verified_at: datetime | None
    closed_at: datetime | None
    resolution_trace_ref: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class HandoverActionResponseView:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverActionEvidenceView:
    evidence_id: uuid.UUID
    purpose: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverActionCurrentEventView:
    action_state_event_id: uuid.UUID
    sequence_no: int
    from_state: str | None
    to_state: str
    actor_id: uuid.UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class HandoverActionDetailView:
    summary: HandoverActionSummaryView
    source_analysis_version_ref: uuid.UUID | None
    source_item_id: uuid.UUID | None
    human_source_reason: str | None
    requested_input_spec: dict[str, object]
    responses: tuple[HandoverActionResponseView, ...]
    evidence: tuple[HandoverActionEvidenceView, ...]
    created_by: uuid.UUID
    created_reason: str
    created_at: datetime
    verified_by: uuid.UUID | None
    current_event: HandoverActionCurrentEventView


@dataclass(frozen=True, slots=True)
class HandoverActionPage:
    items: tuple[HandoverActionSummaryView, ...]
    next_updated_at: datetime | None
    next_action_item_id: uuid.UUID | None
    has_more: bool


class HandoverActionReadRepositoryPort(Protocol):
    def list_page(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None, after_action_item_id: uuid.UUID | None,
        limit: int,
    ) -> tuple[HandoverActionSummaryView, ...]: ...
    def get(self, transaction: object, *, project_id: uuid.UUID,
            action_item_id: uuid.UUID) -> HandoverActionDetailView | None: ...


class HandoverActionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: HandoverActionReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Handover Action read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_page(
        self, query: HandoverActionReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_action_item_id: uuid.UUID | None = None,
    ) -> HandoverActionPage:
        self._validate_query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (after_updated_at is None) != (after_action_item_id is None)
                or after_updated_at is not None and (
                    type(after_updated_at) is not datetime
                    or after_updated_at.tzinfo is None
                    or after_updated_at.utcoffset() is None
                    or type(after_action_item_id) is not uuid.UUID
                    or after_action_item_id.int == 0)):
            raise HandoverActionReadError("VALIDATION_FAILED")
        return self._run(query, "HND_ACTION_LIST", lambda tx:
            self._page(tx, query.project_id, page_size,
                       after_updated_at, after_action_item_id))

    def get(self, query: HandoverActionReadQuery,
            action_item_id: uuid.UUID) -> HandoverActionDetailView:
        self._validate_query(query)
        if type(action_item_id) is not uuid.UUID or action_item_id.int == 0:
            raise HandoverActionReadError("RESOURCE_NOT_FOUND")
        def read(tx: object) -> HandoverActionDetailView:
            item = self._repository.get(
                tx, project_id=query.project_id, action_item_id=action_item_id,
            )
            if type(item) is not HandoverActionDetailView:
                raise HandoverActionReadError("RESOURCE_NOT_FOUND")
            return item
        return self._run(query, "HND_ACTION_GET", read)

    def _run(self, query: HandoverActionReadQuery, operation: str,
             read: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise HandoverActionReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise HandoverActionReadError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                return read(tx)
        except HandoverActionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverActionReadError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverActionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise HandoverActionReadError() from None

    def _page(self, tx: object, project_id: uuid.UUID, page_size: int,
              after_updated_at: datetime | None,
              after_action_item_id: uuid.UUID | None) -> HandoverActionPage:
        rows = self._repository.list_page(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_action_item_id=after_action_item_id, limit=page_size + 1,
        )
        if (type(rows) is not tuple or len(rows) > page_size + 1
                or any(type(item) is not HandoverActionSummaryView for item in rows)):
            raise HandoverActionReadError()
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return HandoverActionPage(
            items, tail.updated_at if tail else None,
            tail.action_item_id if tail else None, more,
        )

    @staticmethod
    def _validate_query(query: HandoverActionReadQuery) -> None:
        if (type(query) is not HandoverActionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID
                or query.project_id.int == 0):
            raise HandoverActionReadError("VALIDATION_FAILED")
