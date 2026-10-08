"""Atomic authorized creation of a logical SolutionSection identity."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.exc import IntegrityError

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


_OPERATION = "V1_SOL_SECTION_CREATE"


class SectionCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSection:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    outline_id: uuid.UUID
    section_key: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SectionInitialView:
    solution_section_id: uuid.UUID
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    section_key: str
    created_at: datetime
    section_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (type(self.solution_section_id) is not uuid.UUID
                or self.solution_section_id.int == 0
                or type(self.solution_outline_id) is not uuid.UUID
                or self.solution_outline_id.int == 0
                or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
                or type(self.section_key) is not str or not self.section_key
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
                or self.section_state != "ACTIVE"
                or self.current_approved_version_ref is not None
                or self.etag != '"v0"'):
            raise ValueError("invalid initial SolutionSection view")


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def require_active_outline(self, transaction: object, *, project_id: uuid.UUID,
                               outline_id: uuid.UUID) -> bool: ...

    def create(self, transaction: object, *, section_id: uuid.UUID, project_id: uuid.UUID,
               outline_id: uuid.UUID, section_key: str, actor_id: uuid.UUID) -> SectionInitialView: ...

    def first_result(self, transaction: object, *, section_id: uuid.UUID,
                     project_id: uuid.UUID) -> SectionInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class SectionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort, authorization: ProjectAuthorizationService,
                 repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("SolutionSection create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repo = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSection) -> SectionInitialView:
        if (type(command) is not CreateSection
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.outline_id) is not uuid.UUID or command.outline_id.int == 0):
            raise SectionCreateError("VALIDATION_FAILED")
        key = self._key(command.section_key)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "outline_id": str(command.outline_id), "section_key": key,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_SECTION_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SOL_SECTION_CREATE"
                        or not self._repo.require_active_outline(
                            tx, project_id=command.project_id,
                            outline_id=command.outline_id)):
                    raise SectionCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise SectionCreateError()
                    result = self._repo.first_result(
                        tx, section_id=previous.ref_id, project_id=command.project_id)
                    if (result is None or result.solution_outline_id != command.outline_id
                            or result.section_key != key):
                        raise SectionCreateError()
                    return result
                section_id = uuid.UUID(new_uuid7())
                result = self._repo.create(
                    tx, section_id=section_id, project_id=command.project_id,
                    outline_id=command.outline_id, section_key=key, actor_id=actor)
                if (type(result) is not SectionInitialView
                        or result.solution_section_id != section_id
                        or result.project_id != command.project_id
                        or result.solution_outline_id != command.outline_id
                        or result.section_key != key):
                    raise SectionCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SOL_SECTION_CREATED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-04",
                    target_object_id=section_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, section_id, 201))
                tx.commit()
                return result
        except SectionCreateError:
            raise
        except (ProjectAuthorizationError, IdempotencyError) as error:
            raise SectionCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SectionCreateError("LICENSE_OPERATION_DENIED") from None
        except IntegrityError as error:
            if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_sol_sections__outline_key":
                raise SectionCreateError("CONFLICT_DUPLICATE") from None
            raise SectionCreateError() from None
        except Exception:
            raise SectionCreateError() from None

    @staticmethod
    def _key(value: object) -> str:
        if type(value) is not str:
            raise SectionCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= 128
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise SectionCreateError("VALIDATION_FAILED")
        return result

    def _actor(self, tx: object, command: CreateSection) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SectionCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SectionCreateError("AUTH_ACCESS_DENIED")
        return actor
