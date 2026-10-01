"""Authorized Evidence metadata reads; Viewer source resolution is separate."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import ALL_MEMBERS, ProjectActorFacts


class EvidenceReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class EvidenceView:
    evidence_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    locator: dict[str, object]
    content_fingerprint: bytes = field(repr=False)
    display_label: str
    display_excerpt: str | None
    eligibility_state: str
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class EvidencePage:
    items: tuple[EvidenceView, ...]
    next_after: tuple[datetime, uuid.UUID] | None
    has_more: bool


class EvidenceSessionReadPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class EvidenceAdminReadPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class EvidenceProjectFactsPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class EvidenceLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EvidenceReadRepositoryPort(Protocol):
    def list(self, transaction: object, *, scope: str, project_id: uuid.UUID | None,
             after: tuple[datetime, uuid.UUID] | None, limit: int) -> EvidencePage: ...
    def get(self, transaction: object, *, scope: str, project_id: uuid.UUID | None,
            evidence_id: uuid.UUID) -> EvidenceView | None: ...


class EvidenceReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 session_access: EvidenceSessionReadPort,
                 admin_access: EvidenceAdminReadPort,
                 project_facts: EvidenceProjectFactsPort,
                 license_guard: EvidenceLicensePort,
                 repository: EvidenceReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, session_access, admin_access,
                                         project_facts, license_guard, repository)):
            raise ValueError("Evidence read dependencies are required")
        self._uow = unit_of_work
        self._session_access, self._admin_access = session_access, admin_access
        self._project_facts, self._guard, self._repository = (
            project_facts, license_guard, repository,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: EvidenceReadQuery, *,
             after: tuple[datetime, uuid.UUID] | None = None,
             limit: int = 50) -> EvidencePage:
        self._validate_query(query)
        if (type(limit) is not int or not 1 <= limit <= 200
                or after is not None and (
                    type(after) is not tuple or len(after) != 2
                    or type(after[0]) is not datetime or after[0].tzinfo is None
                    or after[0].utcoffset() is None
                    or type(after[1]) is not uuid.UUID or after[1].int == 0)):
            raise EvidenceReadError("VALIDATION_FAILED")
        try:
            with self._uow() as tx:
                self._guard.require_valid(trace_id=query.trace_id)
                self._authorize(tx, query)
                page = self._repository.list(
                    tx, scope=query.scope, project_id=query.project_id,
                    after=after, limit=limit,
                )
                if type(page) is not EvidencePage:
                    raise EvidenceReadError("EVIDENCE_UNAVAILABLE")
                return page
        except EvidenceReadError:
            raise
        except RuntimeLicenseError:
            raise EvidenceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise EvidenceReadError("EVIDENCE_UNAVAILABLE") from None

    def get(self, query: EvidenceReadQuery, evidence_id: uuid.UUID) -> EvidenceView:
        self._validate_query(query)
        if type(evidence_id) is not uuid.UUID or evidence_id.int == 0:
            raise EvidenceReadError("RESOURCE_NOT_FOUND")
        try:
            with self._uow() as tx:
                self._guard.require_valid(trace_id=query.trace_id)
                self._authorize(tx, query)
                view = self._repository.get(
                    tx, scope=query.scope, project_id=query.project_id,
                    evidence_id=evidence_id,
                )
                if type(view) is not EvidenceView:
                    raise EvidenceReadError("RESOURCE_NOT_FOUND")
                return view
        except EvidenceReadError:
            raise
        except RuntimeLicenseError:
            raise EvidenceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise EvidenceReadError("EVIDENCE_UNAVAILABLE") from None

    @staticmethod
    def _validate_query(query: EvidenceReadQuery) -> None:
        if (type(query) is not EvidenceReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or query.scope not in ("GLOBAL", "PROJECT")
                or query.scope == "GLOBAL" and query.project_id is not None
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or query.project_id.int == 0)):
            raise EvidenceReadError("VALIDATION_FAILED")

    def _authorize(self, tx: object, query: EvidenceReadQuery) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise EvidenceReadError("EVIDENCE_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        actor = self._session_access.authenticated_user(
            tx, session_token=query.session_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise EvidenceReadError("AUTH_ACCESS_DENIED")
        if query.scope == "GLOBAL":
            if self._admin_access.authorized_admin(
                    tx, session_token=query.session_token, now=now) != actor:
                raise EvidenceReadError("RESOURCE_NOT_FOUND")
        else:
            facts = self._project_facts.actor_facts(
                tx, user_id=actor, project_id=query.project_id,
            )
            if (type(facts) is not ProjectActorFacts
                    or facts.project_role not in ALL_MEMBERS
                    or facts.project_state not in ("ACTIVE", "ARCHIVED")):
                raise EvidenceReadError("RESOURCE_NOT_FOUND")
        return actor
