"""Create one complete immutable PlanVersion DRAFT in a single transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.plan.application.plan_version_input import (
    FixedVersionRef, PlanVersionDraftInput, PlanVersionInputError,
    ValidatedPlanVersionDraft, parse_plan_version_draft,
)
from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProof, ApprovedSolutionInputProofError,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineCurrentFactQuery,
)


_OPERATION = "V1_PLAN_VERSION_CREATE"
_CATEGORY_CODES = frozenset({
    "ANALYSIS", "DESIGN", "IMPLEMENTATION", "TEST", "DEPLOYMENT", "TRAINING",
    "ACCEPTANCE", "PROJECT_MANAGEMENT", "OTHER",
})
_SUPPORT_ROLE_CODES = frozenset({
    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
})
_CALENDAR_CODES = frozenset({"CN_WORKDAY"})


class PlanVersionCreateError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class PlanVersionSourceProofError(RuntimeError):
    """No current, same-Project proof exists for a fixed Plan input reference."""


@dataclass(frozen=True, slots=True)
class CreatePlanVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    draft: object = field(repr=False)
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PlanVersionCreatedView:
    plan_version_id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    created_at: datetime


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class SolutionProofPort(Protocol):
    def prove(self, transaction: object, *, command: OutlineCurrentFactQuery
              ) -> ApprovedSolutionInputProof: ...


class SourceProofPort(Protocol):
    def validate(self, transaction: object, *, project_id: uuid.UUID,
                 draft: PlanVersionDraftInput,
                 solution: ApprovedSolutionInputProof) -> None: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, actor_id: uuid.UUID,
               project_id: uuid.UUID, plan_id: uuid.UUID,
               draft: ValidatedPlanVersionDraft) -> PlanVersionCreatedView: ...

    def first_result(self, transaction: object, *, plan_version_id: uuid.UUID,
                     project_id: uuid.UUID, plan_id: uuid.UUID
                     ) -> PlanVersionCreatedView | None: ...


class PlanVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 solution_proof: SolutionProofPort,
                 source_proofs: SourceProofPort,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                solution_proof, source_proofs, repository, receipts, audit)):
            raise ValueError("PlanVersion create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization = authorization
        self._solution_proof, self._source_proofs = solution_proof, source_proofs
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreatePlanVersion) -> PlanVersionCreatedView:
        if (type(command) is not CreatePlanVersion
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or not self._valid_id(command.trace_id)
                or not self._valid_id(command.project_id)
                or not self._valid_id(command.plan_id)):
            raise PlanVersionCreateError("VALIDATION_FAILED")
        try:
            validated = parse_plan_version_draft(
                command.draft, project_id=command.project_id, plan_id=command.plan_id)
            self._validate_codes(validated.input)
            validate_idempotency_key(command.idempotency_key)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise PlanVersionCreateError()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now.astimezone(timezone.utc))
                if not self._valid_id(actor):
                    raise PlanVersionCreateError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PLAN_VERSION_CREATE")
                if (authorized.user_id != actor or authorized.project_id != command.project_id
                        or authorized.operation != "PLAN_VERSION_CREATE"):
                    raise PlanVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=validated.request_fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise PlanVersionCreateError()
                    result = self._repo.first_result(
                        tx, plan_version_id=previous.ref_id,
                        project_id=command.project_id, plan_id=command.plan_id)
                    if result is None:
                        raise PlanVersionCreateError()
                    return result

                root_refs = tuple(ref for ref in validated.input.approved_solution_refs
                                  if ref.resource_kind == "OUTLINE")
                if len(root_refs) != 1:
                    raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
                outline = root_refs[0]
                proof = self._solution_proof.prove(tx, command=OutlineCurrentFactQuery(
                    command.session_token, command.trace_id, command.project_id,
                    outline.resource_id, outline.version_id))
                self._validate_solution_refs(
                    command.project_id, validated.input, proof)
                self._source_proofs.validate(
                    tx, project_id=command.project_id,
                    draft=validated.input, solution=proof)
                result = self._repo.create(
                    tx, actor_id=actor, project_id=command.project_id,
                    plan_id=command.plan_id, draft=validated)
                if (type(result) is not PlanVersionCreatedView
                        or result.project_id != command.project_id
                        or result.plan_id != command.plan_id
                        or result.version_state != "DRAFT"):
                    raise PlanVersionCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="PLAN_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="plan", target_object_type="PLN-02",
                    target_object_id=result.plan_version_id, after_state="DRAFT",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, result.plan_version_id, 201))
                tx.commit()
                return result
        except PlanVersionCreateError:
            raise
        except (PlanVersionInputError, IdempotencyError) as error:
            raise PlanVersionCreateError(getattr(error, "code", "VALIDATION_FAILED")) from None
        except ApprovedSolutionInputProofError:
            raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE") from None
        except PlanVersionSourceProofError:
            raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE") from None
        except ProjectAuthorizationError as error:
            raise PlanVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise PlanVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanVersionCreateError() from None

    @staticmethod
    def _validate_codes(draft: PlanVersionDraftInput) -> None:
        if draft.calendar_ref is not None and draft.calendar_ref not in _CALENDAR_CODES:
            raise PlanVersionCreateError("VALIDATION_FAILED")
        if any(item.category not in _CATEGORY_CODES for item in draft.wbs_items):
            raise PlanVersionCreateError("VALIDATION_FAILED")
        if any(role not in _SUPPORT_ROLE_CODES
               for item in draft.wbs_items for role in item.support_role_refs):
            raise PlanVersionCreateError("VALIDATION_FAILED")

    @staticmethod
    def _validate_solution_refs(project_id: uuid.UUID,
                                draft: PlanVersionDraftInput,
                                proof: ApprovedSolutionInputProof) -> None:
        if (type(proof) is not ApprovedSolutionInputProof
                or proof.project_id != project_id
                or proof.project_id.int == 0):
            raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
        qualified = {
            FixedVersionRef("OUTLINE", proof.outline_id, proof.outline_version_id),
            *(FixedVersionRef("SECTION", item.section_id, item.section_version_id)
              for item in proof.sections),
        }
        requirement_refs = {
            (ref.requirement_id, ref.requirement_version_id)
            for ref in proof.requirement_refs
        }
        for section in proof.sections:
            for spec in section.qualified_specs:
                ref = spec.ref
                # The current approved spec version is independently pinned and
                # verified by SourceProofPort, which owns its current pointer lock.
                if not any(item.resource_kind == "STRUCTURED_SPEC"
                           and item.resource_id == ref.structured_solution_spec_id
                           and item.spec_series_id == ref.spec_series_id
                           for item in draft.approved_solution_refs):
                    raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
        submitted = set(draft.approved_solution_refs)
        if not qualified.issubset(submitted):
            raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
        represented = {ref for item in draft.wbs_items for ref in item.solution_refs}
        if represented != submitted:
            # The frozen schema stores solution refs per WBS item; do not accept
            # root-level Approved refs that could not be reconstructed from rows.
            raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
        for item in draft.wbs_items:
            if any(ref not in submitted for ref in item.solution_refs):
                raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")
            if any((ref.requirement_id, ref.requirement_version_id) not in requirement_refs
                   for ref in item.requirement_refs):
                raise PlanVersionCreateError("PLAN_SOURCE_UNAVAILABLE")

    @staticmethod
    def _valid_id(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0
