"""Authorized, same-transaction inventory of all current approved Requirements.

This is an internal proof for Outline coverage, not a public list endpoint.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification,
    CurrentChecklistQualificationQuery,
)

from .read_versions import RequirementVersionReadQuery
from .workflow_qualification import RequirementWorkflowScopeLock


MAX_INVENTORY_ROOTS = 500


class ApprovedRequirementInventoryError(RuntimeError):
    def __init__(self, code: str = "REQUIREMENT_INVENTORY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CurrentApprovedRequirement:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID
    content_fingerprint: bytes
    review_id: uuid.UUID
    review_round_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ExplainedRequirementExclusion:
    requirement_id: uuid.UUID
    requirement_state: str
    decision_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ApprovedRequirementInventory:
    project_id: uuid.UUID
    root_count: int
    approved: tuple[CurrentApprovedRequirement, ...]
    explained: tuple[ExplainedRequirementExclusion, ...]
    scope_fingerprint: bytes


class RequirementScopeQualificationPort(Protocol):
    def qualify_with_scope_in_transaction(
        self, transaction: object, query: CurrentChecklistQualificationQuery,
    ) -> tuple[RequirementWorkflowScopeLock, AggregateChecklistQualification]: ...


class ApprovedRequirementInventoryService:
    """Fail closed unless the complete, current Requirement scope is qualified.

    Production composition must inject a qualification Owner backed by
    ``SqlAlchemyRequirementWorkflowQualificationRepository(max_roots=500)``.
    The result check is a second fence against incorrectly configured ports.
    """

    def __init__(self, *, access: object, license_guard: object,
                 authorization: ProjectAuthorizationService,
                 qualification: RequirementScopeQualificationPort,
                 clock=None) -> None:
        if any(value is None for value in (
                access, license_guard, authorization, qualification)):
            raise ValueError("approved inventory dependencies required")
        self._access = access
        self._guard = license_guard
        self._authorization = authorization
        self._qualification = qualification
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove_in_transaction(
        self, transaction: object, query: RequirementVersionReadQuery,
    ) -> ApprovedRequirementInventory:
        if (transaction is None
                or type(query) is not RequirementVersionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID
                or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID
                or query.project_id.int == 0):
            raise ApprovedRequirementInventoryError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise ApprovedRequirementInventoryError()
            actor = self._access.authenticated_user(
                transaction, session_token=query.session_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ApprovedRequirementInventoryError("AUTH_ACCESS_DENIED")
            authorized = self._authorization.require_in_transaction(
                transaction, user_id=actor, project_id=query.project_id,
                operation="REQ_VERSION_GET",
            )
            if (authorized.user_id != actor
                    or authorized.project_id != query.project_id
                    or authorized.operation != "REQ_VERSION_GET"):
                raise ApprovedRequirementInventoryError()
            scope, qualification = self._qualification.qualify_with_scope_in_transaction(
                transaction, CurrentChecklistQualificationQuery(
                    query.session_token, query.trace_id, query.project_id,
                    "REQUIREMENT_FORMAL_VERSIONS",
                ),
            )
            if (type(scope) is not RequirementWorkflowScopeLock
                    or type(qualification) is not AggregateChecklistQualification):
                raise ApprovedRequirementInventoryError()
            scope.__post_init__()
            qualification.__post_init__()
            if (scope.project_id != query.project_id
                    or qualification.project_id != query.project_id
                    or qualification.item_key != "REQUIREMENT_FORMAL_VERSIONS"
                    or scope.root_count > MAX_INVENTORY_ROOTS
                    or len(qualification.subjects) != len(scope.approved)):
                raise ApprovedRequirementInventoryError()
            for locked, subject in zip(scope.approved, qualification.subjects):
                if (subject.subject_type != "REQ-03"
                        or subject.subject_id != locked.snapshot.requirement_id
                        or subject.subject_version_id != locked.latest_version_id
                        or subject.content_fingerprint
                           != locked.snapshot.content_fingerprint
                        or subject.review.review_id != locked.review_id
                        or subject.review.review_round_id != locked.review_round_id):
                    raise ApprovedRequirementInventoryError()
            return ApprovedRequirementInventory(
                query.project_id,
                scope.root_count,
                tuple(CurrentApprovedRequirement(
                    locked.snapshot.requirement_id,
                    locked.latest_version_id,
                    locked.snapshot.content_fingerprint,
                    locked.review_id,
                    locked.review_round_id,
                ) for locked in scope.approved),
                tuple(ExplainedRequirementExclusion(
                    locked.requirement_id, locked.requirement_state,
                    locked.decision_id,
                ) for locked in scope.decisions),
                qualification.scope_fingerprint,
            )
        except ApprovedRequirementInventoryError:
            raise
        except ProjectAuthorizationError as error:
            raise ApprovedRequirementInventoryError(error.code) from None
        except RuntimeLicenseError:
            raise ApprovedRequirementInventoryError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApprovedRequirementInventoryError() from None
