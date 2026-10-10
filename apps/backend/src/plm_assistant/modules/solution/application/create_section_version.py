"""Authorized atomic first DRAFT SectionVersion creation and exact replay."""

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
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .prove_section_version_input import (
    ProvenSectionVersionInput, SectionVersionInputProofError,
    SectionVersionInputProofService,
)
from .section_version_input import (
    SectionRequirementRef, SectionVersionDraftInput, SectionVersionInputError,
    validate_section_version_draft,
)


_OPERATION = "V1_SOL_SECTION_VERSION_CREATE"


class SectionVersionCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSectionVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    draft: SectionVersionDraftInput = field(repr=False)
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SectionVersionInitialView:
    solution_section_version_id: uuid.UUID
    solution_section_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    title: str
    content_document_version_ref: uuid.UUID
    content_fingerprint: bytes = field(repr=False)
    requirement_refs: tuple[SectionRequirementRef, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    assumptions: tuple[dict[str, object], ...] = field(repr=False)
    exclusions: tuple[dict[str, object], ...] = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    version_state: str = "DRAFT"
    content_artifact_ref: None = None
    review_ref: None = None
    review_round_ref: None = None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.solution_section_version_id, self.solution_section_id,
                self.project_id, self.content_document_version_ref,
                self.created_by))
                or type(self.version_no) is not int or self.version_no < 1
                or type(self.title) is not str or not 1 <= len(self.title) <= 500
                or self.title != self.title.strip()
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.requirement_refs) is not tuple
                or any(type(item) is not SectionRequirementRef
                       for item in self.requirement_refs)
                or type(self.evidence_ids) is not tuple
                or any(type(item) is not uuid.UUID or item.int == 0
                       for item in self.evidence_ids)
                or type(self.assumptions) is not tuple
                or type(self.exclusions) is not tuple
                or any(type(item) is not dict for item in (
                    *self.assumptions, *self.exclusions))
                or (self.supersedes_version_ref is not None and (
                    type(self.supersedes_version_ref) is not uuid.UUID
                    or self.supersedes_version_ref.int == 0))
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None
                or self.created_at.utcoffset() is None
                or self.version_state != "DRAFT"
                or self.content_artifact_ref is not None
                or self.review_ref is not None
                or self.review_round_ref is not None):
            raise ValueError("invalid first SectionVersion result")


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, version_id: uuid.UUID,
               actor_id: uuid.UUID,
               proof: ProvenSectionVersionInput) -> SectionVersionInitialView: ...

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> SectionVersionInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class SectionVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 inputs: SectionVersionInputProofService,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                inputs, repository, receipts, audit)):
            raise ValueError("SectionVersion create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._inputs = authorization, inputs
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSectionVersion) -> SectionVersionInitialView:
        if (type(command) is not CreateSectionVersion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0):
            raise SectionVersionCreateError("VALIDATION_FAILED")
        try:
            draft = validate_section_version_draft(command.draft)
            validate_idempotency_key(command.idempotency_key)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=draft.project_id,
                    operation="SOL_SECTION_VERSION_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != draft.project_id
                        or authorized.operation != "SOL_SECTION_VERSION_CREATE"):
                    raise SectionVersionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=draft.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope,
                    request_fingerprint=draft.request_fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise SectionVersionCreateError()
                    result = self._repository.first_result(
                        tx, version_id=previous.ref_id, project_id=draft.project_id)
                    if (type(result) is not SectionVersionInitialView
                            or result.solution_section_id != draft.solution_section_id
                            or result.created_by != actor):
                        raise SectionVersionCreateError()
                    return result
                proof = self._inputs.prove(
                    tx, session_token=command.session_token,
                    trace_id=command.trace_id, draft=command.draft)
                if (type(proof) is not ProvenSectionVersionInput
                        or proof.draft != draft
                        or proof.draft.project_id != draft.project_id
                        or proof.draft.solution_section_id != draft.solution_section_id
                        or proof.base.project_id != draft.project_id
                        or proof.base.solution_section_id != draft.solution_section_id
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    raise SectionVersionCreateError()
                version_id = uuid.UUID(new_uuid7())
                result = self._repository.create(
                    tx, version_id=version_id, actor_id=actor, proof=proof)
                if (type(result) is not SectionVersionInitialView
                        or result.solution_section_version_id != version_id
                        or result.solution_section_id != draft.solution_section_id
                        or result.project_id != draft.project_id
                        or result.version_no != proof.base.next_version_no
                        or result.title != draft.title
                        or result.content_document_version_ref
                        != draft.content_document_version_ref
                        or result.content_fingerprint != proof.content_fingerprint
                        or result.requirement_refs != draft.requirement_refs
                        or result.evidence_ids != draft.evidence_ids
                        or result.assumptions != tuple(draft.assumptions())
                        or result.exclusions != tuple(draft.exclusions())
                        or result.supersedes_version_ref
                        != proof.base.supersedes_version_id
                        or result.created_by != actor):
                    raise SectionVersionCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=draft.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SOL_SECTION_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-05",
                    target_object_id=draft.solution_section_id,
                    target_version_id=version_id, after_state="DRAFT",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201))
                tx.commit()
                return result
        except SectionVersionCreateError:
            raise
        except (SectionVersionInputError, IdempotencyError) as error:
            raise SectionVersionCreateError(error.code) from None
        except ProjectAuthorizationError as error:
            raise SectionVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SectionVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except SectionVersionInputProofError as error:
            raise SectionVersionCreateError(error.code) from None
        except Exception:
            raise SectionVersionCreateError() from None

    def _actor(self, tx: object, command: CreateSectionVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SectionVersionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SectionVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
