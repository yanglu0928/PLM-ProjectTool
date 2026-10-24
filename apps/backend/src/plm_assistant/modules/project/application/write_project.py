"""Internal Project metadata and one-way archive commands."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.read_projects import ProjectView


class ProjectWriteError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchProjectName:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    expected_version: int
    name: str


@dataclass(frozen=True, slots=True)
class ArchiveProject:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    expected_version: int


class ProjectWriteAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectWriteRepositoryPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID) -> ProjectView | None: ...
    def patch_name(self, transaction: object, *, project_id: uuid.UUID,
                   expected_version: int, name: str) -> ProjectView | None: ...
    def archive(self, transaction: object, *, project_id: uuid.UUID,
                expected_version: int) -> ProjectView | None: ...


class ProjectArchiveReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def _name(value: object) -> str:
    if type(value) is not str:
        raise ProjectWriteError("VALIDATION_FAILED")
    result = unicodedata.normalize("NFKC", value).strip()
    if not 1 <= len(result) <= 255 or any(unicodedata.category(char)[0] == "C" for char in result):
        raise ProjectWriteError("VALIDATION_FAILED")
    return result


class ProjectWriteService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectWriteAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectWriteRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None,
                 receipts: ProjectArchiveReceiptPort | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("Project write dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._receipts = receipts

    def patch_name(self, command: PatchProjectName) -> ProjectView:
        self._validate(command, PatchProjectName)
        name = _name(command.name)
        return self._execute(command, "PROJECT_PATCH", "PROJECT_PATCHED",
                             lambda tx: self._repository.patch_name(
                                 tx, project_id=command.project_id,
                                 expected_version=command.expected_version, name=name,
                             ))

    def archive(self, command: ArchiveProject) -> ProjectView:
        self._validate(command, ArchiveProject)
        return self._execute(command, "PROJECT_ARCHIVE", "PROJECT_ARCHIVED",
                             lambda tx: self._repository.archive(
                                 tx, project_id=command.project_id,
                                 expected_version=command.expected_version,
                             ))

    def archive_idempotent(self, command: ArchiveProject, *, idempotency_key: str) -> ProjectView:
        if self._receipts is None:
            raise ProjectWriteError("PROJECT_UNAVAILABLE")
        self._validate(command, ArchiveProject)
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "expected_version": command.expected_version,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise ProjectWriteError("PROJECT_UNAVAILABLE")
                user_id = self._access.authenticated_user(
                    tx, session_token=command.session_token, csrf_token=command.csrf_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(user_id) is not uuid.UUID or user_id.int == 0:
                    raise ProjectWriteError("AUTH_ACCESS_DENIED")
                try:
                    self._authorization.require_archive_replay_in_transaction(
                        tx, user_id=user_id, project_id=command.project_id,
                    )
                except ProjectAuthorizationError as exc:
                    raise ProjectWriteError(exc.code) from None
                scope = IdempotencyScope.from_key(
                    actor_id=user_id, project_id=command.project_id,
                    operation="V1_PROJECT_ARCHIVE", key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != "V1_PROJECT_ARCHIVE"
                            or replay.ref_id != command.project_id or replay.status_code != 200):
                        raise ProjectWriteError("PROJECT_UNAVAILABLE")
                    view = self._repository.get(tx, project_id=command.project_id)
                    if (type(view) is not ProjectView or view.state != "ARCHIVED"
                            or view.etag != f'"v{command.expected_version + 1}"'):
                        raise ProjectWriteError("PROJECT_UNAVAILABLE")
                    return view
                try:
                    self._authorization.require_in_transaction(
                        tx, user_id=user_id, project_id=command.project_id,
                        operation="PROJECT_ARCHIVE",
                    )
                except ProjectAuthorizationError as exc:
                    raise ProjectWriteError(exc.code) from None
                view = self._repository.archive(
                    tx, project_id=command.project_id,
                    expected_version=command.expected_version,
                )
                if type(view) is not ProjectView:
                    raise ProjectWriteError("CONFLICT_VERSION")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=user_id,
                    original_actor_id=None, actor_hint_digest=None, action="PROJECT_ARCHIVED",
                    outcome="SUCCESS", target_owner_module="project",
                    target_object_type="PRJ-01", target_object_id=command.project_id,
                    before_state="ACTIVE", after_state="ARCHIVED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_PROJECT_ARCHIVE", command.project_id, 200),
                )
                tx.commit()
                return view
        except IdempotencyError as exc:
            raise ProjectWriteError(exc.code) from None

    @staticmethod
    def _validate(command: object, command_type: type) -> None:
        if (type(command) is not command_type
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise ProjectWriteError("VALIDATION_FAILED")

    def _execute(self, command: PatchProjectName | ArchiveProject, operation: str,
                 action: str, mutation: Callable[[object], ProjectView | None]) -> ProjectView:
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectWriteError("PROJECT_UNAVAILABLE")
            user_id = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(user_id) is not uuid.UUID or user_id.int == 0:
                raise ProjectWriteError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=user_id, project_id=command.project_id, operation=operation,
                )
            except ProjectAuthorizationError as exc:
                raise ProjectWriteError(exc.code) from None
            result = mutation(tx)
            if type(result) is not ProjectView:
                raise ProjectWriteError("CONFLICT_VERSION")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="PROJECT",
                target_project_id=command.project_id, actor_type="USER", actor_id=user_id,
                original_actor_id=None, actor_hint_digest=None, action=action,
                outcome="SUCCESS", target_owner_module="project",
                target_object_type="PRJ-01", target_object_id=command.project_id,
                before_state="ACTIVE", after_state=result.state,
            ))
            tx.commit()
            return result
