"""Authorized GLOBAL/PROJECT PrototypeTemplate creation with immutable first version."""

from __future__ import annotations

import json
import math
import re
import unicodedata
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


_TERMINAL = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)
_FORBIDDEN_KEYS = frozenset({
    "script", "scripts", "command", "commands", "exec", "execute",
    "executable", "code", "url", "uri", "href", "src", "event_handler",
})
_EVENT_HANDLER_KEY = re.compile(
    r"on(?:abort|animationend|animationiteration|animationstart|beforeinput|blur|"
    r"change|click|contextmenu|dblclick|drag|dragend|dragenter|dragleave|dragover|"
    r"dragstart|drop|error|focus|input|keydown|keypress|keyup|load|mousedown|"
    r"mouseenter|mouseleave|mousemove|mouseout|mouseover|mouseup|pointerdown|"
    r"pointerenter|pointerleave|pointermove|pointerout|pointerover|pointerup|"
    r"reset|resize|scroll|submit|touchcancel|touchend|touchmove|touchstart|"
    r"transitionend|wheel)\Z",
    re.IGNORECASE | re.ASCII,
)
_FORBIDDEN_TEXT = ("javascript:", "data:text/html", "<script", "cmd.exe",
                   "powershell", "file://")


class PrototypeTemplateCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TemplateArtifactRef:
    artifact_kind: str
    target_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CreateProjectPrototypeTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreateGlobalPrototypeTemplate:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    name: str
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrototypeTemplateInitialView:
    prototype_template_id: uuid.UUID
    prototype_template_version_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    name: str
    version_no: int
    layout_contract: dict[str, object]
    component_contract: dict[str, object]
    applicable_terminals: tuple[str, ...]
    artifact_refs: tuple[TemplateArtifactRef, ...]
    content_fingerprint: str
    created_at: datetime
    template_state: str = "ACTIVE"
    version_state: str = "PUBLISHED"
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (
            type(self.prototype_template_id) is not uuid.UUID
            or self.prototype_template_id.int == 0
            or type(self.prototype_template_version_id) is not uuid.UUID
            or self.prototype_template_version_id.int == 0
            or self.scope not in {"GLOBAL", "PROJECT"}
            or (self.scope == "GLOBAL" and self.project_id is not None)
            or (self.scope == "PROJECT" and (
                type(self.project_id) is not uuid.UUID or self.project_id.int == 0
            ))
            or type(self.name) is not str or not self.name
            or self.version_no != 1
            or type(self.layout_contract) is not dict
            or type(self.component_contract) is not dict
            or type(self.applicable_terminals) is not tuple
            or type(self.artifact_refs) is not tuple
            or not re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint)
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
            or self.template_state != "ACTIVE"
            or self.version_state != "PUBLISHED"
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial PrototypeTemplate view")


class ProjectAccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes, csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class AdminAccessPort(Protocol):
    def authorized_admin(
        self, transaction: object, *, session_token: bytes, csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(
        self, transaction: object, *, result_id: uuid.UUID,
        template_id: uuid.UUID, version_id: uuid.UUID, scope: str,
        project_id: uuid.UUID | None, name: str,
        layout_contract: dict[str, object], component_contract: dict[str, object],
        applicable_terminals: tuple[str, ...],
        artifact_refs: tuple[TemplateArtifactRef, ...],
        content_fingerprint: bytes, actor_id: uuid.UUID,
    ) -> PrototypeTemplateInitialView: ...

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
    ) -> PrototypeTemplateInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class PrototypeTemplateCreateService:
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
            raise ValueError("PrototypeTemplate create dependencies are required")
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

    def create_project(
        self, command: CreateProjectPrototypeTemplate,
    ) -> PrototypeTemplateInitialView:
        return self._execute(command, scope="PROJECT", project_id=command.project_id)

    def create_global(
        self, command: CreateGlobalPrototypeTemplate,
    ) -> PrototypeTemplateInitialView:
        return self._execute(command, scope="GLOBAL", project_id=None)

    def _execute(
        self, command: CreateProjectPrototypeTemplate | CreateGlobalPrototypeTemplate,
        *, scope: str, project_id: uuid.UUID | None,
    ) -> PrototypeTemplateInitialView:
        self._validate(command, scope, project_id)
        name = self._name(command.name)
        layout = self._contract(command.layout_contract)
        components = self._contract(command.component_contract)
        terminals = self._terminals(command.applicable_terminals)
        artifacts = self._artifacts(command.artifact_refs)
        operation = f"V1_PRT_TEMPLATE_{scope}_CREATE"
        request_fingerprint = canonical_payload_fingerprint({
            "scope": scope, "project_id": None if project_id is None else str(project_id),
            "name": name, "layout_contract": layout,
            "component_contract": components,
            "applicable_terminals": list(terminals),
            "artifact_refs": [{"artifact_kind": item.artifact_kind,
                               "target_id": str(item.target_id)} for item in artifacts],
        })
        try:
            validate_idempotency_key(command.idempotency_key)
            template_id = uuid.UUID(new_uuid7())
            version_id = uuid.UUID(new_uuid7())
            result_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                self._authorize(tx, command, scope=scope, project_id=project_id)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._authorize(
                    tx, command, scope=scope, project_id=project_id,
                )
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
                        raise PrototypeTemplateCreateError("PROTOTYPE_UNAVAILABLE")
                    view = self._repository.result(tx, result_id=previous.ref_id)
                    if not self._matches(view, scope, project_id, name, layout,
                                         components, terminals, artifacts):
                        raise PrototypeTemplateCreateError("PROTOTYPE_UNAVAILABLE")
                    return view
                artifact_digests: list[dict[str, str]] = []
                for artifact in artifacts:
                    if artifact.artifact_kind != "DOCUMENT_VERSION":
                        raise PrototypeTemplateCreateError(
                            "PROTOTYPE_ARTIFACT_UNAVAILABLE"
                        )
                    proof = self._documents.prove(
                        tx, template_scope=scope, project_id=project_id,
                        document_version_id=artifact.target_id,
                    )
                    if proof is None or proof.document_version_id != artifact.target_id:
                        raise PrototypeTemplateCreateError(
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
                view = self._repository.create(
                    tx, result_id=result_id, template_id=template_id,
                    version_id=version_id, scope=scope, project_id=project_id,
                    name=name, layout_contract=layout,
                    component_contract=components,
                    applicable_terminals=terminals, artifact_refs=artifacts,
                    content_fingerprint=content_fingerprint, actor_id=actor,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="DEPLOYMENT" if scope == "GLOBAL" else "PROJECT",
                    target_project_id=project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="PROTOTYPE_TEMPLATE_CREATED", outcome="SUCCESS",
                    target_owner_module="prototype", target_object_type="PRT-04",
                    target_object_id=template_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=receipt_scope,
                    result=IdempotencyResult(operation, result_id, 201),
                )
                tx.commit()
                return view
        except PrototypeTemplateCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeTemplateCreateError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeTemplateCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeTemplateCreateError(error.code) from None
        except Exception:
            raise PrototypeTemplateCreateError("PROTOTYPE_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: object, scope: str, project_id: uuid.UUID | None) -> None:
        if (
            type(command) not in (
                CreateProjectPrototypeTemplate, CreateGlobalPrototypeTemplate,
            )
            or type(command.session_token) is not bytes
            or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes
            or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID
            or command.trace_id.int == 0
            or (scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0
            ))
            or (scope == "GLOBAL" and project_id is not None)
        ):
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (
            not 1 <= len(result) <= 255
            or any(unicodedata.category(char)[0] == "C" for char in result)
        ):
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        return result

    @classmethod
    def _contract(cls, value: object) -> dict[str, object]:
        if type(value) is not dict:
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        nodes = [0]

        def visit(item: object, depth: int) -> None:
            nodes[0] += 1
            if depth > 8 or nodes[0] > 2000:
                raise PrototypeTemplateCreateError("VALIDATION_FAILED")
            if item is None or type(item) in (bool, int):
                return
            if type(item) is float:
                if not math.isfinite(item):
                    raise PrototypeTemplateCreateError("VALIDATION_FAILED")
                return
            if type(item) is str:
                if (
                    len(item) > 4096
                    or any(unicodedata.category(char)[0] == "C" for char in item)
                    or any(marker in item.casefold() for marker in _FORBIDDEN_TEXT)
                ):
                    raise PrototypeTemplateCreateError("VALIDATION_FAILED")
                return
            if type(item) is list:
                if len(item) > 500:
                    raise PrototypeTemplateCreateError("VALIDATION_FAILED")
                for child in item:
                    visit(child, depth + 1)
                return
            if type(item) is dict:
                if len(item) > 500:
                    raise PrototypeTemplateCreateError("VALIDATION_FAILED")
                for key, child in item.items():
                    if (
                        type(key) is not str or not _KEY.fullmatch(key)
                        or key.casefold() in _FORBIDDEN_KEYS
                        or _EVENT_HANDLER_KEY.fullmatch(key) is not None
                    ):
                        raise PrototypeTemplateCreateError("VALIDATION_FAILED")
                    visit(child, depth + 1)
                return
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")

        visit(value, 0)
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > 65536:
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        return json.loads(encoded.decode("utf-8"))

    @staticmethod
    def _terminals(value: object) -> tuple[str, ...]:
        if (
            type(value) is not tuple or not 1 <= len(value) <= 16
            or any(type(item) is not str or not _TERMINAL.fullmatch(item)
                   for item in value)
            or len(set(value)) != len(value)
        ):
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        return tuple(sorted(value))

    @staticmethod
    def _artifacts(value: object) -> tuple[TemplateArtifactRef, ...]:
        if (
            type(value) is not tuple or len(value) > 100
            or any(
                type(item) is not TemplateArtifactRef
                or item.artifact_kind not in {"DOCUMENT_VERSION", "OUTPUT_ARTIFACT"}
                or type(item.target_id) is not uuid.UUID or item.target_id.int == 0
                for item in value
            )
        ):
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        ordered = tuple(sorted(value, key=lambda item: (
            item.artifact_kind, str(item.target_id),
        )))
        if len({(item.artifact_kind, item.target_id) for item in ordered}) != len(ordered):
            raise PrototypeTemplateCreateError("VALIDATION_FAILED")
        return ordered

    def _authorize(
        self, tx: object,
        command: CreateProjectPrototypeTemplate | CreateGlobalPrototypeTemplate,
        *, scope: str, project_id: uuid.UUID | None,
    ) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeTemplateCreateError("PROTOTYPE_UNAVAILABLE")
        now = now.astimezone(timezone.utc)
        if scope == "GLOBAL":
            actor = self._admin_access.authorized_admin(
                tx, session_token=command.session_token,
                csrf_token=command.csrf_token, now=now,
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise PrototypeTemplateCreateError("AUTH_ACCESS_DENIED")
            return actor
        actor = self._project_access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeTemplateCreateError("AUTH_ACCESS_DENIED")
        authorized = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=project_id,
            operation="PRT_TEMPLATE_CREATE",
        )
        if (
            authorized.user_id != actor or authorized.project_id != project_id
            or authorized.operation != "PRT_TEMPLATE_CREATE"
        ):
            raise PrototypeTemplateCreateError("RESOURCE_NOT_FOUND")
        return actor

    @staticmethod
    def _matches(
        view: PrototypeTemplateInitialView | None, scope: str,
        project_id: uuid.UUID | None, name: str,
        layout: dict[str, object], components: dict[str, object],
        terminals: tuple[str, ...], artifacts: tuple[TemplateArtifactRef, ...],
    ) -> bool:
        return (
            type(view) is PrototypeTemplateInitialView
            and view.scope == scope and view.project_id == project_id
            and view.name == name and view.layout_contract == layout
            and view.component_contract == components
            and view.applicable_terminals == terminals
            and view.artifact_refs == artifacts
        )
