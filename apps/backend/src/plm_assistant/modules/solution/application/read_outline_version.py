"""Authorized immutable OutlineVersion GET/LIST; historical refs are not current proof."""

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

from .outline_version_history import OutlineVersionHistoryView
from .outline_version_input import (
    OutlineVersionDraftInput, OutlineVersionInputError,
    validate_outline_version_draft,
)
from .read_outline import OutlineCurrentView


class OutlineVersionReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutlineVersionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_outline_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OutlineVersionPage:
    items: tuple[OutlineVersionHistoryView, ...]
    next_before_version_no: int | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class OutlinePort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID) -> OutlineCurrentView | None: ...


class VersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            outline_id: uuid.UUID,
            version_id: uuid.UUID) -> OutlineVersionHistoryView | None: ...

    def list(self, transaction: object, *, project_id: uuid.UUID,
             outline_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[OutlineVersionHistoryView, ...]: ...


class OutlineVersionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 outlines: OutlinePort, versions: VersionPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                outlines, versions)):
            raise ValueError("OutlineVersion read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._outlines, self._versions = outlines, versions
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: OutlineVersionReadQuery,
            version_id: uuid.UUID) -> OutlineVersionHistoryView:
        self._query(query)
        if not self._id(version_id):
            raise OutlineVersionReadError("RESOURCE_NOT_FOUND")
        def read(tx: object) -> OutlineVersionHistoryView:
            self._actor(tx, query, "SOL_OUTLINE_VERSION_GET")
            self._parent(tx, query)
            view = self._versions.get(
                tx, project_id=query.project_id,
                outline_id=query.solution_outline_id, version_id=version_id)
            if view is None:
                raise OutlineVersionReadError("RESOURCE_NOT_FOUND")
            self._view(view, query)
            if view.solution_outline_version_id != version_id:
                raise OutlineVersionReadError()
            return view
        return self._run(query.trace_id, read)

    def list(self, query: OutlineVersionReadQuery, *, page_size: int = 50,
             before_version_no: int | None = None) -> OutlineVersionPage:
        self._query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 100
                or (before_version_no is not None and (
                    type(before_version_no) is not int
                    or before_version_no < 2))):
            raise OutlineVersionReadError("VALIDATION_FAILED")
        def read(tx: object) -> OutlineVersionPage:
            self._actor(tx, query, "SOL_OUTLINE_VERSION_LIST")
            self._parent(tx, query)
            rows = self._versions.list(
                tx, project_id=query.project_id,
                outline_id=query.solution_outline_id,
                before_version_no=before_version_no, limit=page_size + 1)
            if type(rows) is not tuple or len(rows) > page_size + 1:
                raise OutlineVersionReadError()
            items = rows[:page_size]
            for index, item in enumerate(rows):
                self._view(item, query)
                if (before_version_no is not None
                        and item.version_no >= before_version_no):
                    raise OutlineVersionReadError()
                if index > 0 and rows[index - 1].version_no <= item.version_no:
                    raise OutlineVersionReadError()
            more = len(rows) > page_size
            return OutlineVersionPage(
                items, items[-1].version_no if more else None, more)
        return self._run(query.trace_id, read)

    def _run(self, trace_id: uuid.UUID, action: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=trace_id)
            with self._uow() as tx:
                return action(tx)
        except OutlineVersionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise OutlineVersionReadError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineVersionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutlineVersionReadError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0

    def _query(self, query: OutlineVersionReadQuery) -> None:
        if (type(query) is not OutlineVersionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not all(self._id(value) for value in (
                    query.trace_id, query.project_id,
                    query.solution_outline_id))):
            raise OutlineVersionReadError("VALIDATION_FAILED")

    def _actor(self, tx: object, query: OutlineVersionReadQuery,
               operation: str) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise OutlineVersionReadError()
        actor = self._access.authenticated_user(
            tx, session_token=query.session_token,
            now=now.astimezone(timezone.utc))
        if not self._id(actor):
            raise OutlineVersionReadError("AUTH_ACCESS_DENIED")
        authorized = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=query.project_id,
            operation=operation)
        if (authorized.user_id != actor
                or authorized.project_id != query.project_id
                or authorized.operation != operation):
            raise OutlineVersionReadError("RESOURCE_NOT_FOUND")
        return actor

    def _parent(self, tx: object, query: OutlineVersionReadQuery) -> None:
        root = self._outlines.get_current(
            tx, project_id=query.project_id,
            outline_id=query.solution_outline_id)
        if root is None:
            raise OutlineVersionReadError("RESOURCE_NOT_FOUND")
        if (type(root) is not OutlineCurrentView
                or root.project_id != query.project_id
                or root.solution_outline_id != query.solution_outline_id
                or root.outline_state not in ("ACTIVE", "ARCHIVED")):
            raise OutlineVersionReadError()

    def _view(self, value: object, query: OutlineVersionReadQuery) -> None:
        if (type(value) is not OutlineVersionHistoryView
                or value.project_id != query.project_id
                or value.solution_outline_id != query.solution_outline_id
                or not self._id(value.solution_outline_version_id)
                or type(value.version_no) is not int or value.version_no < 1
                or value.version_state not in (
                    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")
                or type(value.content_fingerprint) is not bytes
                or len(value.content_fingerprint) != 32
                or (value.supersedes_version_ref is not None
                    and not self._id(value.supersedes_version_ref))
                or (value.review_ref is None) != (value.review_round_ref is None)
                or (value.review_ref is not None and not self._id(value.review_ref))
                or (value.review_round_ref is not None
                    and not self._id(value.review_round_ref))
                or not self._id(value.created_by)
                or type(value.created_at) is not datetime
                or value.created_at.tzinfo is None
                or value.created_at.utcoffset() is None):
            raise OutlineVersionReadError()
        try:
            validate_outline_version_draft(OutlineVersionDraftInput(
                query.project_id, query.solution_outline_id,
                value.section_ids, value.requirement_refs,
                value.reference_refs, value.missing_declarations,
                value.conflict_declarations))
        except OutlineVersionInputError:
            raise OutlineVersionReadError() from None
