"""Explicit, administrator-authorized creation of the empty trusted-time state."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.installation_import import LicenseImportAccessPort


class TrustedTimeInitializationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InitializeTrustedTime:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID


class TrustedTimeInitializationRepositoryPort(Protocol):
    def create_pristine(self, transaction: object) -> uuid.UUID | None: ...


class TrustedTimeInitializationService:
    """Never repairs or replaces a missing/corrupt state with existing history."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: LicenseImportAccessPort,
                 repository: TrustedTimeInitializationRepositoryPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, repository, audit)):
            raise ValueError("trusted-time initialization dependencies are required")
        self._unit_of_work, self._access = unit_of_work, access
        self._repository, self._audit = repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize_once(self, command: InitializeTrustedTime) -> uuid.UUID:
        if (type(command) is not InitializeTrustedTime
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise TrustedTimeInitializationError("VALIDATION_FAILED")
        try:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("timezone required")
            with self._unit_of_work() as tx:
                actor = self._access.authorized_admin(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise TrustedTimeInitializationError("AUTH_ACCESS_DENIED")
                state_id = self._repository.create_pristine(tx)
                if state_id is None:
                    raise TrustedTimeInitializationError("TRUST_STATE_CONFLICT")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="LICENSE_TRUSTED_TIME_INITIALIZED", outcome="SUCCESS",
                    target_owner_module="license", target_object_type="LIC-03",
                    target_object_id=state_id,
                ))
                tx.commit()
                return state_id
        except TrustedTimeInitializationError:
            raise
        except Exception:
            raise TrustedTimeInitializationError("TRUST_STATE_INVALID") from None
