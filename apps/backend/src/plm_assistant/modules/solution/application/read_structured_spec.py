"""Authorized fixed SOL-06 history; never substitute the first CREATE receipt."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .structured_spec_input import SpecRequirementRef, SpecSectionRef


class StructuredSpecReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StructuredSpecReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class StructuredSpecHistoryView:
    structured_solution_spec_id: uuid.UUID
    spec_series_id: uuid.UUID
    project_id: uuid.UUID
    spec_type: str
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    payload_json: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[SpecRequirementRef, ...]
    section_refs: tuple[SpecSectionRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    artifact_ids: tuple[uuid.UUID, ...]
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime

    def payload(self) -> dict[str, object]:
        return json.loads(self.payload_json)


@dataclass(frozen=True, slots=True)
class StructuredSpecSummaryView:
    structured_solution_spec_id: uuid.UUID
    spec_series_id: uuid.UUID
    project_id: uuid.UUID
    spec_type: str
    version_no: int
    version_state: str
    content_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StructuredSpecListPage:
    items: tuple[StructuredSpecSummaryView, ...]
    next_before_spec_id: uuid.UUID | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            spec_id: uuid.UUID) -> StructuredSpecHistoryView | None: ...

    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      before_spec_id: uuid.UUID | None,
                      limit: int) -> StructuredSpecListPage: ...


class StructuredSpecReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 specs: RepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, specs)):
            raise ValueError("StructuredSpec read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._specs = authorization, specs
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: StructuredSpecReadQuery,
            spec_id: uuid.UUID) -> StructuredSpecHistoryView:
        if (type(query) is not StructuredSpecReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not all(_id(value) for value in (
                    query.trace_id, query.project_id, spec_id))):
            raise StructuredSpecReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise StructuredSpecReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not _id(actor):
                    raise StructuredSpecReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_STRUCTURED_SPEC_GET")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "SOL_STRUCTURED_SPEC_GET"):
                    raise StructuredSpecReadError("RESOURCE_NOT_FOUND")
                view = self._specs.get(
                    tx, project_id=query.project_id, spec_id=spec_id)
                if view is None:
                    raise StructuredSpecReadError("RESOURCE_NOT_FOUND")
                if (type(view) is not StructuredSpecHistoryView
                        or view.project_id != query.project_id
                        or view.structured_solution_spec_id != spec_id
                        or not _id(view.spec_series_id)
                        or view.spec_type not in (
                            "PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC",
                            "PERMISSION_DESIGN")
                        or type(view.version_no) is not int or view.version_no < 1
                        or view.version_state not in (
                            "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                            "SUPERSEDED", "RESTRICTED")
                        or (view.review_ref is None) != (view.review_round_ref is None)
                        or (view.supersedes_version_ref is None)
                        != (view.version_no == 1)
                        or not _id(view.created_by)
                        or type(view.created_at) is not datetime
                        or view.created_at.tzinfo is None
                        or view.created_at.utcoffset() is None
                        or any(type(digest) is not bytes or len(digest) != 32
                               for digest in (view.content_fingerprint,
                                              view.payload_fingerprint))
                        or view.artifact_ids):
                    raise StructuredSpecReadError()
                return view
        except StructuredSpecReadError:
            raise
        except ProjectAuthorizationError as error:
            raise StructuredSpecReadError(error.code) from None
        except RuntimeLicenseError:
            raise StructuredSpecReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise StructuredSpecReadError() from None

    def list_versions(self, query: StructuredSpecReadQuery, *,
                      before_spec_id: uuid.UUID | None = None,
                      limit: int = 50) -> StructuredSpecListPage:
        if (type(query) is not StructuredSpecReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not all(_id(value) for value in (
                    query.trace_id, query.project_id))
                or (before_spec_id is not None and not _id(before_spec_id))
                or type(limit) is not int or not 1 <= limit <= 100):
            raise StructuredSpecReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise StructuredSpecReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if not _id(actor):
                    raise StructuredSpecReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="SOL_STRUCTURED_SPEC_LIST")
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != "SOL_STRUCTURED_SPEC_LIST"):
                    raise StructuredSpecReadError("RESOURCE_NOT_FOUND")
                page = self._specs.list_versions(
                    tx, project_id=query.project_id,
                    before_spec_id=before_spec_id, limit=limit)
                self._validate_page(
                    page, query.project_id, before_spec_id, limit)
                return page
        except StructuredSpecReadError:
            raise
        except ProjectAuthorizationError as error:
            raise StructuredSpecReadError(error.code) from None
        except RuntimeLicenseError:
            raise StructuredSpecReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise StructuredSpecReadError() from None

    @staticmethod
    def _validate_page(page: StructuredSpecListPage, project_id: uuid.UUID,
                       before: uuid.UUID | None, limit: int) -> None:
        if (type(page) is not StructuredSpecListPage
                or type(page.items) is not tuple or len(page.items) > limit
                or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_before_spec_id
                    != page.items[-1].structured_solution_spec_id))
                or (not page.has_more and page.next_before_spec_id is not None)):
            raise StructuredSpecReadError()
        previous = before
        pairs: set[tuple[uuid.UUID, int]] = set()
        for item in page.items:
            pair = (getattr(item, "spec_series_id", None),
                    getattr(item, "version_no", None))
            if (type(item) is not StructuredSpecSummaryView
                    or not _id(item.structured_solution_spec_id)
                    or (previous is not None
                        and item.structured_solution_spec_id.int >= previous.int)
                    or not _id(item.spec_series_id)
                    or item.project_id != project_id
                    or item.spec_type not in (
                        "PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC",
                        "PERMISSION_DESIGN")
                    or type(item.version_no) is not int or item.version_no < 1
                    or item.version_state not in (
                        "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                        "SUPERSEDED", "RESTRICTED")
                    or any(type(digest) is not bytes or len(digest) != 32
                           for digest in (item.content_fingerprint,
                                          item.payload_fingerprint))
                    or (item.supersedes_version_ref is None)
                    != (item.version_no == 1)
                    or (item.review_ref is None) != (item.review_round_ref is None)
                    or not _id(item.created_by)
                    or type(item.created_at) is not datetime
                    or item.created_at.tzinfo is None
                    or item.created_at.utcoffset() is None
                    or pair in pairs):
                raise StructuredSpecReadError()
            pairs.add(pair)
            previous = item.structured_solution_spec_id


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0
