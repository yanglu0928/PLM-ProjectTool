"""Atomic, authorized creation of immutable DRAFT PrototypeVersions."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProofPort,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProofPort,
)

from .create_template import PrototypeTemplateCreateError, PrototypeTemplateCreateService
from .version_input_proofs import PrototypeVersionTemplateProofPort


class PrototypeVersionCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class VersionArtifactRef:
    artifact_kind: str
    target_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class VersionRequirementRef:
    requirement_id: uuid.UUID
    requirement_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CreatePrototypeVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    expected_lock_version: int
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    artifact_refs: tuple[VersionArtifactRef, ...]
    requirement_refs: tuple[VersionRequirementRef, ...]
    interaction_spec: dict[str, object]
    coverage_summary: dict[str, object]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrototypeVersionInitialView:
    prototype_version_id: uuid.UUID
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    supersedes_version_id: uuid.UUID | None
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    artifact_refs: tuple[VersionArtifactRef, ...]
    requirement_refs: tuple[VersionRequirementRef, ...]
    interaction_spec: dict[str, object]
    coverage_summary: dict[str, object]
    content_fingerprint: str
    created_at: datetime
    version_state: str = "DRAFT"


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, result_id: uuid.UUID,
               version_id: uuid.UUID, project_id: uuid.UUID,
               prototype_id: uuid.UUID, template_id: uuid.UUID,
               template_version_id: uuid.UUID,
               expected_lock_version: int,
               artifacts: tuple[VersionArtifactRef, ...],
               requirements: tuple[VersionRequirementRef, ...],
               interaction: dict[str, object], interaction_fingerprint: bytes,
               coverage: dict[str, object], content_fingerprint: bytes,
               actor_id: uuid.UUID) -> PrototypeVersionInitialView: ...

    def result(self, transaction: object, *, result_id: uuid.UUID,
               project_id: uuid.UUID,
               prototype_id: uuid.UUID) -> PrototypeVersionInitialView | None: ...


class PrototypeVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], project_access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 requirements: PrototypeApprovedRequirementVersionProofPort,
                 templates: PrototypeVersionTemplateProofPort,
                 documents: PrototypeVersionDocumentArtifactProofPort,
                 repository: RepositoryPort, receipts: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        values = (unit_of_work, project_access, license_guard, authorization,
                  requirements, templates, documents, repository, receipts, audit)
        if any(value is None for value in values):
            raise ValueError("PrototypeVersion create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, project_access, license_guard
        self._authorization, self._requirements = authorization, requirements
        self._templates, self._documents = templates, documents
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreatePrototypeVersion) -> PrototypeVersionInitialView:
        self._validate(command)
        artifacts = self._artifacts(command.artifact_refs)
        requirements = self._requirement_refs(command.requirement_refs)
        interaction = self._object(command.interaction_spec)
        coverage = self._object(command.coverage_summary)
        payload = {
            "project_id": str(command.project_id), "prototype_id": str(command.prototype_id),
            "expected_lock_version": command.expected_lock_version,
            "template_id": str(command.template_id),
            "template_version_id": str(command.template_version_id),
            "artifact_refs": [(x.artifact_kind, str(x.target_id)) for x in artifacts],
            "requirement_refs": [(str(x.requirement_id), str(x.requirement_version_id))
                                 for x in requirements],
            "interaction_spec": interaction, "coverage_summary": coverage,
        }
        request_fingerprint = canonical_payload_fingerprint(payload)
        try:
            validate_idempotency_key(command.idempotency_key)
            with self._uow() as tx:
                self._authorize(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            result_id, version_id = uuid.UUID(new_uuid7()), uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._authorize(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation="V1_PRT_VERSION_CREATE", key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint)
                if previous is not None:
                    if previous.ref_type != "V1_PRT_VERSION_CREATE" or previous.status_code != 201:
                        raise PrototypeVersionCreateError("PROTOTYPE_UNAVAILABLE")
                    view = self._repository.result(
                        tx, result_id=previous.ref_id, project_id=command.project_id,
                        prototype_id=command.prototype_id)
                    if view is None or not self._matches(view, command, artifacts, requirements,
                                                         interaction, coverage):
                        raise PrototypeVersionCreateError("PROTOTYPE_UNAVAILABLE")
                    return view
                template = self._templates.prove(
                    tx, project_id=command.project_id,
                    prototype_template_id=command.template_id,
                    prototype_template_version_id=command.template_version_id)
                if template is None:
                    raise PrototypeVersionCreateError("PROTOTYPE_TEMPLATE_UNAVAILABLE")
                artifact_proofs = []
                for item in artifacts:
                    if item.artifact_kind != "DOCUMENT_VERSION":
                        raise PrototypeVersionCreateError("PROTOTYPE_ARTIFACT_UNAVAILABLE")
                    proof = self._documents.prove_for_prototype_version(
                        tx, project_id=command.project_id,
                        document_version_id=item.target_id)
                    if proof is None:
                        raise PrototypeVersionCreateError("PROTOTYPE_ARTIFACT_UNAVAILABLE")
                    artifact_proofs.append((item.artifact_kind, str(item.target_id),
                                            proof.content_sha256))
                requirement_proofs = []
                for item in requirements:
                    proof = self._requirements.prove(
                        tx, project_id=command.project_id,
                        requirement_id=item.requirement_id,
                        requirement_version_id=item.requirement_version_id)
                    if proof is None:
                        raise PrototypeVersionCreateError("PROTOTYPE_REQUIREMENT_UNAVAILABLE")
                    requirement_proofs.append((str(item.requirement_id),
                                               str(item.requirement_version_id),
                                               proof.content_fingerprint))
                interaction_fp = canonical_payload_fingerprint(interaction)
                content_fp = canonical_payload_fingerprint({
                    **payload, "template_fingerprint": template.content_fingerprint,
                    "artifact_proofs": artifact_proofs,
                    "requirement_proofs": requirement_proofs,
                })
                view = self._repository.create(
                    tx, result_id=result_id, version_id=version_id,
                    project_id=command.project_id, prototype_id=command.prototype_id,
                    expected_lock_version=command.expected_lock_version,
                    template_id=command.template_id,
                    template_version_id=command.template_version_id,
                    artifacts=artifacts, requirements=requirements,
                    interaction=interaction, interaction_fingerprint=interaction_fp,
                    coverage=coverage, content_fingerprint=content_fp, actor_id=actor)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="PROTOTYPE_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="prototype", target_object_type="PRT-03",
                    target_object_id=version_id, after_state="DRAFT"))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_PRT_VERSION_CREATE", result_id, 201))
                tx.commit()
                return view
        except PrototypeVersionCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeVersionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeVersionCreateError(error.code) from None
        except Exception:
            raise PrototypeVersionCreateError("PROTOTYPE_UNAVAILABLE") from None

    def _authorize(self, tx: object, command: CreatePrototypeVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeVersionCreateError("PROTOTYPE_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeVersionCreateError("AUTH_ACCESS_DENIED")
        action = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=command.project_id,
            operation="PRT_VERSION_CREATE")
        if action.user_id != actor or action.project_id != command.project_id:
            raise PrototypeVersionCreateError("RESOURCE_NOT_FOUND")
        return actor

    @staticmethod
    def _validate(command: object) -> None:
        if (type(command) is not CreatePrototypeVersion
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or any(type(x) is not uuid.UUID or x.int == 0 for x in (
                command.trace_id, command.project_id, command.prototype_id,
                command.template_id, command.template_version_id))
            or type(command.expected_lock_version) is not int
            or not 0 <= command.expected_lock_version <= 9223372036854775806):
            raise PrototypeVersionCreateError("VALIDATION_FAILED")

    @staticmethod
    def _object(value: object) -> dict[str, object]:
        try:
            return PrototypeTemplateCreateService._contract(value)
        except PrototypeTemplateCreateError:
            raise PrototypeVersionCreateError("VALIDATION_FAILED") from None

    @staticmethod
    def _artifacts(value: object) -> tuple[VersionArtifactRef, ...]:
        if type(value) is not tuple or not 1 <= len(value) <= 100 or any(
            type(x) is not VersionArtifactRef or x.artifact_kind not in
            {"DOCUMENT_VERSION", "OUTPUT_ARTIFACT"} or type(x.target_id) is not uuid.UUID
            or x.target_id.int == 0 for x in value):
            raise PrototypeVersionCreateError("VALIDATION_FAILED")
        result = tuple(sorted(value, key=lambda x: (x.artifact_kind, str(x.target_id))))
        if len(set(result)) != len(result):
            raise PrototypeVersionCreateError("VALIDATION_FAILED")
        return result

    @staticmethod
    def _requirement_refs(value: object) -> tuple[VersionRequirementRef, ...]:
        if type(value) is not tuple or not 1 <= len(value) <= 200 or any(
            type(x) is not VersionRequirementRef
            or type(x.requirement_id) is not uuid.UUID or x.requirement_id.int == 0
            or type(x.requirement_version_id) is not uuid.UUID
            or x.requirement_version_id.int == 0 for x in value):
            raise PrototypeVersionCreateError("VALIDATION_FAILED")
        result = tuple(sorted(value, key=lambda x: str(x.requirement_version_id)))
        if len({x.requirement_version_id for x in result}) != len(result):
            raise PrototypeVersionCreateError("VALIDATION_FAILED")
        return result

    @staticmethod
    def _matches(view, command, artifacts, requirements, interaction, coverage) -> bool:
        return (type(view) is PrototypeVersionInitialView
                and view.project_id == command.project_id
                and view.prototype_id == command.prototype_id
                and view.template_id == command.template_id
                and view.template_version_id == command.template_version_id
                and view.artifact_refs == artifacts and view.requirement_refs == requirements
                and view.interaction_spec == interaction and view.coverage_summary == coverage)
