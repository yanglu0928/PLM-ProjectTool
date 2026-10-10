"""Authorized immutable SectionVersion history; refs are not current proof."""

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

from .read_section import SectionCurrentView
from .section_version_input import (
    SectionRequirementRef, SectionVersionDraftInput, SectionVersionInputError,
    validate_section_version_draft,
)


class SectionVersionReadError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SectionVersionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    solution_section_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SectionVersionHistoryView:
    solution_section_version_id: uuid.UUID
    solution_section_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    title: str
    content_document_version_ref: uuid.UUID | None
    content_artifact_ref: uuid.UUID | None
    content_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[SectionRequirementRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    assumptions: tuple[dict[str, object], ...] = field(repr=False)
    exclusions: tuple[dict[str, object], ...] = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SectionVersionPage:
    items: tuple[SectionVersionHistoryView, ...]
    next_before_version_no: int | None
    has_more: bool


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SectionPort(Protocol):
    def get_current(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID) -> SectionCurrentView | None: ...


class VersionPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            section_id: uuid.UUID,
            version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...

    def list(self, transaction: object, *, project_id: uuid.UUID,
             section_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[SectionVersionHistoryView, ...]: ...


class SectionVersionReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 sections: SectionPort, versions: VersionPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                sections, versions)):
            raise ValueError("SectionVersion read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._sections, self._versions = sections, versions
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: SectionVersionReadQuery,
            version_id: uuid.UUID) -> SectionVersionHistoryView:
        self._query(query)
        if not self._id(version_id):
            raise SectionVersionReadError("RESOURCE_NOT_FOUND")

        def read(tx: object) -> SectionVersionHistoryView:
            self._actor(tx, query, "SOL_SECTION_VERSION_GET")
            self._parent(tx, query)
            view = self._versions.get(
                tx, project_id=query.project_id,
                section_id=query.solution_section_id, version_id=version_id)
            if view is None:
                raise SectionVersionReadError("RESOURCE_NOT_FOUND")
            self._view(view, query)
            if view.solution_section_version_id != version_id:
                raise SectionVersionReadError()
            return view

        return self._run(query.trace_id, read)

    def list(self, query: SectionVersionReadQuery, *, page_size: int = 50,
             before_version_no: int | None = None) -> SectionVersionPage:
        self._query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 100
                or (before_version_no is not None and (
                    type(before_version_no) is not int
                    or before_version_no < 2))):
            raise SectionVersionReadError("VALIDATION_FAILED")

        def read(tx: object) -> SectionVersionPage:
            self._actor(tx, query, "SOL_SECTION_VERSION_LIST")
            self._parent(tx, query)
            rows = self._versions.list(
                tx, project_id=query.project_id,
                section_id=query.solution_section_id,
                before_version_no=before_version_no, limit=page_size + 1)
            if type(rows) is not tuple or len(rows) > page_size + 1:
                raise SectionVersionReadError()
            items = rows[:page_size]
            for index, item in enumerate(rows):
                self._view(item, query)
                if (before_version_no is not None
                        and item.version_no >= before_version_no):
                    raise SectionVersionReadError()
                if index > 0 and rows[index - 1].version_no <= item.version_no:
                    raise SectionVersionReadError()
            more = len(rows) > page_size
            return SectionVersionPage(
                items, items[-1].version_no if more else None, more)

        return self._run(query.trace_id, read)

    def _run(self, trace_id: uuid.UUID, action: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=trace_id)
            with self._uow() as tx:
                return action(tx)
        except SectionVersionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise SectionVersionReadError(error.code) from None
        except RuntimeLicenseError:
            raise SectionVersionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SectionVersionReadError() from None

    @staticmethod
    def _id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0

    def _query(self, query: SectionVersionReadQuery) -> None:
        if (type(query) is not SectionVersionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not all(self._id(value) for value in (
                    query.trace_id, query.project_id,
                    query.solution_section_id))):
            raise SectionVersionReadError("VALIDATION_FAILED")

    def _actor(self, tx: object, query: SectionVersionReadQuery,
               operation: str) -> None:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise SectionVersionReadError()
        actor = self._access.authenticated_user(
            tx, session_token=query.session_token,
            now=now.astimezone(timezone.utc))
        if not self._id(actor):
            raise SectionVersionReadError("AUTH_ACCESS_DENIED")
        authorized = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=query.project_id,
            operation=operation)
        if (authorized.user_id != actor
                or authorized.project_id != query.project_id
                or authorized.operation != operation):
            raise SectionVersionReadError("RESOURCE_NOT_FOUND")

    def _parent(self, tx: object, query: SectionVersionReadQuery) -> None:
        root = self._sections.get_current(
            tx, project_id=query.project_id,
            section_id=query.solution_section_id)
        if root is None:
            raise SectionVersionReadError("RESOURCE_NOT_FOUND")
        if (type(root) is not SectionCurrentView
                or root.project_id != query.project_id
                or root.solution_section_id != query.solution_section_id
                or not self._id(root.solution_outline_id)
                or root.section_state not in ("ACTIVE", "ARCHIVED")):
            raise SectionVersionReadError()

    def _view(self, value: object, query: SectionVersionReadQuery) -> None:
        if (type(value) is not SectionVersionHistoryView
                or value.project_id != query.project_id
                or value.solution_section_id != query.solution_section_id
                or not self._id(value.solution_section_version_id)
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
            raise SectionVersionReadError()
        try:
            validate_section_version_draft(SectionVersionDraftInput(
                query.project_id, query.solution_section_id,
                value.title, value.content_document_version_ref,
                value.content_artifact_ref, value.requirement_refs,
                value.evidence_ids, value.assumptions, value.exclusions))
        except SectionVersionInputError:
            raise SectionVersionReadError() from None
