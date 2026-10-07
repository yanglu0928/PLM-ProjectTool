"""Authorized RequirementRelation create and project-scoped list."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


RELATION_TYPES = frozenset({
    "DEPENDS_ON", "PARENT_OF", "RELATED_TO", "DUPLICATES", "CONFLICTS_WITH",
})
SYMMETRIC_TYPES = frozenset({"DUPLICATES", "CONFLICTS_WITH"})
_OPERATION = "V1_REQ_RELATION_CREATE"
_RESULT_TYPE = "V1_REQ_RELATION"


class RequirementRelationError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_RELATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RequirementVersionRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CreateRequirementRelation:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    source: RequirementVersionRef
    target: RequirementVersionRef
    relation_type: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementRelationQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RequirementRelationView:
    requirement_relation_id: uuid.UUID
    project_id: uuid.UUID
    source: RequirementVersionRef
    target: RequirementVersionRef
    relation_type: str
    relation_state: str
    lock_version: int
    created_by: uuid.UUID
    created_at: datetime
    superseded_by_ref: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class RequirementRelationPage:
    items: tuple[RequirementRelationView, ...]
    next_relation_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class StoredRequirementRelation:
    requirement_relation_id: uuid.UUID
    inserted: bool


class RequirementRelationRepositoryPort(Protocol):
    def endpoints_exist(self, transaction: object, *, project_id: uuid.UUID,
                        source: RequirementVersionRef,
                        target: RequirementVersionRef) -> bool: ...
    def assert_acyclic(self, transaction: object, *, project_id: uuid.UUID,
                       source_version_id: uuid.UUID, target_version_id: uuid.UUID,
                       relation_type: str) -> None: ...
    def create_active(self, transaction: object, *, project_id: uuid.UUID,
                      source: RequirementVersionRef, target: RequirementVersionRef,
                      relation_type: str, actor_id: uuid.UUID) -> StoredRequirementRelation: ...
    def exists(self, transaction: object, *, project_id: uuid.UUID,
               relation_id: uuid.UUID) -> bool: ...
    def get(self, transaction: object, *, project_id: uuid.UUID,
            relation_id: uuid.UUID) -> RequirementRelationView | None: ...
    def list_relations(self, transaction: object, *, project_id: uuid.UUID,
                       after_relation_id: uuid.UUID | None,
                       limit: int) -> tuple[RequirementRelationView, ...]: ...


class RequirementRelationService:
    def __init__(self, *, unit_of_work: Callable[[], object], write_access: object,
                 read_access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: RequirementRelationRepositoryPort, receipts: object,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, write_access, read_access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("RequirementRelation dependencies required")
        self._uow, self._write_access = unit_of_work, write_access
        self._read_access, self._guard = read_access, license_guard
        self._authorization, self._repo = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateRequirementRelation) -> RequirementRelationView:
        self._validate_create(command)
        source, target = self._canonical(
            command.source, command.target, command.relation_type)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "source": self._ref_payload(source),
                "target": self._ref_payload(target),
                "relation_type": command.relation_type,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(
                    self._write_access, tx, command.session_token,
                    command.csrf_token)
                self._authorize(tx, actor, command.project_id, "REQ_RELATION_CREATE")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != _RESULT_TYPE or replay.status_code != 201
                            or not self._repo.exists(
                                tx, project_id=command.project_id,
                                relation_id=replay.ref_id)):
                        raise RequirementRelationError()
                    return self._get(tx, command.project_id, replay.ref_id)
                if not self._repo.endpoints_exist(
                        tx, project_id=command.project_id,
                        source=source, target=target):
                    raise RequirementRelationError("RESOURCE_NOT_FOUND")
                self._repo.assert_acyclic(
                    tx, project_id=command.project_id,
                    source_version_id=source.requirement_version_id,
                    target_version_id=target.requirement_version_id,
                    relation_type=command.relation_type,
                )
                stored = self._repo.create_active(
                    tx, project_id=command.project_id, source=source,
                    target=target, relation_type=command.relation_type,
                    actor_id=actor,
                )
                if (type(stored) is not StoredRequirementRelation
                        or type(stored.requirement_relation_id) is not uuid.UUID
                        or stored.requirement_relation_id.int == 0
                        or type(stored.inserted) is not bool):
                    raise RequirementRelationError()
                if stored.inserted:
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="PROJECT",
                        target_project_id=command.project_id, actor_type="USER",
                        actor_id=actor, original_actor_id=None,
                        actor_hint_digest=None, action="REQUIREMENT_RELATION_CREATED",
                        outcome="SUCCESS", target_owner_module="requirement",
                        target_object_type="REQ-04",
                        target_object_id=stored.requirement_relation_id,
                        after_state="ACTIVE",
                    ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(
                        _RESULT_TYPE, stored.requirement_relation_id, 201))
                view = self._get(
                    tx, command.project_id, stored.requirement_relation_id)
                tx.commit()
                return view
        except RequirementRelationError:
            raise
        except IdempotencyError as error:
            raise RequirementRelationError(error.code) from None
        except ProjectAuthorizationError as error:
            raise RequirementRelationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementRelationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementRelationError() from None

    def list(self, query: RequirementRelationQuery, *, page_size: int,
             after_relation_id: uuid.UUID | None = None) -> RequirementRelationPage:
        self._validate_query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or after_relation_id is not None and not self._id(after_relation_id)):
            raise RequirementRelationError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                actor = self._actor(
                    self._read_access, tx, query.session_token, None)
                self._authorize(tx, actor, query.project_id, "REQ_RELATION_LIST")
                rows = self._repo.list_relations(
                    tx, project_id=query.project_id,
                    after_relation_id=after_relation_id, limit=page_size + 1)
                if (type(rows) is not tuple or len(rows) > page_size + 1
                        or any(type(row) is not RequirementRelationView for row in rows)):
                    raise RequirementRelationError()
                items, more = rows[:page_size], len(rows) > page_size
                return RequirementRelationPage(
                    items, items[-1].requirement_relation_id if more else None, more)
        except RequirementRelationError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementRelationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementRelationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementRelationError() from None

    def _get(self, tx, project_id, relation_id):
        found = self._repo.get(
            tx, project_id=project_id, relation_id=relation_id)
        if type(found) is not RequirementRelationView:
            raise RequirementRelationError()
        return found

    def _actor(self, access, tx, token, csrf):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementRelationError()
        kwargs = {"session_token": token, "now": now.astimezone(timezone.utc)}
        if csrf is not None:
            kwargs.update(csrf_token=csrf)
        actor = access.authenticated_user(tx, **kwargs)
        if not self._id(actor):
            raise RequirementRelationError("AUTH_ACCESS_DENIED")
        return actor

    def _authorize(self, tx, actor, project_id, operation):
        proof = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id, operation=operation)
        if (proof.user_id != actor or proof.project_id != project_id
                or proof.operation != operation):
            raise RequirementRelationError("RESOURCE_NOT_FOUND")

    @classmethod
    def _validate_create(cls, command):
        if (type(command) is not CreateRequirementRelation
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or not cls._id(command.trace_id) or not cls._id(command.project_id)
                or type(command.source) is not RequirementVersionRef
                or type(command.target) is not RequirementVersionRef
                or not all(cls._id(value) for value in (
                    command.source.requirement_id,
                    command.source.requirement_version_id,
                    command.target.requirement_id,
                    command.target.requirement_version_id))
                or command.source.requirement_version_id
                == command.target.requirement_version_id
                or command.relation_type not in RELATION_TYPES):
            raise RequirementRelationError("VALIDATION_FAILED")

    @classmethod
    def _validate_query(cls, query):
        if (type(query) is not RequirementRelationQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not cls._id(query.trace_id) or not cls._id(query.project_id)):
            raise RequirementRelationError("VALIDATION_FAILED")

    @staticmethod
    def _canonical(source, target, relation_type):
        if (relation_type in SYMMETRIC_TYPES
                and (source.requirement_id.bytes,
                     source.requirement_version_id.bytes)
                > (target.requirement_id.bytes,
                   target.requirement_version_id.bytes)):
            return target, source
        return source, target

    @staticmethod
    def _ref_payload(ref):
        return {"requirement_id": str(ref.requirement_id),
                "requirement_version_id": str(ref.requirement_version_id)}

    @staticmethod
    def _id(value):
        return type(value) is uuid.UUID and value.int != 0
