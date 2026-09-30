"""Internal PG18 maintenance transition; not a deployable operator entrypoint."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, MaintenanceAdmissionError,
)


@dataclass(frozen=True, slots=True)
class MaintenanceTransitionReceipt:
    state: str
    lock_version: int
    changed_at: datetime
    audit_event_id: uuid.UUID


class MaintenanceOperatorAccess(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class PostgresMaintenanceTransition:
    """Caller owns Engine; Auth verifies current Admin in the state transaction."""

    def __init__(self, engine: Engine, *, access: MaintenanceOperatorAccess) -> None:
        if not isinstance(engine, Engine) or access is None:
            raise ValueError("Explicit PostgreSQL engine and Auth access required")
        self._engine = engine
        self._access = access
        self._audit = AuditService(SqlAlchemyAuditRepository())

    def change(self, *, target: str, expected_version: int,
               session_token: bytes, csrf_token: bytes,
               wait_ms: int = 1000) -> MaintenanceTransitionReceipt:
        if target not in ("RUNNING", "MAINTENANCE"):
            raise ValueError("Invalid maintenance target")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("Invalid maintenance version")
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32):
            raise ValueError("Authenticated session and CSRF required")
        if type(wait_ms) is not int or not 1 <= wait_ms <= 30_000:
            raise ValueError("Invalid maintenance wait")
        previous = "RUNNING" if target == "MAINTENANCE" else "MAINTENANCE"
        connection = None
        locked = False
        committed = False
        try:
            connection = self._engine.connect()
            if (connection.dialect.name != "postgresql"
                    or connection.dialect.server_version_info[:1] != (18,)):
                raise MaintenanceAdmissionError()
            connection.scalar(text("SELECT set_config('lock_timeout', :timeout, true)"),
                              {"timeout": f"{wait_ms}ms"})
            connection.scalar(text("SELECT pg_advisory_lock(:key)"),
                              {"key": MAINTENANCE_LOCK_KEY})
            locked = True
            connection.commit()  # Retain session lock without a long transaction.

            def session_factory() -> Session:
                return Session(bind=connection, autoflush=False, autobegin=False)

            with SqlAlchemyUnitOfWork(session_factory) as uow:
                operator_id = self._access.authorized_admin(
                    uow, session_token=session_token, csrf_token=csrf_token,
                    now=datetime.now(timezone.utc))
                if type(operator_id) is not uuid.UUID or operator_id.int == 0:
                    raise MaintenanceAdmissionError("MAINTENANCE_ACCESS_DENIED")
                row = uow.session.execute(text(
                    "UPDATE plm.plt_maintenance_state SET state=:target, "
                    "lock_version=lock_version+1 WHERE state_id=1 AND state=:previous "
                    "AND lock_version=:version RETURNING state,lock_version,changed_at"
                ), {"target": target, "previous": previous,
                    "version": expected_version}).one_or_none()
                if row is None:
                    raise MaintenanceAdmissionError("MAINTENANCE_STATE_CONFLICT")
                event = AuditEventDraft(
                    trace_id=uuid.uuid4(), event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=operator_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="MAINTENANCE_ENTER" if target == "MAINTENANCE"
                    else "MAINTENANCE_EXIT", outcome="SUCCESS",
                    before_state=previous, after_state=target,
                )
                audit_event_id = self._audit.append(uow, event)
                receipt = MaintenanceTransitionReceipt(
                    row.state, row.lock_version, row.changed_at, audit_event_id)
                try:
                    uow.commit()
                    committed = True
                except Exception:
                    raise MaintenanceAdmissionError("MAINTENANCE_OUTCOME_UNKNOWN") from None
            return receipt
        except MaintenanceAdmissionError:
            raise
        except OperationalError as exc:
            if getattr(exc.orig, "sqlstate", None) == "55P03":
                raise MaintenanceAdmissionError("MAINTENANCE_BUSY") from None
            raise MaintenanceAdmissionError("MAINTENANCE_UNAVAILABLE") from None
        except Exception:
            raise MaintenanceAdmissionError(
                "MAINTENANCE_OUTCOME_UNKNOWN" if committed else "MAINTENANCE_UNAVAILABLE"
            ) from None
        finally:
            if connection is not None:
                try:
                    connection.rollback()
                    if locked:
                        released = connection.scalar(text("SELECT pg_advisory_unlock(:key)"),
                                                     {"key": MAINTENANCE_LOCK_KEY})
                        connection.commit()
                        if released is not True:
                            raise MaintenanceAdmissionError()
                except Exception as exc:
                    connection.invalidate()
                    raise MaintenanceAdmissionError() from exc
                finally:
                    connection.close()
