"""Authorized PrototypeTemplate current-list and immutable-version reads."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .create_template import TemplateArtifactRef


class PrototypeTemplateReadError(RuntimeError):
    def __init__(self, code: str = "PROTOTYPE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProjectPrototypeTemplateReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GlobalPrototypeTemplateReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PrototypeTemplateVersionView:
    prototype_template_id: uuid.UUID
    prototype_template_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    template_state: str
    version_no: int
    version_state: str
    supersedes_version_id: uuid.UUID | None
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    content_fingerprint: str
    root_lock_version: int
    is_current: bool
    root_updated_at: datetime
    version_created_at: datetime

    @property
    def etag(self) -> str:
        return f'"v{self.root_lock_version}"'

    def __post_init__(self) -> None:
        expected_project = (
            self.scope == "GLOBAL" and self.project_id is None
            or self.scope == "PROJECT"
            and type(self.project_id) is uuid.UUID and self.project_id.int != 0
        )
        if (
            type(self.prototype_template_id) is not uuid.UUID
            or self.prototype_template_id.int == 0
            or type(self.prototype_template_version_id) is not uuid.UUID
            or self.prototype_template_version_id.int == 0
            or not expected_project or not self.name
            or self.template_state not in {"ACTIVE", "ARCHIVED", "RESTRICTED"}
            or type(self.version_no) is not int or self.version_no < 1
            or self.version_state != "PUBLISHED"
            or (self.version_no == 1) != (self.supersedes_version_id is None)
            or self.supersedes_version_id is not None and (
                type(self.supersedes_version_id) is not uuid.UUID
                or self.supersedes_version_id.int == 0
            )
            or type(self.layout_contract) is not dict
            or type(self.component_contract) is not dict
            or type(self.applicable_terminals) is not tuple
            or type(self.artifact_refs) is not tuple
            or re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint) is None
            or type(self.root_lock_version) is not int or self.root_lock_version < 0
            or type(self.is_current) is not bool
            or any(
                type(value) is not datetime
                or value.tzinfo is None or value.utcoffset() is None
                for value in (self.root_updated_at, self.version_created_at)
            )
        ):
            raise ValueError("invalid PrototypeTemplate version view")


@dataclass(frozen=True, slots=True)
class PrototypeTemplatePage:
    items: tuple[PrototypeTemplateVersionView, ...]
    next_updated_at: datetime | None
    next_template_id: uuid.UUID | None
    has_more: bool


class RepositoryPort(Protocol):
    def list_current(
        self, transaction: object, *, project_id: uuid.UUID | None,
        global_only: bool, after_updated_at: datetime | None,
        after_template_id: uuid.UUID | None, limit: int,
    ) -> tuple[PrototypeTemplateVersionView, ...]: ...

    def get_version(
        self, transaction: object, *, project_id: uuid.UUID | None,
        global_only: bool, template_id: uuid.UUID, version_id: uuid.UUID,
    ) -> PrototypeTemplateVersionView | None: ...


class PrototypeTemplateReadService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], project_access: object,
        admin_access: object, license_guard: object,
        authorization: ProjectAuthorizationService, repository: RepositoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, project_access, admin_access, license_guard,
            authorization, repository,
        )):
            raise ValueError("PrototypeTemplate read dependencies are required")
        self._uow, self._project_access = unit_of_work, project_access
        self._admin_access, self._guard = admin_access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_project(
        self, query: ProjectPrototypeTemplateReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_template_id: uuid.UUID | None = None,
    ) -> PrototypeTemplatePage:
        self._project_query(query)
        self._position(page_size, after_updated_at, after_template_id)
        return self._project_run(query, lambda tx: self._page(
            self._repository.list_current(
                tx, project_id=query.project_id, global_only=False,
                after_updated_at=after_updated_at,
                after_template_id=after_template_id, limit=page_size + 1,
            ), page_size,
        ))

    def list_global(
        self, query: GlobalPrototypeTemplateReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_template_id: uuid.UUID | None = None,
    ) -> PrototypeTemplatePage:
        self._global_query(query)
        self._position(page_size, after_updated_at, after_template_id)
        return self._global_run(query, lambda tx: self._page(
            self._repository.list_current(
                tx, project_id=None, global_only=True,
                after_updated_at=after_updated_at,
                after_template_id=after_template_id, limit=page_size + 1,
            ), page_size,
        ))

    def get_project_version(
        self, query: ProjectPrototypeTemplateReadQuery, *,
        template_id: uuid.UUID, version_id: uuid.UUID,
    ) -> PrototypeTemplateVersionView:
        self._project_query(query)
        self._identity(template_id); self._identity(version_id)
        return self._project_run(query, lambda tx: self._required(
            self._repository.get_version(
                tx, project_id=query.project_id, global_only=False,
                template_id=template_id, version_id=version_id,
            )
        ))

    def get_global_version(
        self, query: GlobalPrototypeTemplateReadQuery, *,
        template_id: uuid.UUID, version_id: uuid.UUID,
    ) -> PrototypeTemplateVersionView:
        self._global_query(query)
        self._identity(template_id); self._identity(version_id)
        return self._global_run(query, lambda tx: self._required(
            self._repository.get_version(
                tx, project_id=None, global_only=True,
                template_id=template_id, version_id=version_id,
            )
        ))

    def _project_run(self, query, read):
        def authorized(tx):
            actor = self._project_access.authenticated_user(
                tx, session_token=query.session_token, now=self._now(),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise PrototypeTemplateReadError("AUTH_ACCESS_DENIED")
            action = self._authorization.require_in_transaction(
                tx, user_id=actor, project_id=query.project_id,
                operation="PRT_TEMPLATE_LIST",
            )
            if (
                action.user_id != actor or action.project_id != query.project_id
                or action.operation != "PRT_TEMPLATE_LIST"
            ):
                raise PrototypeTemplateReadError("RESOURCE_NOT_FOUND")
            return read(tx)
        return self._run(query.trace_id, authorized)

    def _global_run(self, query, read):
        def authorized(tx):
            actor = self._admin_access.authorized_admin(
                tx, session_token=query.session_token, now=self._now(),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise PrototypeTemplateReadError("AUTH_ACCESS_DENIED")
            return read(tx)
        return self._run(query.trace_id, authorized)

    def _run(self, trace_id, action):
        try:
            self._guard.require_valid(trace_id=trace_id)
            with self._uow() as tx:
                return action(tx)
        except PrototypeTemplateReadError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeTemplateReadError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeTemplateReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PrototypeTemplateReadError() from None

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeTemplateReadError()
        return now.astimezone(timezone.utc)

    @staticmethod
    def _required(view):
        if type(view) is not PrototypeTemplateVersionView:
            raise PrototypeTemplateReadError("RESOURCE_NOT_FOUND")
        return view

    @staticmethod
    def _page(rows, size):
        if type(rows) is not tuple or len(rows) > size + 1 or any(
            type(row) is not PrototypeTemplateVersionView for row in rows
        ):
            raise PrototypeTemplateReadError()
        items, more = rows[:size], len(rows) > size
        tail = items[-1] if more else None
        return PrototypeTemplatePage(
            items, tail.root_updated_at if tail else None,
            tail.prototype_template_id if tail else None, more,
        )

    @staticmethod
    def _project_query(query):
        if (
            type(query) is not ProjectPrototypeTemplateReadQuery
            or type(query.session_token) is not bytes or len(query.session_token) != 32
            or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
            or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
        ):
            raise PrototypeTemplateReadError("VALIDATION_FAILED")

    @staticmethod
    def _global_query(query):
        if (
            type(query) is not GlobalPrototypeTemplateReadQuery
            or type(query.session_token) is not bytes or len(query.session_token) != 32
            or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
        ):
            raise PrototypeTemplateReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value):
        if type(value) is not uuid.UUID or value.int == 0:
            raise PrototypeTemplateReadError("RESOURCE_NOT_FOUND")

    @staticmethod
    def _position(size, at, identity):
        if (
            type(size) is not int or not 1 <= size <= 200
            or (at is None) != (identity is None)
            or at is not None and (
                type(at) is not datetime or at.tzinfo is None or at.utcoffset() is None
                or type(identity) is not uuid.UUID or identity.int == 0
            )
        ):
            raise PrototypeTemplateReadError("VALIDATION_FAILED")
