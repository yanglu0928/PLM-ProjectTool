"""Authorized immutable revision of GLOBAL/PROJECT PrototypeTemplate."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeDocumentArtifactProofPort,
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

from .create_template import (
    AdminAccessPort, LicensePort, ProjectAccessPort, PrototypeTemplateCreateError,
    PrototypeTemplateCreateService, ReceiptPort, TemplateArtifactRef,
)


class PrototypeTemplateReviseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviseProjectPrototypeTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_template_id: uuid.UUID
    expected_lock_version: int
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReviseGlobalPrototypeTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    prototype_template_id: uuid.UUID
    expected_lock_version: int
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentPrototypeTemplate:
    prototype_template_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    template_state: str
    current_template_version_ref: uuid.UUID
    current_version_no: int
    lock_version: int


@dataclass(frozen=True, slots=True)
class PrototypeTemplateRevisionView:
    prototype_template_id: uuid.UUID
    prototype_template_version_id: uuid.UUID
    supersedes_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    version_no: int
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    content_fingerprint: str
    lock_version: int
    created_at: datetime
    template_state: str = "ACTIVE"
    version_state: str = "PUBLISHED"

    @property
    def etag(self) -> str:
        return f'"v{self.lock_version}"'

    def __post_init__(self) -> None:
        if (
            type(self.prototype_template_id) is not uuid.UUID
            or self.prototype_template_id.int == 0
            or type(self.prototype_template_version_id) is not uuid.UUID
            or self.prototype_template_version_id.int == 0
            or type(self.supersedes_version_id) is not uuid.UUID
            or self.supersedes_version_id.int == 0
            or self.scope not in {"GLOBAL", "PROJECT"}
            or (self.scope == "GLOBAL" and self.project_id is not None)
            or (self.scope == "PROJECT" and (
                type(self.project_id) is not uuid.UUID or self.project_id.int == 0
            ))
            or type(self.name) is not str or not self.name
            or type(self.version_no) is not int or self.version_no < 2
            or self.lock_version != self.version_no - 1
            or type(self.layout_contract) is not dict
            or type(self.component_contract) is not dict
            or type(self.applicable_terminals) is not tuple
            or type(self.artifact_refs) is not tuple
            or re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint) is None
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
            or self.template_state != "ACTIVE"
            or self.version_state != "PUBLISHED"
        ):
            raise ValueError("invalid PrototypeTemplate revision view")


class RepositoryPort(Protocol):
    def current_for_update(
        self, transaction: object, *, template_id: uuid.UUID,
        scope: str, project_id: uuid.UUID | None,
    ) -> CurrentPrototypeTemplate | None: ...

    def revise(
        self, transaction: object, *, result_id: uuid.UUID,
        current: CurrentPrototypeTemplate, version_id: uuid.UUID,
        layout_contract: dict[str, object], component_contract: dict[str, object],
        applicable_terminals: tuple[str, ...],
        artifact_refs: tuple[TemplateArtifactRef, ...],
        content_fingerprint: bytes, actor_id: uuid.UUID,
    ) -> PrototypeTemplateRevisionView: ...

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
    ) -> PrototypeTemplateRevisionView | None: ...


class PrototypeTemplateReviseService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        project_access: ProjectAccessPort, admin_access: AdminAccessPort,
        license_guard: LicensePort, authorization: ProjectAuthorizationService,
        document_artifacts: PrototypeDocumentArtifactProofPort,
        repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, project_access, admin_access, license_guard, authorization,
            document_artifacts, repository, receipts, audit,
        )):
            raise ValueError("PrototypeTemplate revise dependencies are required")
        self._uow = unit_of_work
        self._project_access = project_access
        self._admin_access = admin_access
        self._guard = license_guard
        self._authorization = authorization
        self._documents = document_artifacts
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revise_project(
        self, command: ReviseProjectPrototypeTemplate,
    ) -> PrototypeTemplateRevisionView:
        return self._execute(command, scope="PROJECT", project_id=command.project_id)

    def revise_global(
        self, command: ReviseGlobalPrototypeTemplate,
    ) -> PrototypeTemplateRevisionView:
        return self._execute(command, scope="GLOBAL", project_id=None)

    def _execute(
        self, command: ReviseProjectPrototypeTemplate | ReviseGlobalPrototypeTemplate,
        *, scope: str, project_id: uuid.UUID | None,
    ) -> PrototypeTemplateRevisionView:
        self._validate(command, scope, project_id)
        try:
            layout = PrototypeTemplateCreateService._contract(command.layout_contract)
            components = PrototypeTemplateCreateService._contract(
                command.component_contract
            )
            terminals = PrototypeTemplateCreateService._terminals(
                command.applicable_terminals
            )
            artifacts = PrototypeTemplateCreateService._artifacts(command.artifact_refs)
            validate_idempotency_key(command.idempotency_key)
        except PrototypeTemplateCreateError as error:
            raise PrototypeTemplateReviseError(error.code) from None
        except IdempotencyError as error:
            raise PrototypeTemplateReviseError(error.code) from None
        operation = f"V1_PRT_TEMPLATE_{scope}_REVISE"
        request_fingerprint = canonical_payload_fingerprint({
            "scope": scope, "project_id": None if project_id is None else str(project_id),
            "prototype_template_id": str(command.prototype_template_id),
            "expected_lock_version": command.expected_lock_version,
            "layout_contract": layout, "component_contract": components,
            "applicable_terminals": list(terminals),
            "artifact_refs": [{"artifact_kind": item.artifact_kind,
                               "target_id": str(item.target_id)} for item in artifacts],
        })
        version_id = uuid.UUID(new_uuid7())
        result_id = uuid.UUID(new_uuid7())
        try:
            with self._uow() as tx:
                self._authorize(tx, command, scope=scope, project_id=project_id)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._authorize(tx, command, scope=scope, project_id=project_id)
                receipt_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=project_id,
                    operation=operation, key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=receipt_scope,
                    request_fingerprint=request_fingerprint,
                )
                if previous is not None:
                    if previous.ref_type != operation or previous.status_code != 201:
                        raise PrototypeTemplateReviseError("PROTOTYPE_UNAVAILABLE")
                    view = self._repository.result(tx, result_id=previous.ref_id)
                    if not self._matches(view, command, scope, project_id, layout,
                                         components, terminals, artifacts):
                        raise PrototypeTemplateReviseError("PROTOTYPE_UNAVAILABLE")
                    return view
                current = self._repository.current_for_update(
                    tx, template_id=command.prototype_template_id,
                    scope=scope, project_id=project_id,
                )
                if current is None:
                    raise PrototypeTemplateReviseError("RESOURCE_NOT_FOUND")
                if current.template_state != "ACTIVE":
                    raise PrototypeTemplateReviseError("PROTOTYPE_STATE_CONFLICT")
                if current.lock_version != command.expected_lock_version:
                    raise PrototypeTemplateReviseError("VERSION_CONFLICT")
                if current.current_version_no != current.lock_version + 1:
                    raise PrototypeTemplateReviseError("PROTOTYPE_UNAVAILABLE")
                artifact_digests: list[dict[str, str]] = []
                for artifact in artifacts:
                    if artifact.artifact_kind != "DOCUMENT_VERSION":
                        raise PrototypeTemplateReviseError(
                            "PROTOTYPE_ARTIFACT_UNAVAILABLE"
                        )
                    proof = self._documents.prove(
                        tx, template_scope=scope, project_id=project_id,
                        document_version_id=artifact.target_id,
                    )
                    if proof is None or proof.document_version_id != artifact.target_id:
                        raise PrototypeTemplateReviseError(
                            "PROTOTYPE_ARTIFACT_UNAVAILABLE"
                        )
                    artifact_digests.append({
                        "artifact_kind": artifact.artifact_kind,
                        "target_id": str(artifact.target_id),
                        "content_sha256": proof.content_sha256,
                    })
                content_fingerprint = canonical_payload_fingerprint({
                    "layout_contract": layout,
                    "component_contract": components,
                    "applicable_terminals": list(terminals),
                    "artifact_proofs": artifact_digests,
                })
                view = self._repository.revise(
                    tx, result_id=result_id, current=current, version_id=version_id,
                    layout_contract=layout, component_contract=components,
                    applicable_terminals=terminals, artifact_refs=artifacts,
                    content_fingerprint=content_fingerprint, actor_id=actor,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="DEPLOYMENT" if scope == "GLOBAL" else "PROJECT",
                    target_project_id=project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="PROTOTYPE_TEMPLATE_REVISED", outcome="SUCCESS",
                    target_owner_module="prototype", target_object_type="PRT-04",
                    target_object_id=current.prototype_template_id,
                    before_state=f"TEMPLATE_V{current.current_version_no}",
                    after_state=f"TEMPLATE_V{view.version_no}",
                ))
                self._receipts.complete(
                    tx, scope=receipt_scope,
                    result=IdempotencyResult(operation, result_id, 201),
                )
                tx.commit()
                return view
        except PrototypeTemplateReviseError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeTemplateReviseError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeTemplateReviseError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeTemplateReviseError(error.code) from None
        except Exception:
            raise PrototypeTemplateReviseError("PROTOTYPE_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: object, scope: str, project_id: uuid.UUID | None) -> None:
        if (
            type(command) not in (
                ReviseProjectPrototypeTemplate, ReviseGlobalPrototypeTemplate,
            )
            or type(command.session_token) is not bytes
            or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes
            or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.prototype_template_id) is not uuid.UUID
            or command.prototype_template_id.int == 0
            or type(command.expected_lock_version) is not int
            or not 0 <= command.expected_lock_version < 2**63 - 1
            or (scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0
            ))
            or (scope == "GLOBAL" and project_id is not None)
        ):
            raise PrototypeTemplateReviseError("VALIDATION_FAILED")

    def _authorize(
        self, tx: object,
        command: ReviseProjectPrototypeTemplate | ReviseGlobalPrototypeTemplate,
        *, scope: str, project_id: uuid.UUID | None,
    ) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeTemplateReviseError("PROTOTYPE_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        if scope == "GLOBAL":
            actor = self._admin_access.authorized_admin(
                tx, session_token=command.session_token,
                csrf_token=command.csrf_token, now=now,
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise PrototypeTemplateReviseError("AUTH_ACCESS_DENIED")
            return actor
        actor = self._project_access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeTemplateReviseError("AUTH_ACCESS_DENIED")
        authorized = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id,
            operation="PRT_TEMPLATE_REVISE",
        )
        if (
            authorized.user_id != actor or authorized.project_id != project_id
            or authorized.operation != "PRT_TEMPLATE_REVISE"
        ):
            raise PrototypeTemplateReviseError("RESOURCE_NOT_FOUND")
        return actor

    @staticmethod
    def _matches(
        view: PrototypeTemplateRevisionView | None,
        command: ReviseProjectPrototypeTemplate | ReviseGlobalPrototypeTemplate,
        scope: str, project_id: uuid.UUID | None,
        layout: dict[str, object], components: dict[str, object],
        terminals: tuple[str, ...], artifacts: tuple[TemplateArtifactRef, ...],
    ) -> bool:
        return (
            type(view) is PrototypeTemplateRevisionView
            and view.prototype_template_id == command.prototype_template_id
            and view.scope == scope and view.project_id == project_id
            and view.lock_version == command.expected_lock_version + 1
            and view.layout_contract == layout
            and view.component_contract == components
            and view.applicable_terminals == terminals
            and view.artifact_refs == artifacts
        )
