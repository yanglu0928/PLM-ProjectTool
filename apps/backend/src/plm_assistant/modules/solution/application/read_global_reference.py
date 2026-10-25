"""Authorized GLOBAL Reference identity and fixed-source read-only owner."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

from .read_reference import ReferenceDocumentRefView


class GlobalReferenceReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GlobalReferenceReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GlobalReferenceCurrentView:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    name: str
    eligibility_state: str
    eligibility_reason: str | None
    version_no: int
    version_state: str
    source_project_class: str
    deidentification_class: str
    applicability: dict[str, object] = field(repr=False)
    document_refs: tuple[ReferenceDocumentRefView, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_fingerprint: bytes = field(repr=False)
    content_fingerprint: bytes = field(repr=False)
    deidentification_confirmation_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    version_created_by: uuid.UUID
    version_created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class GlobalReferenceSummaryView:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    name: str
    eligibility_state: str
    version_no: int
    version_state: str
    created_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class GlobalReferenceListPage:
    items: tuple[GlobalReferenceSummaryView, ...]
    next_after_reference_solution_id: uuid.UUID | None
    has_more: bool


class AdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get_current(self, transaction: object, *, reference_solution_id: uuid.UUID,
                    ) -> GlobalReferenceCurrentView | None: ...

    def list_current(self, transaction: object, *,
                     after_reference_solution_id: uuid.UUID | None,
                     limit: int) -> GlobalReferenceListPage: ...


class GlobalReferenceReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], admins: AdminPort,
                 license_guard: LicensePort, repository: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, admins, license_guard, repository)):
            raise ValueError("GLOBAL Reference read dependencies required")
        self._uow, self._admins, self._guard = unit_of_work, admins, license_guard
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_current(self, query: GlobalReferenceReadQuery,
                    reference_solution_id: uuid.UUID) -> GlobalReferenceCurrentView:
        self._validate_query(query)
        if not self._id(reference_solution_id):
            raise GlobalReferenceReadError("RESOURCE_NOT_FOUND")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._admin(tx, query)
                view = self._repository.get_current(
                    tx, reference_solution_id=reference_solution_id)
                if view is None:
                    raise GlobalReferenceReadError("RESOURCE_NOT_FOUND")
                self._validate_view(view, reference_solution_id)
                return view
        except GlobalReferenceReadError:
            raise
        except RuntimeLicenseError:
            raise GlobalReferenceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalReferenceReadError() from None

    def list_current(self, query: GlobalReferenceReadQuery, *,
                     after_reference_solution_id: uuid.UUID | None = None,
                     limit: int = 50) -> GlobalReferenceListPage:
        self._validate_query(query)
        if ((after_reference_solution_id is not None
             and not self._id(after_reference_solution_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise GlobalReferenceReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                self._admin(tx, query)
                page = self._repository.list_current(
                    tx, after_reference_solution_id=after_reference_solution_id,
                    limit=limit)
                self._validate_page(page, after_reference_solution_id, limit)
                return page
        except GlobalReferenceReadError:
            raise
        except RuntimeLicenseError:
            raise GlobalReferenceReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalReferenceReadError() from None

    def _admin(self, tx: object, query: GlobalReferenceReadQuery) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise GlobalReferenceReadError()
        actor = self._admins.authorized_admin(
            tx, session_token=query.session_token,
            now=now.astimezone(timezone.utc))
        if not self._id(actor):
            raise GlobalReferenceReadError("RESOURCE_NOT_FOUND")
        return actor

    @classmethod
    def _validate_query(cls, query: GlobalReferenceReadQuery) -> None:
        if (type(query) is not GlobalReferenceReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._id(query.trace_id)):
            raise GlobalReferenceReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_view(cls, view: GlobalReferenceCurrentView | None,
                       identity: uuid.UUID) -> None:
        if (type(view) is not GlobalReferenceCurrentView
                or view.reference_solution_id != identity
                or not cls._id(view.reference_version_id)
                or not cls._id(view.deidentification_confirmation_id)
                or type(view.name) is not str or not view.name
                or view.eligibility_state not in (
                    "REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED")
                or (view.eligibility_reason is not None
                    and type(view.eligibility_reason) is not str)
                or type(view.version_no) is not int or view.version_no < 1
                or view.version_state != "DRAFT"
                or type(view.source_project_class) is not str
                or type(view.deidentification_class) is not str
                or type(view.applicability) is not dict
                or type(view.document_refs) is not tuple
                or not 1 <= len(view.document_refs) <= 100
                or any(type(ref) is not ReferenceDocumentRefView
                       or not cls._id(ref.document_id)
                       or not cls._id(ref.document_version_id)
                       for ref in view.document_refs)
                or len({ref.document_version_id for ref in view.document_refs})
                != len(view.document_refs)
                or type(view.evidence_ids) is not tuple
                or len(view.evidence_ids) > 500
                or any(not cls._id(item) for item in view.evidence_ids)
                or len(set(view.evidence_ids)) != len(view.evidence_ids)
                or type(view.source_fingerprint) is not bytes
                or len(view.source_fingerprint) != 32
                or type(view.content_fingerprint) is not bytes
                or len(view.content_fingerprint) != 32
                or not cls._id(view.created_by)
                or not cls._id(view.version_created_by)
                or not cls._time(view.created_at)
                or not cls._time(view.version_created_at)
                or not cls._etag(view.etag)):
            raise GlobalReferenceReadError()

    @classmethod
    def _validate_page(cls, page: GlobalReferenceListPage, after: uuid.UUID | None,
                       limit: int) -> None:
        if (type(page) is not GlobalReferenceListPage
                or type(page.items) is not tuple
                or len(page.items) > limit
                or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_reference_solution_id
                    != page.items[-1].reference_solution_id))
                or (not page.has_more
                    and page.next_after_reference_solution_id is not None)):
            raise GlobalReferenceReadError()
        previous = after
        for item in page.items:
            if (type(item) is not GlobalReferenceSummaryView
                    or not cls._id(item.reference_solution_id)
                    or previous is not None
                    and item.reference_solution_id.int <= previous.int
                    or not cls._id(item.reference_version_id)
                    or type(item.name) is not str or not item.name
                    or item.eligibility_state not in (
                        "REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED")
                    or type(item.version_no) is not int or item.version_no < 1
                    or item.version_state != "DRAFT"
                    or not cls._time(item.created_at)
                    or not cls._etag(item.etag)):
                raise GlobalReferenceReadError()
            previous = item.reference_solution_id

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0

    @staticmethod
    def _time(value: object) -> bool:
        return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None

    @staticmethod
    def _etag(value: object) -> bool:
        return type(value) is str and re.fullmatch(
            r'"v(0|[1-9][0-9]*)"', value, flags=re.ASCII) is not None
