"""Authorize project candidate discovery before invoking internal GLOBAL scan."""

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

from .global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec, GlobalReferenceCandidateCursorError,
)
from .list_global_reference_candidates import (
    GlobalReferenceCandidate, GlobalReferenceCandidateCatalog,
    GlobalReferenceCandidatePage,
)


class GlobalReferenceCandidateReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GlobalReferenceCandidateReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GlobalReferenceCandidateReadPage:
    items: tuple[GlobalReferenceCandidate, ...]
    next_cursor: str | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class GlobalReferenceCandidateReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 catalog: GlobalReferenceCandidateCatalog,
                 cursor: GlobalReferenceCandidateCursorCodec,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                catalog, cursor)):
            raise ValueError("GLOBAL candidate read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._catalog, self._cursor = authorization, catalog, cursor
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: GlobalReferenceCandidateReadQuery, *,
             page_size: int = 20, cursor: str | None = None
             ) -> GlobalReferenceCandidateReadPage:
        if (type(query) is not GlobalReferenceCandidateReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not self._id(query.trace_id) or not self._id(query.project_id)
                or type(page_size) is not int or not 1 <= page_size <= 100
                or (cursor is not None and type(cursor) is not str)):
            raise GlobalReferenceCandidateReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise GlobalReferenceCandidateReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not self._id(actor):
                    raise GlobalReferenceCandidateReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_GLOBAL_REFERENCE_CANDIDATE_LIST")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation
                        != "SOL_GLOBAL_REFERENCE_CANDIDATE_LIST"):
                    raise GlobalReferenceCandidateReadError()
                after = (self._cursor.decode(
                    cursor, session_token=query.session_token,
                    project_id=query.project_id, page_size=page_size)
                    if cursor is not None else None)
                page = self._catalog.scan(
                    tx, trace_id=query.trace_id, project_id=query.project_id,
                    after_reference_solution_id=after, limit=page_size)
                if type(page) is not GlobalReferenceCandidatePage:
                    raise GlobalReferenceCandidateReadError()
                next_cursor = (self._cursor.encode(
                    session_token=query.session_token, project_id=query.project_id,
                    page_size=page_size,
                    after_root_id=page.next_after_reference_solution_id)
                    if page.has_more else None)
                return GlobalReferenceCandidateReadPage(
                    page.items, next_cursor, page.has_more)
        except GlobalReferenceCandidateReadError:
            raise
        except GlobalReferenceCandidateCursorError:
            raise GlobalReferenceCandidateReadError("REQUEST_MALFORMED") from None
        except ProjectAuthorizationError as error:
            raise GlobalReferenceCandidateReadError(error.code) from None
        except RuntimeLicenseError:
            raise GlobalReferenceCandidateReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalReferenceCandidateReadError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
