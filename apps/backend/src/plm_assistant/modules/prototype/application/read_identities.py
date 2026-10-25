"""Authorized PrototypePackage and Prototype identity reads."""

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


class PrototypeIdentityReadError(RuntimeError):
    def __init__(self, code: str = "PROTOTYPE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PrototypeIdentityReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PrototypePackageSummary:
    prototype_package_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    package_state: str
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class PrototypePackageView:
    summary: PrototypePackageSummary
    prototype_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class PrototypeSummary:
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prototype_state: str
    current_approved_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class PrototypePackagePage:
    items: tuple[PrototypePackageSummary, ...]
    next_updated_at: datetime | None
    next_prototype_package_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class PrototypePage:
    items: tuple[PrototypeSummary, ...]
    next_updated_at: datetime | None
    next_prototype_id: uuid.UUID | None
    has_more: bool


class PrototypeIdentityReadRepositoryPort(Protocol):
    def list_packages(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_prototype_package_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypePackageSummary, ...]: ...
    def get_package(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_package_id: uuid.UUID,
    ) -> PrototypePackageView | None: ...
    def list_prototypes(
        self, transaction: object, *, project_id: uuid.UUID,
        after_updated_at: datetime | None,
        after_prototype_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypeSummary, ...]: ...
    def get_prototype(
        self, transaction: object, *, project_id: uuid.UUID,
        prototype_id: uuid.UUID,
    ) -> PrototypeSummary | None: ...


class PrototypeIdentityReadService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: PrototypeIdentityReadRepositoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Prototype identity read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_packages(
        self, query: PrototypeIdentityReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_prototype_package_id: uuid.UUID | None = None,
    ) -> PrototypePackagePage:
        self._validate_query(query)
        self._validate_position(
            page_size, after_updated_at, after_prototype_package_id,
        )
        return self._run(query, "PRT_PACKAGE_LIST", lambda tx: self._package_page(
            tx, query.project_id, page_size, after_updated_at,
            after_prototype_package_id,
        ))

    def get_package(
        self, query: PrototypeIdentityReadQuery,
        prototype_package_id: uuid.UUID,
    ) -> PrototypePackageView:
        self._validate_query(query)
        self._identity(prototype_package_id)

        def read(tx: object) -> PrototypePackageView:
            view = self._repository.get_package(
                tx, project_id=query.project_id,
                prototype_package_id=prototype_package_id,
            )
            if type(view) is not PrototypePackageView:
                raise PrototypeIdentityReadError("RESOURCE_NOT_FOUND")
            if (type(view.prototype_ids) is not tuple
                    or tuple(sorted(view.prototype_ids, key=lambda value: value.bytes))
                    != view.prototype_ids
                    or len(set(view.prototype_ids)) != len(view.prototype_ids)
                    or any(not self._valid_id(value)
                           for value in view.prototype_ids)):
                raise PrototypeIdentityReadError()
            return view

        return self._run(query, "PRT_PACKAGE_GET", read)

    def list_prototypes(
        self, query: PrototypeIdentityReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_prototype_id: uuid.UUID | None = None,
    ) -> PrototypePage:
        self._validate_query(query)
        self._validate_position(page_size, after_updated_at, after_prototype_id)
        return self._run(query, "PRT_LIST", lambda tx: self._prototype_page(
            tx, query.project_id, page_size, after_updated_at,
            after_prototype_id,
        ))

    def get_prototype(
        self, query: PrototypeIdentityReadQuery, prototype_id: uuid.UUID,
    ) -> PrototypeSummary:
        self._validate_query(query)
        self._identity(prototype_id)

        def read(tx: object) -> PrototypeSummary:
            view = self._repository.get_prototype(
                tx, project_id=query.project_id, prototype_id=prototype_id,
            )
            if type(view) is not PrototypeSummary:
                raise PrototypeIdentityReadError("RESOURCE_NOT_FOUND")
            return view

        return self._run(query, "PRT_GET", read)

    def _run(self, query, operation, read):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise PrototypeIdentityReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if not self._valid_id(actor):
                    raise PrototypeIdentityReadError("AUTH_ACCESS_DENIED")
                proof = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                if (proof.user_id != actor or proof.project_id != query.project_id
                        or proof.operation != operation):
                    raise PrototypeIdentityReadError("RESOURCE_NOT_FOUND")
                return read(tx)
        except PrototypeIdentityReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeIdentityReadError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeIdentityReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PrototypeIdentityReadError() from None

    def _package_page(self, tx, project_id, page_size, after_updated_at, after_id):
        rows = self._repository.list_packages(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_prototype_package_id=after_id, limit=page_size + 1,
        )
        self._rows(rows, PrototypePackageSummary, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return PrototypePackagePage(
            items, tail.updated_at if tail else None,
            tail.prototype_package_id if tail else None, more,
        )

    def _prototype_page(self, tx, project_id, page_size, after_updated_at, after_id):
        rows = self._repository.list_prototypes(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_prototype_id=after_id, limit=page_size + 1,
        )
        self._rows(rows, PrototypeSummary, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return PrototypePage(
            items, tail.updated_at if tail else None,
            tail.prototype_id if tail else None, more,
        )

    @staticmethod
    def _rows(rows, row_type, maximum):
        if (type(rows) is not tuple or len(rows) > maximum
                or any(type(row) is not row_type for row in rows)):
            raise PrototypeIdentityReadError()

    @classmethod
    def _validate_query(cls, query):
        if (type(query) is not PrototypeIdentityReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._valid_id(query.trace_id)
                or not cls._valid_id(query.project_id)):
            raise PrototypeIdentityReadError("VALIDATION_FAILED")

    @classmethod
    def _identity(cls, value):
        if not cls._valid_id(value):
            raise PrototypeIdentityReadError("RESOURCE_NOT_FOUND")

    @classmethod
    def _validate_position(cls, page_size, updated_at, identity):
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (updated_at is None) != (identity is None)
                or updated_at is not None and (
                    type(updated_at) is not datetime
                    or updated_at.tzinfo is None
                    or updated_at.utcoffset() is None
                    or not cls._valid_id(identity))):
            raise PrototypeIdentityReadError("VALIDATION_FAILED")

    @staticmethod
    def _valid_id(value):
        return type(value) is uuid.UUID and value.int != 0
