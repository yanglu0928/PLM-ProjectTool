"""Authorized RequirementPrototypeLink creation and scoped reads."""

from __future__ import annotations

import re
import unicodedata
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


LINK_PURPOSES = frozenset({
    "ILLUSTRATES", "VALIDATES", "ACCEPTANCE_REFERENCE",
})
_OPERATION = "V1_PRT_REQUIREMENT_LINK_CREATE"
_RESULT_TYPE = "V1_PRT_REQUIREMENT_LINK"


class RequirementPrototypeLinkError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_PROTOTYPE_LINK_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class UncoveredAcceptanceCriterion:
    acceptance_criterion_ref: uuid.UUID
    reason: str


@dataclass(frozen=True, slots=True)
class RequirementPrototypeCoverage:
    covered_acceptance_criterion_refs: tuple[uuid.UUID, ...]
    uncovered_acceptance_criteria: tuple[UncoveredAcceptanceCriterion, ...]


@dataclass(frozen=True, slots=True)
class CreateRequirementPrototypeLink:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    prototype_id: uuid.UUID
    prototype_version_id: uuid.UUID
    purpose: str
    coverage: RequirementPrototypeCoverage
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementPrototypeLinkQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RequirementPrototypeLinkView:
    requirement_prototype_link_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    prototype_id: uuid.UUID
    prototype_version_id: uuid.UUID
    purpose: str
    coverage: RequirementPrototypeCoverage
    link_state: str
    lock_version: int
    created_by: uuid.UUID
    created_at: datetime
    superseded_by_ref: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class RequirementPrototypeLinkPage:
    items: tuple[RequirementPrototypeLinkView, ...]
    next_link_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class StoredRequirementPrototypeLink:
    link_id: uuid.UUID
    inserted: bool


class RequirementPrototypeLinkRepositoryPort(Protocol):
    def prove_current_endpoints(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
    ) -> tuple[uuid.UUID, ...] | None: ...
    def create_active(
        self, transaction: object, *, project_id: uuid.UUID,
        requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
        prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
        purpose: str, coverage: RequirementPrototypeCoverage,
        actor_id: uuid.UUID,
    ) -> StoredRequirementPrototypeLink: ...
    def get(self, transaction: object, *, project_id: uuid.UUID,
            link_id: uuid.UUID) -> RequirementPrototypeLinkView | None: ...
    def list_links(self, transaction: object, *, project_id: uuid.UUID,
                   after_link_id: uuid.UUID | None,
                   limit: int) -> tuple[RequirementPrototypeLinkView, ...]: ...


