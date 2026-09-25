"""Current authorized Document metadata reads; no content or HTTP projection."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS, ProjectActorFacts


class DocumentReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DocumentReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class DocumentView:
    document_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_category: str
    document_subtype: str | None
    title: str
    original_display_name: str
    document_state: str
    latest_version_ref: uuid.UUID | None
    effective_version_ref: uuid.UUID | None
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class DocumentPage:
    items: tuple[DocumentView, ...]
    next_after_document_id: uuid.UUID | None
    has_more: bool


class DocumentReadSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class DocumentReadAdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class DocumentReadProjectFactsPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class DocumentReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class DocumentReadRepositoryPort(Protocol):
    def list(self, transaction: object, *, scope: str,
             project_id: uuid.UUID | None, after_document_id: uuid.UUID | None,
             limit: int) -> DocumentPage: ...
    def get(self, transaction: object, *, scope: str,
            project_id: uuid.UUID | None, document_id: uuid.UUID) -> DocumentView | None: ...


class DocumentReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 session_access: DocumentReadSessionPort,
                 admin_access: DocumentReadAdminPort,
                 project_facts: DocumentReadProjectFactsPort,
                 license_guard: DocumentReadLicensePort,
                 repository: DocumentReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, session_access, admin_access,
                                         project_facts, license_guard, repository)):
            raise ValueError("Document read dependencies are required")
        self._uow = unit_of_work
        self._session_access, self._admin_access = session_access, admin_access
        self._project_facts, self._guard, self._repository = (
            project_facts, license_guard, repository,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: DocumentReadQuery, *, after_document_id: uuid.UUID | None = None,
             limit: int = 50) -> DocumentPage:
        self._validate_query(query)
        if ((after_document_id is not None and (
                type(after_document_id) is not uuid.UUID or after_document_id.int == 0))
                or type(limit) is not int or not 1 <= limit <= 200):
            raise DocumentReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._authorize(tx, query)
                page = self._repository.list(
                    tx, scope=query.scope, project_id=query.project_id,
                    after_document_id=after_document_id, limit=limit,
                )
                if type(page) is not DocumentPage:
                    raise DocumentReadError("DOCUMENT_UNAVAILABLE")
                return page
        except DocumentReadError:
            raise
        except RuntimeLicenseError:
            raise DocumentReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise DocumentReadError("DOCUMENT_UNAVAILABLE") from None

    def get(self, query: DocumentReadQuery, document_id: uuid.UUID) -> DocumentView:
        self._validate_query(query)
        if type(document_id) is not uuid.UUID or document_id.int == 0:
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._authorize(tx, query)
                view = self._repository.get(
                    tx, scope=query.scope, project_id=query.project_id,
                    document_id=document_id,
                )
                if type(view) is not DocumentView:
                    raise DocumentReadError("RESOURCE_NOT_FOUND")
                return view
        except DocumentReadError:
            raise
        except RuntimeLicenseError:
            raise DocumentReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise DocumentReadError("DOCUMENT_UNAVAILABLE") from None

    @staticmethod
    def _validate_query(query: DocumentReadQuery) -> None:
        if (type(query) is not DocumentReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or query.project_id.int == 0)):
            raise DocumentReadError("VALIDATION_FAILED")

    def _authorize(self, tx: object, query: DocumentReadQuery) -> None:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise DocumentReadError("DOCUMENT_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        actor = self._session_access.authenticated_user(
            tx, session_token=query.session_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise DocumentReadError("AUTH_ACCESS_DENIED")
        if query.scope == "GLOBAL":
            if self._admin_access.authorized_admin(
                    tx, session_token=query.session_token, now=now) != actor:
                raise DocumentReadError("RESOURCE_NOT_FOUND")
        else:
            facts = self._project_facts.actor_facts(
                tx, user_id=actor, project_id=query.project_id,
            )
            if (type(facts) is not ProjectActorFacts or facts.project_role not in ALL_MEMBERS
                    or facts.project_state not in ("ACTIVE", "ARCHIVED")):
                raise DocumentReadError("RESOURCE_NOT_FOUND")
