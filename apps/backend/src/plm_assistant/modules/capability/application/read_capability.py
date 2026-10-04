"""Authorized GLOBAL Capability projections; HTTP transport is intentionally absent."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class CapabilityReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CapabilityReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CapabilityBaselineView:
    baseline_id: uuid.UUID
    baseline_code: str
    name: str
    description: str | None
    state: str
    source_collection_ref: str
    current_approved_version_ref: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class CapabilityVersionView:
    baseline_version_id: uuid.UUID
    baseline_id: uuid.UUID
    version_no: int
    state: str
    source_collection_ref: str
    content_fingerprint: str
    declared_item_count: int
    declared_document_ref_count: int
    declared_evidence_ref_count: int
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CapabilityItemView:
    capability_item_id: uuid.UUID
    baseline_version_id: uuid.UUID
    baseline_id: uuid.UUID
    ordinal: int
    capability_code: str
    domain_name: str
    module_name: str
    feature_name: str
    name: str
    description: str
    boundary_text: str
    prerequisites: tuple[str, ...]
    interface_refs: tuple[str, ...]
    state: str
    document_version_refs: tuple[uuid.UUID, ...]
    evidence_refs: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class CapabilityBaselinePage:
    items: tuple[CapabilityBaselineView, ...]
    next_position: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class CapabilityVersionPage:
    items: tuple[CapabilityVersionView, ...]
    next_position: int | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class CapabilityItemPage:
    items: tuple[CapabilityItemView, ...]
    next_position: int | None
    has_more: bool


class CapabilitySessionAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class CapabilityCurrentUserPort(Protocol):
    def current_enabled_user(self, transaction: object, *,
                             user_id: uuid.UUID) -> CurrentUserFacts | None: ...


class CapabilityMembershipPort(Protocol):
    def has_active_membership(self, transaction: object, *, user_id: uuid.UUID) -> bool: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityReadRepositoryPort(Protocol):
    def list_baselines(self, transaction: object, *, visibility: str,
                       after_id: uuid.UUID | None, limit: int
                       ) -> tuple[CapabilityBaselineView, ...]: ...
    def get_baseline(self, transaction: object, *, visibility: str,
                     baseline_id: uuid.UUID) -> CapabilityBaselineView | None: ...
    def list_versions(self, transaction: object, *, visibility: str,
                      baseline_id: uuid.UUID, after_version_no: int | None,
                      limit: int) -> tuple[CapabilityVersionView, ...]: ...
    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView | None: ...
    def list_items(self, transaction: object, *, visibility: str,
                   baseline_id: uuid.UUID, baseline_version_id: uuid.UUID,
                   after_ordinal: int | None,
                   limit: int) -> tuple[CapabilityItemView, ...]: ...


class CapabilityReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 session_access: CapabilitySessionAccessPort,
                 current_user: CapabilityCurrentUserPort,
                 membership: CapabilityMembershipPort,
                 license_guard: LicenseGuardPort,
                 repository: CapabilityReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        dependencies = (unit_of_work, session_access, current_user, membership,
                        license_guard, repository)
        if any(value is None for value in dependencies):
            raise ValueError("Capability read dependencies are required")
        self._uow = unit_of_work
        self._session_access = session_access
        self._current_user = current_user
        self._membership = membership
        self._guard = license_guard
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_baselines(self, query: CapabilityReadQuery, *, page_size: int,
                       after_id: uuid.UUID | None = None) -> CapabilityBaselinePage:
        self._validate_query(query)
        self._validate_page(page_size, after_id, uuid.UUID)
        return self._run(query, lambda tx, visibility: self._page_baselines(
            tx, visibility, page_size, after_id,
        ))

    def get_baseline(self, query: CapabilityReadQuery,
                     baseline_id: uuid.UUID) -> CapabilityBaselineView:
        self._validate_query(query)
        self._identity(baseline_id)
        def read(tx: object, visibility: str) -> CapabilityBaselineView:
            item = self._repository.get_baseline(
                tx, visibility=visibility, baseline_id=baseline_id,
            )
            if type(item) is not CapabilityBaselineView:
                raise CapabilityReadError("RESOURCE_NOT_FOUND")
            return item
        return self._run(query, read)

    def list_versions(self, query: CapabilityReadQuery, *, baseline_id: uuid.UUID,
                      page_size: int, after_version_no: int | None = None,
                      ) -> CapabilityVersionPage:
        self._validate_query(query)
        self._identity(baseline_id)
        self._validate_page(page_size, after_version_no, int)
        return self._run(query, lambda tx, visibility: self._page_versions(
            tx, visibility, baseline_id, page_size, after_version_no,
        ))

    def get_version(self, query: CapabilityReadQuery, *, baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView:
        self._validate_query(query)
        self._identity(baseline_id)
        self._identity(baseline_version_id)
        def read(tx: object, visibility: str) -> CapabilityVersionView:
            item = self._repository.get_version(
                tx, visibility=visibility, baseline_id=baseline_id,
                baseline_version_id=baseline_version_id,
            )
            if type(item) is not CapabilityVersionView:
                raise CapabilityReadError("RESOURCE_NOT_FOUND")
            return item
        return self._run(query, read)

    def list_items(self, query: CapabilityReadQuery, *, baseline_id: uuid.UUID,
                   baseline_version_id: uuid.UUID, page_size: int,
                   after_ordinal: int | None = None) -> CapabilityItemPage:
        self._validate_query(query)
        self._identity(baseline_id)
        self._identity(baseline_version_id)
        self._validate_page(page_size, after_ordinal, int, allow_zero=True)
        return self._run(query, lambda tx, visibility: self._page_items(
            tx, visibility, baseline_id, baseline_version_id, page_size, after_ordinal,
        ))

    def _run(self, query: CapabilityReadQuery, operation: Callable[[object, str], object]):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                visibility = self._visibility(tx, query)
                return operation(tx, visibility)
        except CapabilityReadError:
            raise
        except RuntimeLicenseError:
            raise CapabilityReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise CapabilityReadError("CAPABILITY_UNAVAILABLE") from None

    def _visibility(self, tx: object, query: CapabilityReadQuery) -> str:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise CapabilityReadError("CAPABILITY_UNAVAILABLE")
        user_id = self._session_access.authenticated_user(
            tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
        )
        if type(user_id) is not uuid.UUID or user_id.int == 0:
            raise CapabilityReadError("AUTH_ACCESS_DENIED")
        facts = self._current_user.current_enabled_user(tx, user_id=user_id)
        if type(facts) is not CurrentUserFacts or facts.user_id != user_id:
            raise CapabilityReadError("AUTH_ACCESS_DENIED")
        if facts.deployment_role == "DEPLOYMENT_ADMIN":
            return "ADMIN_HISTORY"
        if facts.deployment_role != "NONE" or self._membership.has_active_membership(
            tx, user_id=user_id,
        ) is not True:
            raise CapabilityReadError("AUTH_ACCESS_DENIED")
        return "CURRENT_APPROVED"

    def _page_baselines(self, tx: object, visibility: str, page_size: int,
                        after_id: uuid.UUID | None) -> CapabilityBaselinePage:
        rows = self._repository.list_baselines(
            tx, visibility=visibility, after_id=after_id, limit=page_size + 1,
        )
        self._validate_rows(rows, CapabilityBaselineView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return CapabilityBaselinePage(items, items[-1].baseline_id if more else None, more)

    def _page_versions(self, tx: object, visibility: str, baseline_id: uuid.UUID,
                       page_size: int, after: int | None) -> CapabilityVersionPage:
        rows = self._repository.list_versions(
            tx, visibility=visibility, baseline_id=baseline_id,
            after_version_no=after, limit=page_size + 1,
        )
        self._validate_rows(rows, CapabilityVersionView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return CapabilityVersionPage(items, items[-1].version_no if more else None, more)

    def _page_items(self, tx: object, visibility: str, baseline_id: uuid.UUID,
                    version_id: uuid.UUID, page_size: int,
                    after: int | None) -> CapabilityItemPage:
        rows = self._repository.list_items(
            tx, visibility=visibility, baseline_id=baseline_id,
            baseline_version_id=version_id, after_ordinal=after,
            limit=page_size + 1,
        )
        self._validate_rows(rows, CapabilityItemView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return CapabilityItemPage(items, items[-1].ordinal if more else None, more)

    @staticmethod
    def _validate_rows(rows: object, row_type: type, maximum: int) -> None:
        if type(rows) is not tuple or len(rows) > maximum or any(
            type(item) is not row_type for item in rows
        ):
            raise CapabilityReadError("CAPABILITY_UNAVAILABLE")

    @staticmethod
    def _validate_query(query: CapabilityReadQuery) -> None:
        if (type(query) is not CapabilityReadQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0):
            raise CapabilityReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value: uuid.UUID) -> None:
        if type(value) is not uuid.UUID or value.int == 0:
            raise CapabilityReadError("RESOURCE_NOT_FOUND")

    @staticmethod
    def _validate_page(page_size: int, position: object, position_type: type,
                       *, allow_zero: bool = False) -> None:
        if type(page_size) is not int or not 1 <= page_size <= 200:
            raise CapabilityReadError("VALIDATION_FAILED")
        if position is None:
            return
        if type(position) is not position_type:
            raise CapabilityReadError("VALIDATION_FAILED")
        if position_type is uuid.UUID and position.int == 0:
            raise CapabilityReadError("VALIDATION_FAILED")
        if position_type is int and (position < 0 or (position == 0 and not allow_zero)):
            raise CapabilityReadError("VALIDATION_FAILED")