class RequirementPrototypeLinkService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], write_access: object,
        read_access: object, license_guard: object,
        authorization: ProjectAuthorizationService,
        repository: RequirementPrototypeLinkRepositoryPort,
        version_reader: object, current_validator: object,
        receipts: object, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, write_access, read_access, license_guard,
            authorization, repository, version_reader, current_validator,
            receipts, audit,
        )):
            raise ValueError("RequirementPrototypeLink dependencies required")
        self._uow, self._write_access = unit_of_work, write_access
        self._read_access, self._guard = read_access, license_guard
        self._authorization, self._repo = authorization, repository
        self._versions, self._validator = version_reader, current_validator
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(
        self, command: CreateRequirementPrototypeLink,
    ) -> RequirementPrototypeLinkView:
        self._validate_create(command)
        coverage = self._coverage(command.coverage)
        payload = self._coverage_payload(coverage)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "requirement_id": str(command.requirement_id),
                "requirement_version_id": str(command.requirement_version_id),
                "prototype_id": str(command.prototype_id),
                "prototype_version_id": str(command.prototype_version_id),
                "purpose": command.purpose, "coverage": payload,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(
                    self._write_access, tx, command.session_token,
                    command.csrf_token,
                )
                self._authorize(tx, actor, command.project_id, "PRT_LINK_CREATE")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _RESULT_TYPE or replay.status_code != 201:
                        raise RequirementPrototypeLinkError()
                    view = self._get(tx, command.project_id, replay.ref_id)
                    self._prove(tx, command, coverage)
                    if not self._matches(view, command, coverage):
                        raise RequirementPrototypeLinkError()
                    return view
                self._prove(tx, command, coverage)
                stored = self._repo.create_active(
                    tx, project_id=command.project_id,
                    requirement_id=command.requirement_id,
                    requirement_version_id=command.requirement_version_id,
                    prototype_id=command.prototype_id,
                    prototype_version_id=command.prototype_version_id,
                    purpose=command.purpose, coverage=coverage, actor_id=actor,
                )
                if (type(stored) is not StoredRequirementPrototypeLink
                        or not self._id(stored.link_id)
                        or type(stored.inserted) is not bool):
                    raise RequirementPrototypeLinkError()
                view = self._get(tx, command.project_id, stored.link_id)
                if not self._matches(view, command, coverage):
                    raise RequirementPrototypeLinkError("LINK_CONFLICT")
                if stored.inserted:
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="PROJECT",
                        target_project_id=command.project_id, actor_type="USER",
                        actor_id=actor, original_actor_id=None,
                        actor_hint_digest=None,
                        action="REQUIREMENT_PROTOTYPE_LINK_CREATED",
                        outcome="SUCCESS", target_owner_module="prototype",
                        target_object_type="PRT-05",
                        target_object_id=stored.link_id, after_state="ACTIVE",
                    ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(
                        _RESULT_TYPE, stored.link_id, 201,
                    ),
                )
                tx.commit()
                return view
        except RequirementPrototypeLinkError:
            raise
        except IdempotencyError as error:
            raise RequirementPrototypeLinkError(error.code) from None
        except ProjectAuthorizationError as error:
            raise RequirementPrototypeLinkError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementPrototypeLinkError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementPrototypeLinkError() from None

    def list(
        self, query: RequirementPrototypeLinkQuery, *, page_size: int,
        after_link_id: uuid.UUID | None = None,
    ) -> RequirementPrototypeLinkPage:
        if (type(query) is not RequirementPrototypeLinkQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or not self._id(query.trace_id) or not self._id(query.project_id)
                or type(page_size) is not int or not 1 <= page_size <= 200
                or after_link_id is not None and not self._id(after_link_id)):
            raise RequirementPrototypeLinkError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                actor = self._actor(
                    self._read_access, tx, query.session_token, None,
                )
                self._authorize(tx, actor, query.project_id, "PRT_LINK_LIST")
                rows = self._repo.list_links(
                    tx, project_id=query.project_id,
                    after_link_id=after_link_id, limit=page_size + 1,
                )
                if (type(rows) is not tuple or len(rows) > page_size + 1
                        or any(type(row) is not RequirementPrototypeLinkView
                               for row in rows)):
                    raise RequirementPrototypeLinkError()
                items, more = rows[:page_size], len(rows) > page_size
                return RequirementPrototypeLinkPage(
                    items, items[-1].requirement_prototype_link_id if more else None,
                    more,
                )
        except RequirementPrototypeLinkError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementPrototypeLinkError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementPrototypeLinkError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RequirementPrototypeLinkError() from None

    def _prove(self, tx, command, coverage):
        criteria = self._repo.prove_current_endpoints(
            tx, project_id=command.project_id,
            requirement_id=command.requirement_id,
            requirement_version_id=command.requirement_version_id,
            prototype_id=command.prototype_id,
            prototype_version_id=command.prototype_version_id,
        )
        if type(criteria) is not tuple or not criteria:
            raise RequirementPrototypeLinkError("RESOURCE_NOT_FOUND")
        snapshot = self._versions.get(
            tx, project_id=command.project_id,
            prototype_id=command.prototype_id,
            version_id=command.prototype_version_id,
        )
        if (snapshot is None or snapshot.version_state != "APPROVED"
                or self._validator.current_facts(tx, snapshot) is None):
            raise RequirementPrototypeLinkError("PROTOTYPE_INPUT_DRIFT")
        refs = {(item.requirement_id, item.requirement_version_id)
                for item in snapshot.requirement_refs}
        if (command.requirement_id, command.requirement_version_id) not in refs:
            raise RequirementPrototypeLinkError("RESOURCE_NOT_FOUND")
        declared = set(criteria)
        covered = set(coverage.covered_acceptance_criterion_refs)
        uncovered = {item.acceptance_criterion_ref
                     for item in coverage.uncovered_acceptance_criteria}
        if covered & uncovered or covered | uncovered != declared:
            raise RequirementPrototypeLinkError("COVERAGE_INCOMPLETE")

    def _actor(self, access, tx, token, csrf):
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementPrototypeLinkError()
        kwargs = {"session_token": token, "now": now.astimezone(timezone.utc)}
        if csrf is not None:
            kwargs["csrf_token"] = csrf
        actor = access.authenticated_user(tx, **kwargs)
        if not self._id(actor):
            raise RequirementPrototypeLinkError("AUTH_ACCESS_DENIED")
        return actor

    def _authorize(self, tx, actor, project_id, operation):
        proof = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id, operation=operation,
        )
        if (proof.user_id != actor or proof.project_id != project_id
                or proof.operation != operation):
            raise RequirementPrototypeLinkError("RESOURCE_NOT_FOUND")

    @classmethod
    def _validate_create(cls, command):
        if (type(command) is not CreateRequirementPrototypeLink
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(not cls._id(value) for value in (
                    command.trace_id, command.project_id,
                    command.requirement_id, command.requirement_version_id,
                    command.prototype_id, command.prototype_version_id,
                ))
                or command.purpose not in LINK_PURPOSES):
            raise RequirementPrototypeLinkError("VALIDATION_FAILED")

    @classmethod
    def _coverage(cls, value):
        if (type(value) is not RequirementPrototypeCoverage
                or type(value.covered_acceptance_criterion_refs) is not tuple
                or not 1 <= len(value.covered_acceptance_criterion_refs) <= 500
                or type(value.uncovered_acceptance_criteria) is not tuple
                or len(value.uncovered_acceptance_criteria) > 499):
            raise RequirementPrototypeLinkError("VALIDATION_FAILED")
        covered = tuple(sorted(value.covered_acceptance_criterion_refs,
                               key=lambda item: item.bytes))
        if any(not cls._id(item) for item in covered) or len(set(covered)) != len(covered):
            raise RequirementPrototypeLinkError("VALIDATION_FAILED")
        gaps = []
        for item in value.uncovered_acceptance_criteria:
            if type(item) is not UncoveredAcceptanceCriterion or not cls._id(
                    item.acceptance_criterion_ref):
                raise RequirementPrototypeLinkError("VALIDATION_FAILED")
            reason = unicodedata.normalize("NFKC", item.reason).strip()
            if (not 1 <= len(reason) <= 1000
                    or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", reason)):
                raise RequirementPrototypeLinkError("VALIDATION_FAILED")
            gaps.append(UncoveredAcceptanceCriterion(
                item.acceptance_criterion_ref, reason,
            ))
        gaps.sort(key=lambda item: item.acceptance_criterion_ref.bytes)
        if len({item.acceptance_criterion_ref for item in gaps}) != len(gaps):
            raise RequirementPrototypeLinkError("VALIDATION_FAILED")
        return RequirementPrototypeCoverage(covered, tuple(gaps))

    @staticmethod
    def _coverage_payload(value):
        return {
            "covered_acceptance_criterion_refs": [
                str(item) for item in value.covered_acceptance_criterion_refs
            ],
            "uncovered_acceptance_criteria": [{
                "acceptance_criterion_ref": str(item.acceptance_criterion_ref),
                "reason": item.reason,
            } for item in value.uncovered_acceptance_criteria],
        }

    @staticmethod
    def _matches(view, command, coverage):
        return (
            view.project_id == command.project_id
            and view.requirement_id == command.requirement_id
            and view.requirement_version_id == command.requirement_version_id
            and view.prototype_id == command.prototype_id
            and view.prototype_version_id == command.prototype_version_id
            and view.purpose == command.purpose and view.coverage == coverage
            and view.link_state == "ACTIVE" and view.lock_version == 0
        )

    def _get(self, tx, project_id, link_id):
        view = self._repo.get(tx, project_id=project_id, link_id=link_id)
        if type(view) is not RequirementPrototypeLinkView:
            raise RequirementPrototypeLinkError()
        return view

    @staticmethod
    def _id(value):
        return type(value) is uuid.UUID and value.int != 0
