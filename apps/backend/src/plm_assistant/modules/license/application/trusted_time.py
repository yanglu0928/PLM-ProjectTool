"""Internal trusted-time port; only a fully validated License may call advance."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft


class TrustedTimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TrustedTimeRecord:
    state_id: uuid.UUID
    last_successful_time: datetime | None
    state_version: int
    integrity_metadata: dict[str, str] | None
    last_event_ref: uuid.UUID | None


class TrustedTimeRepositoryPort(Protocol):
    def read_locked(self, transaction: object) -> TrustedTimeRecord | None: ...
    def append_event(self, transaction: object, *, code: str, candidate: datetime,
                     trace_id: uuid.UUID) -> uuid.UUID: ...
    def advance(self, transaction: object, *, expected_version: int, state_id: uuid.UUID,
                candidate: datetime, event_id: uuid.UUID,
                integrity_metadata: dict[str, str]) -> bool: ...


class TrustedTimeIntegrityPort(Protocol):
    def sign(self, record: TrustedTimeRecord) -> dict[str, str]: ...
    def verify(self, record: TrustedTimeRecord) -> bool: ...


class UnitOfWorkPort(Protocol):
    def __enter__(self) -> UnitOfWorkPort: ...
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool: ...
    def commit(self) -> None: ...


class TrustedTimeStatePort:
    """Fail-closed monotonic state transition with durable audit on denials."""

    def __init__(self, unit_of_work: Callable[[], UnitOfWorkPort],
                 repository: TrustedTimeRepositoryPort, integrity: TrustedTimeIntegrityPort,
                 audit: AuditService) -> None:
        if any(value is None for value in (unit_of_work, repository, integrity, audit)):
            raise ValueError("trusted-time dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._integrity = integrity
        self._audit = audit

    def current_verified_version(self) -> int:
        """Read the current monotonic version only after integrity verification."""
        try:
            with self._unit_of_work() as tx:
                state = self._repository.read_locked(tx)
                if state is None or not self._integrity.verify(state):
                    raise TrustedTimeError("TRUST_STATE_INVALID")
                return state.state_version
        except TrustedTimeError:
            raise
        except Exception:
            raise TrustedTimeError("TRUST_STATE_INVALID") from None

    def advance(self, *, candidate: datetime, expected_version: int,
                trace_id: uuid.UUID, rollback_tolerance: timedelta = timedelta(0)) -> TrustedTimeRecord:
        if (not isinstance(candidate, datetime) or candidate.tzinfo is None
                or candidate.utcoffset() is None or type(expected_version) is not int
                or expected_version < 0 or type(trace_id) is not uuid.UUID or trace_id.int == 0
                or not isinstance(rollback_tolerance, timedelta)
                or not timedelta(0) <= rollback_tolerance <= timedelta(minutes=5)):
            raise TrustedTimeError("TRUST_STATE_INVALID")
        current = candidate.astimezone(timezone.utc)
        try:
            with self._unit_of_work() as tx:
                state = self._repository.read_locked(tx)
                if state is None:
                    raise TrustedTimeError("TRUST_STATE_INVALID")
                if not self._integrity.verify(state):
                    raise TrustedTimeError("TRUST_STATE_INVALID")
                if state.state_version != expected_version:
                    raise TrustedTimeError("TRUST_STATE_CONFLICT")
                previous = state.last_successful_time
                if previous is not None and current < previous - rollback_tolerance:
                    raise TrustedTimeError("TIME_ROLLBACK")
                if previous is not None and current <= previous:
                    self._repository.append_event(tx, code="WITHIN_TOLERANCE", candidate=current, trace_id=trace_id)
                    self._audit.append(tx, _audit(trace_id, "SUCCESS", "WITHIN_TOLERANCE", state.state_id))
                    tx.commit()
                    return state
                event_id = self._repository.append_event(tx, code="ADVANCED", candidate=current, trace_id=trace_id)
                updated = TrustedTimeRecord(state.state_id, current, state.state_version + 1, None, event_id)
                metadata = self._integrity.sign(updated)
                if not self._repository.advance(tx, expected_version=expected_version,
                                                state_id=state.state_id, candidate=current,
                                                event_id=event_id, integrity_metadata=metadata):
                    raise TrustedTimeError("TRUST_STATE_CONFLICT")
                self._audit.append(tx, _audit(trace_id, "SUCCESS", "ADVANCED", state.state_id))
                tx.commit()
                return TrustedTimeRecord(state.state_id, current, state.state_version + 1, metadata, event_id)
        except TrustedTimeError as exc:
            self._record_denial(exc.code, current, trace_id)
            raise
        except Exception:
            self._record_denial("TRUST_STATE_INVALID", current, trace_id)
            raise TrustedTimeError("TRUST_STATE_INVALID") from None

    def _record_denial(self, code: str, candidate: datetime, trace_id: uuid.UUID) -> None:
        event_code = {"TIME_ROLLBACK": "ROLLBACK_REJECTED",
                      "TRUST_STATE_CONFLICT": "CONFLICT_REJECTED"}.get(code, "INTEGRITY_REJECTED")
        try:
            with self._unit_of_work() as tx:
                self._repository.append_event(tx, code=event_code, candidate=candidate, trace_id=trace_id)
                self._audit.append(tx, _audit(trace_id, "DENIED", code, None))
                tx.commit()
        except Exception:
            raise TrustedTimeError("TRUST_STATE_INVALID") from None


def _audit(trace_id: uuid.UUID, outcome: str, reason: str,
           state_id: uuid.UUID | None) -> AuditEventDraft:
    return AuditEventDraft(
        trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
        actor_type="UNRESOLVED", actor_id=None, original_actor_id=None,
        actor_hint_digest=None, action="LICENSE_TRUSTED_TIME_CHECK",
        outcome=outcome, reason_code=reason,
        target_owner_module="license" if state_id else None,
        target_object_type="LIC-03" if state_id else None,
        target_object_id=state_id,
    )
