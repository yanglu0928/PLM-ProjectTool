"""Authorized RequirementPackage and Requirement identity reads."""

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


class RequirementIdentityReadError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RequirementIdentityReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RequirementPackageSummary:
    requirement_package_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    package_state: str
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class RequirementPackageView:
    summary: RequirementPackageSummary
    requirement_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class RequirementSummary:
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    requirement_code: str
    requirement_state: str
    current_approved_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class RequirementPackagePage:
    items: tuple[RequirementPackageSummary, ...]
    next_updated_at: datetime | None
    next_requirement_package_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class RequirementPage:
    items: tuple[RequirementSummary, ...]
    next_updated_at: datetime | None
    next_requirement_id: uuid.UUID | None
    has_more: bool


class RequirementIdentityReadRepositoryPort(Protocol):
    def list_packages(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_requirement_package_id: uuid.UUID | None, limit: int,
    ) -> tuple[RequirementPackageSummary, ...]: ...
    def get_package(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_package_id: uuid.UUID,
    ) -> RequirementPackageView | None: ...
    def list_requirements(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_requirement_id: uuid.UUID | None, limit: int,
    ) -> tuple[RequirementSummary, ...]: ...
    def get_requirement(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> RequirementSummary | None: ...


class RequirementIdentityReadService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: RequirementIdentityReadRepositoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Requirement identity read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_packages(
        self, query: RequirementIdentityReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_requirement_package_id: uuid.UUID | None = None,
    ) -> RequirementPackagePage:
        self._validate_query(query)
        self._validate_position(
            page_size, after_updated_at, after_requirement_package_id)
        return self._run(query, "REQ_PACKAGE_LIST", lambda tx: self._package_page(
            tx, query.project_id, page_size, after_updated_at,
            after_requirement_package_id))

    def get_package(
        self, query: RequirementIdentityReadQuery,
        requirement_package_id: uuid.UUID,
    ) -> RequirementPackageView:
        self._validate_query(query)
        self._identity(requirement_package_id)

        def read(tx: object) -> RequirementPackageView:
            view = self._repository.get_package(
                tx, project_id=query.project_id,
                requirement_package_id=requirement_package_id)
            if type(view) is not RequirementPackageView:
                raise RequirementIdentityReadError("RESOURCE_NOT_FOUND")
            if (type(view.requirement_ids) is not tuple
                    or tuple(sorted(view.requirement_ids, key=lambda value: value.bytes))
                    != view.requirement_ids
                    or len(set(view.requirement_ids)) != len(view.requirement_ids)
                    or any(type(value) is not uuid.UUID or value.int == 0
                           for value in view.requirement_ids)):
                raise RequirementIdentityReadError()
            return view

        return self._run(query, "REQ_PACKAGE_GET", read)

    def list_requirements(
        self, query: RequirementIdentityReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_requirement_id: uuid.UUID | None = None,
    ) -> RequirementPage:
        self._validate_query(query)
        self._validate_position(page_size, after_updated_at, after_requirement_id)
        return self._run(query, "REQ_LIST", lambda tx: self._requirement_page(
            tx, query.project_id, page_size, after_updated_at,
            after_requirement_id))

    def get_requirement(
        self, query: RequirementIdentityReadQuery, requirement_id: uuid.UUID,
    ) -> RequirementSummary:
        self._validate_query(query)
        self._identity(requirement_id)

        def read(tx: object) -> RequirementSummary:
            view = self._repository.get_requirement(
                tx, project_id=query.project_id, requirement_id=requirement_id)
            if type(view) is not RequirementSummary:
                raise RequirementIdentityReadError("RESOURCE_NOT_FOUND")
            return view

        return self._run(query, "REQ_GET", read)

    def _run(
        self, query: RequirementIdentityReadQuery, operation: str,
        read: Callable[[object], object],
    ):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise RequirementIdentityReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc))
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise RequirementIdentityReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation)
                if (authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != operation):
                    raise RequirementIdentityReadError("RESOURCE_NOT_FOUND")
                return read(tx)
        except RequirementIdentityReadError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementIdentityReadError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementIdentityReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementIdentityReadError() from None

    def _package_page(
        self, tx: object, project_id: uuid.UUID, page_size: int,
        after_updated_at: datetime | None, after_id: uuid.UUID | None,
    ) -> RequirementPackagePage:
        rows = self._repository.list_packages(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_requirement_package_id=after_id, limit=page_size + 1)
        self._rows(rows, RequirementPackageSummary, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return RequirementPackagePage(
            items, tail.updated_at if tail else None,
            tail.requirement_package_id if tail else None, more)

    def _requirement_page(
        self, tx: object, project_id: uuid.UUID, page_size: int,
        after_updated_at: datetime | None, after_id: uuid.UUID | None,
    ) -> RequirementPage:
        rows = self._repository.list_requirements(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_requirement_id=after_id, limit=page_size + 1)
        self._rows(rows, RequirementSummary, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return RequirementPage(
            items, tail.updated_at if tail else None,
            tail.requirement_id if tail else None, more)

    @staticmethod
    def _rows(rows: object, row_type: type, maximum: int) -> None:
        if (type(rows) is not tuple or len(rows) > maximum
                or any(type(row) is not row_type for row in rows)):
            raise RequirementIdentityReadError()

    @staticmethod
    def _validate_query(query: RequirementIdentityReadQuery) -> None:
        if (type(query) is not RequirementIdentityReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0):
            raise RequirementIdentityReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value: uuid.UUID | None) -> None:
        if type(value) is not uuid.UUID or value.int == 0:
            raise RequirementIdentityReadError("RESOURCE_NOT_FOUND")

    @classmethod
    def _validate_position(
        cls, page_size: int, updated_at: datetime | None,
        identity: uuid.UUID | None,
    ) -> None:
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (updated_at is None) != (identity is None)
                or updated_at is not None and (
                    type(updated_at) is not datetime
                    or updated_at.tzinfo is None
                    or updated_at.utcoffset() is None
                    or type(identity) is not uuid.UUID
                    or identity.int == 0)):
            raise RequirementIdentityReadError("VALIDATION_FAILED")
