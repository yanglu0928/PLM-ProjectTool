"""Authorized immutable PrototypeVersion reads and non-mutating validation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from .create_version import PrototypeVersionInitialView


class PrototypeVersionReadError(RuntimeError):
    def __init__(self, code: str): self.code = code; super().__init__(code)


@dataclass(frozen=True, slots=True)
class PrototypeVersionQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PrototypeVersionPage:
    items: tuple[PrototypeVersionInitialView, ...]
    next_version_no: int | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class PrototypeVersionValidationReport:
    prototype_version_id: uuid.UUID
    valid: bool
    issues: tuple[str, ...]
    checked_at: datetime
    version_state: str


class ReadRepositoryPort(Protocol):
    def list(self, transaction: object, *, project_id: uuid.UUID,
             prototype_id: uuid.UUID, before_version_no: int | None,
             limit: int) -> tuple[PrototypeVersionInitialView, ...]: ...
    def get(self, transaction: object, *, project_id: uuid.UUID,
            prototype_id: uuid.UUID,
            version_id: uuid.UUID) -> PrototypeVersionInitialView | None: ...


class PrototypeVersionReadValidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], project_access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: ReadRepositoryPort, templates: object,
                 requirements: object, documents: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None):
        values = (unit_of_work, project_access, license_guard, authorization,
                  repository, templates, requirements, documents, audit)
        if any(value is None for value in values): raise ValueError("dependencies required")
        self._uow, self._access, self._guard = unit_of_work, project_access, license_guard
        self._authorization, self._repository = authorization, repository
        self._templates, self._requirements, self._documents = templates, requirements, documents
        self._audit, self._clock = audit, clock or (lambda: datetime.now(timezone.utc))

    def list(self, query: PrototypeVersionQuery, *, page_size: int,
             before_version_no: int | None = None) -> PrototypeVersionPage:
        self._query(query)
        if type(page_size) is not int or not 1 <= page_size <= 100 or (
            before_version_no is not None and
            (type(before_version_no) is not int or before_version_no < 2)):
            raise PrototypeVersionReadError("VALIDATION_FAILED")
        def read(tx):
            self._actor(tx, query, "PRT_VERSION_LIST", csrf=False)
            rows = self._repository.list(tx, project_id=query.project_id,
                prototype_id=query.prototype_id, before_version_no=before_version_no,
                limit=page_size + 1)
            items, more = rows[:page_size], len(rows) > page_size
            return PrototypeVersionPage(items, items[-1].version_no if more else None, more)
        return self._run(query.trace_id, read)

    def get(self, query: PrototypeVersionQuery, *, version_id: uuid.UUID):
        self._query(query)
        if type(version_id) is not uuid.UUID or version_id.int == 0:
            raise PrototypeVersionReadError("VALIDATION_FAILED")
        return self._run(query.trace_id, lambda tx: self._required(
            self._actor(tx, query, "PRT_VERSION_GET", csrf=False),
            self._repository.get(tx, project_id=query.project_id,
                prototype_id=query.prototype_id, version_id=version_id)))

    def validate(self, query: PrototypeVersionQuery, *, version_id: uuid.UUID,
                 csrf_token: bytes) -> PrototypeVersionValidationReport:
        self._query(query)
        if (type(version_id) is not uuid.UUID or version_id.int == 0
            or type(csrf_token) is not bytes or len(csrf_token) != 32):
            raise PrototypeVersionReadError("VALIDATION_FAILED")
        def check(tx):
            actor = self._actor(tx, query, "PRT_VERSION_VALIDATE", csrf=True,
                                csrf_token=csrf_token)
            view = self._repository.get(tx, project_id=query.project_id,
                prototype_id=query.prototype_id, version_id=version_id)
            if view is None: raise PrototypeVersionReadError("RESOURCE_NOT_FOUND")
            issues = []
            if self._templates.prove(tx, project_id=query.project_id,
                prototype_template_id=view.template_id,
                prototype_template_version_id=view.template_version_id) is None:
                issues.append("TEMPLATE_UNAVAILABLE")
            for item in view.requirement_refs:
                if self._requirements.prove(tx, project_id=query.project_id,
                    requirement_id=item.requirement_id,
                    requirement_version_id=item.requirement_version_id) is None:
                    issues.append("REQUIREMENT_UNAVAILABLE")
            for item in view.artifact_refs:
                if item.artifact_kind != "DOCUMENT_VERSION" or \
                   self._documents.prove_for_prototype_version(
                       tx, project_id=query.project_id,
                       document_version_id=item.target_id) is None:
                    issues.append("ARTIFACT_UNAVAILABLE")
            issues = sorted(set(issues))
            now = self._now()
            report = PrototypeVersionValidationReport(
                version_id, not issues, tuple(issues), now, view.version_state)
            self._audit.append(tx, AuditEventDraft(
                trace_id=query.trace_id, event_scope="PROJECT",
                target_project_id=query.project_id, actor_type="USER", actor_id=actor,
                original_actor_id=None, actor_hint_digest=None,
                action="PROTOTYPE_VERSION_VALIDATED", outcome="SUCCESS",
                target_owner_module="prototype", target_object_type="PRT-03",
                target_object_id=version_id, before_state=view.version_state,
                after_state=view.version_state))
            tx.commit()
            return report
        return self._run(query.trace_id, check)

    def _actor(self, tx, query, operation, *, csrf, csrf_token=None):
        kwargs = {"session_token": query.session_token, "now": self._now()}
        if csrf: kwargs["csrf_token"] = csrf_token
        actor = self._access.authenticated_user(tx, **kwargs)
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeVersionReadError("AUTH_ACCESS_DENIED")
        action = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=query.project_id, operation=operation)
        if action.user_id != actor or action.project_id != query.project_id:
            raise PrototypeVersionReadError("RESOURCE_NOT_FOUND")
        return actor

    def _run(self, trace_id, action):
        try:
            self._guard.require_valid(trace_id=trace_id)
            with self._uow() as tx: return action(tx)
        except PrototypeVersionReadError: raise
        except ProjectAuthorizationError as error:
            raise PrototypeVersionReadError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeVersionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PrototypeVersionReadError("PROTOTYPE_UNAVAILABLE") from None

    def _now(self):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeVersionReadError("PROTOTYPE_UNAVAILABLE")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _query(query):
        if (type(query) is not PrototypeVersionQuery
            or type(query.session_token) is not bytes or len(query.session_token) != 32
            or any(type(x) is not uuid.UUID or x.int == 0 for x in
                   (query.trace_id, query.project_id, query.prototype_id))):
            raise PrototypeVersionReadError("VALIDATION_FAILED")

    @staticmethod
    def _required(_actor, view):
        if view is None: raise PrototypeVersionReadError("RESOURCE_NOT_FOUND")
        return view
