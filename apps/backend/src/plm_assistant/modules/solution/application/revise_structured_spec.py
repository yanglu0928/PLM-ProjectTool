"""Authorized atomic SOL-06 replacement DRAFT with durable exact replay."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .prove_structured_spec_sources import (
    ProvenStructuredSpecSources, StructuredSpecSourceError,
    StructuredSpecSourceProofService,
)
from .structured_spec_input import (
    StructuredSpecDraftInput, StructuredSpecInputError,
    ValidatedStructuredSpecDraft, validate_structured_spec_draft,
)
from .structured_spec_result import (
    StructuredSpecInitialView, StructuredSpecRevisionBase,
)


_OPERATION = "V1_SOL_STRUCTURED_SPEC_REVISE"
_POLICY = "SOL_STRUCTURED_SPEC_REVISE"
_ALLOWED_STATES = frozenset({"DRAFT", "RETURNED", "APPROVED"})


class StructuredSpecReviseError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviseStructuredSpec:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    spec_id: uuid.UUID
    draft: StructuredSpecDraftInput = field(repr=False)
    idempotency_key: str = field(repr=False)


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def revision_base(self, transaction: object, *, project_id: uuid.UUID,
                      spec_id: uuid.UUID) -> StructuredSpecRevisionBase | None: ...

    def revise(self, transaction: object, *, base: StructuredSpecRevisionBase,
               version_id: uuid.UUID, actor_id: uuid.UUID,
               proof: ProvenStructuredSpecSources) -> StructuredSpecInitialView: ...

    def first_result(self, transaction: object, *, version_id: uuid.UUID,
                     project_id: uuid.UUID) -> StructuredSpecInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _same_body(result: StructuredSpecInitialView,
               draft: ValidatedStructuredSpecDraft) -> bool:
    return (
        result.project_id == draft.project_id
        and result.spec_type == draft.spec_type
        and result.payload_json == draft.payload_json
        and result.payload_fingerprint == draft.payload_fingerprint
        and result.requirement_refs == draft.requirement_refs
        and result.section_refs == draft.section_refs
        and result.evidence_ids == draft.evidence_ids
        and result.artifact_ids == draft.artifact_ids
    )


class StructuredSpecReviseService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort,
                 authorization: ProjectAuthorizationService,
                 sources: StructuredSpecSourceProofService,
                 repository: RepositoryPort, receipts: ReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                sources, repository, receipts, audit)):
            raise ValueError("StructuredSpec revise dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources = authorization, sources
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revise(self, command: ReviseStructuredSpec) -> StructuredSpecInitialView:
        if (type(command) is not ReviseStructuredSpec
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or not _id(command.trace_id)
                or not _id(command.project_id)
                or not _id(command.spec_id)):
            raise StructuredSpecReviseError("VALIDATION_FAILED")
        try:
            draft = validate_structured_spec_draft(command.draft)
            if (draft.project_id != command.project_id
                    or draft.spec_series_id is not None
                    or draft.supersedes_version_ref is not None):
                raise StructuredSpecReviseError("VALIDATION_FAILED")
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "kind": "SOL_STRUCTURED_SPEC_REVISE_V1",
                "project_id": str(command.project_id),
                "spec_id": str(command.spec_id),
                "body_fingerprint": draft.request_fingerprint.hex(),
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation=_POLICY)
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != _POLICY):
                    raise StructuredSpecReviseError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if previous is not None:
                    return self._replay(
                        tx, actor=actor, command=command,
                        draft=draft, previous=previous)
                base = self._repository.revision_base(
                    tx, project_id=command.project_id, spec_id=command.spec_id)
                if base is None:
                    raise StructuredSpecReviseError("RESOURCE_NOT_FOUND")
                if (type(base) is not StructuredSpecRevisionBase
                        or base.structured_solution_spec_id != command.spec_id
                        or base.project_id != command.project_id
                        or not _id(base.spec_series_id)
                        or base.version_no < 1
                        or base.latest_version_no < base.version_no):
                    raise StructuredSpecReviseError()
                if base.latest_version_ref != command.spec_id:
                    raise StructuredSpecReviseError("VERSION_CONFLICT")
                if base.version_state not in _ALLOWED_STATES:
                    raise StructuredSpecReviseError("CONFLICT_STATE")
                if base.spec_type != draft.spec_type:
                    raise StructuredSpecReviseError("VALIDATION_FAILED")
                bound_input = replace(
                    command.draft, spec_series_id=base.spec_series_id,
                    supersedes_version_ref=command.spec_id)
                bound = validate_structured_spec_draft(bound_input)
                proof = self._sources.prove(
                    tx, session_token=command.session_token,
                    trace_id=command.trace_id, draft=bound_input)
                if (type(proof) is not ProvenStructuredSpecSources
                        or proof.draft != bound
                        or type(proof.content_fingerprint) is not bytes
                        or len(proof.content_fingerprint) != 32):
                    raise StructuredSpecReviseError()
                version_id = uuid.UUID(new_uuid7())
                result = self._repository.revise(
                    tx, base=base, version_id=version_id,
                    actor_id=actor, proof=proof)
                if (type(result) is not StructuredSpecInitialView
                        or result.structured_solution_spec_id != version_id
                        or result.spec_series_id != base.spec_series_id
                        or result.supersedes_version_ref != command.spec_id
                        or result.version_no != base.version_no + 1
                        or result.version_state != "DRAFT"
                        or result.content_fingerprint != proof.content_fingerprint
                        or result.created_by != actor
                        or not _same_body(result, draft)):
                    raise StructuredSpecReviseError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None,
                    action="SOL_STRUCTURED_SPEC_REVISED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-06",
                    target_object_id=base.spec_series_id,
                    target_version_id=version_id,
                    before_state=base.version_state, after_state="DRAFT",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, version_id, 201))
                tx.commit()
                return result
        except StructuredSpecReviseError:
            raise
        except (StructuredSpecInputError, IdempotencyError) as error:
            raise StructuredSpecReviseError(error.code) from None
        except ProjectAuthorizationError as error:
            raise StructuredSpecReviseError(error.code) from None
        except RuntimeLicenseError:
            raise StructuredSpecReviseError("LICENSE_OPERATION_DENIED") from None
        except StructuredSpecSourceError as error:
            raise StructuredSpecReviseError(error.code) from None
        except Exception:
            raise StructuredSpecReviseError() from None

    def _replay(self, tx: object, *, actor: uuid.UUID,
                command: ReviseStructuredSpec,
                draft: ValidatedStructuredSpecDraft,
                previous: IdempotencyResult) -> StructuredSpecInitialView:
        if previous.ref_type != _OPERATION or previous.status_code != 201:
            raise StructuredSpecReviseError()
        result = self._repository.first_result(
            tx, version_id=previous.ref_id, project_id=command.project_id)
        if (type(result) is not StructuredSpecInitialView
                or result.structured_solution_spec_id != previous.ref_id
                or result.supersedes_version_ref != command.spec_id
                or result.version_no < 2
                or result.version_state != "DRAFT"
                or result.created_by != actor
                or not _same_body(result, draft)):
            raise StructuredSpecReviseError()
        return result

    def _actor(self, tx: object, command: ReviseStructuredSpec) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise StructuredSpecReviseError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if not _id(actor):
            raise StructuredSpecReviseError("AUTH_ACCESS_DENIED")
        return actor
