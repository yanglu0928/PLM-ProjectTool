"""Read-only PG18 admission: hold one session lock across the caller's I/O."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


# Fixed product-local advisory namespace, shared with the future transition Port.
MAINTENANCE_LOCK_KEY = 0x504C4D544F4F4C01


class MaintenanceAdmissionError(RuntimeError):
    def __init__(self, code: str = "MAINTENANCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MaintenanceAdmissionSnapshot:
    lock_version: int
    changed_at: datetime

    def __post_init__(self) -> None:
        if (type(self.lock_version) is not int or self.lock_version < 0
                or type(self.changed_at) is not datetime
                or self.changed_at.tzinfo is None
                or self.changed_at.utcoffset() is None):
            raise MaintenanceAdmissionError()


class PostgresMaintenanceAdmission:
    """Supplied Engine remains caller-owned; this Port never toggles state."""

    def __init__(self, engine: Engine) -> None:
        if not isinstance(engine, Engine):
            raise ValueError("Explicit PostgreSQL admission engine required")
        self._engine = engine

    @contextmanager
    def admit(self) -> Iterator[MaintenanceAdmissionSnapshot]:
        connection: Connection | None = None
        locked = False
        try:
            connection = self._engine.connect()
            if (connection.dialect.name != "postgresql"
                    or connection.dialect.server_version_info[:1] != (18,)):
                raise MaintenanceAdmissionError()
            acquired = connection.scalar(text(
                "SELECT pg_try_advisory_lock_shared(:key)"),
                {"key": MAINTENANCE_LOCK_KEY})
            connection.commit()  # Session lock survives; no long transaction.
            if acquired is not True:
                raise MaintenanceAdmissionError("MAINTENANCE_BUSY")
            locked = True
            row = connection.execute(text(
                "SELECT state_id,state,lock_version,changed_at "
                "FROM plm.plt_maintenance_state WHERE state_id=1"
            )).one_or_none()
            connection.commit()
            if row is None or row.state_id != 1:
                raise MaintenanceAdmissionError()
            if row.state != "RUNNING":
                raise MaintenanceAdmissionError("MAINTENANCE_ACTIVE")
            snapshot = MaintenanceAdmissionSnapshot(row.lock_version, row.changed_at)
            snapshot.__post_init__()
        except MaintenanceAdmissionError:
            if connection is not None:
                self._release(connection, locked)
            raise
        except Exception:
            if connection is not None:
                self._release(connection, locked)
            raise MaintenanceAdmissionError() from None
        try:
            yield snapshot
        finally:
            self._release(connection, True)

    @staticmethod
    def _release(connection: Connection, locked: bool) -> None:
        try:
            if locked:
                connection.rollback()
                released = connection.scalar(text(
                    "SELECT pg_advisory_unlock_shared(:key)"),
                    {"key": MAINTENANCE_LOCK_KEY})
                connection.commit()
                if released is not True:
                    raise MaintenanceAdmissionError()
        except Exception:
            connection.invalidate()
            raise MaintenanceAdmissionError() from None
        finally:
            connection.close()
