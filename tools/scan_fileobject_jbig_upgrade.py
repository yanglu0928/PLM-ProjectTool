"""Maintenance-fenced, read-only FileObject TIFF compatibility preflight.

No customer filename, path, locator, database URL, or content is emitted.
This does not perform an upgrade, backup, or data conversion.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src"))
from plm_assistant.modules.document.infrastructure.local_storage import (  # noqa: E402
    LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (  # noqa: E402
    MAINTENANCE_LOCK_KEY,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (  # noqa: E402
    read_database_url,
)
from plm_assistant.modules.platform.infrastructure.database import (  # noqa: E402
    validate_database_url,
)
from scan_tiff_jbig_preflight import UnsupportedTiff, inspect_stream


MAX_FILE_BYTES = 100_000_000
TIFF_MAGIC = (b"II*\0", b"MM\0*", b"II+\0", b"MM\0+")
READ_SQL = text(
    "SELECT file_object_id,scope,project_id,storage_class,storage_locator,"
    "original_name_metadata,sha256,size_bytes,detected_mime,file_state "
    "FROM plm.doc_file_objects WHERE usage_kind='DOCUMENT' ORDER BY file_object_id"
)
STATE_SQL = text(
    "SELECT state,lock_version FROM plm.plt_maintenance_state WHERE state_id=1"
)


class PreflightUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Counts:
    registered: int = 0
    verified: int = 0
    tiff_clear: int = 0
    jbig: int = 0
    unknown: int = 0
    non_tiff: int = 0
    terminal_skipped: int = 0

    def add(self, field: str) -> "Counts":
        values = self.__dict__.copy()
        values[field] += 1
        return Counts(**values)

    def report(self) -> dict[str, Any]:
        status = "BLOCK_JBIG" if self.jbig else "BLOCK_UNKNOWN" if self.unknown else "CLEAR"
        return {"status": status, "upgrade_allowed": status == "CLEAR", **self.__dict__}


def inspect_record(row: Any, storage: LocalFileStorage) -> str:
    """Return TIFF_CLEAR/JBIG/NON_TIFF/TERMINAL_SKIP or UNKNOWN."""
    try:
        if row.file_state == "REMOVED":
            return "TERMINAL_SKIP"
        if row.file_state not in ("AVAILABLE", "RESTRICTED"):
            return "UNKNOWN"
        if (row.storage_class != "PERSISTENT" or type(row.file_object_id) is not uuid.UUID
                or type(row.sha256) is not bytes or len(row.sha256) != 32
                or type(row.size_bytes) is not int or not 0 <= row.size_bytes <= MAX_FILE_BYTES):
            return "UNKNOWN"
        _, expected = storage.locators(scope=row.scope, project_id=row.project_id,
                                       file_object_id=row.file_object_id)
        if row.storage_locator != expected:
            return "UNKNOWN"
        with storage.open_verified_snapshot(row.storage_locator,
                                            expected_sha256=row.sha256,
                                            expected_size=row.size_bytes,
                                            max_bytes=MAX_FILE_BYTES) as snapshot:
            magic = snapshot.read(4)
            snapshot.seek(0)
            declared_tiff = (isinstance(row.detected_mime, str)
                             and row.detected_mime.lower() in ("image/tiff", "image/tif"))
            named_tiff = (isinstance(row.original_name_metadata, str)
                          and row.original_name_metadata.lower().endswith((".tif", ".tiff")))
            if magic not in TIFF_MAGIC:
                return "UNKNOWN" if declared_tiff or named_tiff else "NON_TIFF"
            return "JBIG" if inspect_stream(snapshot) else "TIFF_CLEAR"
    except (LocalStorageError, UnsupportedTiff, OSError, ValueError, TypeError):
        return "UNKNOWN"


class MaintenanceWindow:
    """One held session fence; no method authorizes OS or backup requirements."""

    def __init__(self, connection: Connection, lock_version: int) -> None:
        self._connection = connection
        self._lock_version = lock_version

    def verify(self) -> None:
        try:
            row = self._connection.execute(STATE_SQL).one_or_none()
            if (row is None or row.state != "MAINTENANCE"
                    or row.lock_version != self._lock_version):
                raise PreflightUnavailable("maintenance state changed")
            self._connection.commit()
        except PreflightUnavailable:
            self._connection.rollback()
            raise
        except Exception:
            self._connection.rollback()
            raise PreflightUnavailable("maintenance state unavailable") from None

    def scan(self, storage: LocalFileStorage) -> dict[str, Any]:
        if not isinstance(storage, LocalFileStorage):
            raise PreflightUnavailable("storage unavailable")
        connection = self._connection
        try:
            connection.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            state = connection.execute(STATE_SQL).one_or_none()
            if (state is None or state.state != "MAINTENANCE"
                    or state.lock_version != self._lock_version):
                raise PreflightUnavailable("maintenance state changed")
            expected = connection.scalar(text(
                "SELECT count(*) FROM plm.doc_file_objects WHERE usage_kind='DOCUMENT'"))
            if type(expected) is not int or expected < 0:
                raise PreflightUnavailable("FileObject inventory count unavailable")
            counts = Counts()
            rows = connection.execution_options(stream_results=True, yield_per=1000).execute(READ_SQL)
            try:
                for row in rows:
                    counts = counts.add("registered")
                    outcome = inspect_record(row, storage)
                    if outcome == "TERMINAL_SKIP":
                        counts = counts.add("terminal_skipped")
                    elif outcome == "UNKNOWN":
                        counts = counts.add("unknown")
                    else:
                        counts = counts.add("verified")
                        column = {"TIFF_CLEAR": "tiff_clear", "JBIG": "jbig",
                                  "NON_TIFF": "non_tiff"}[outcome]
                        counts = counts.add(column)
            finally:
                rows.close()
            if counts.registered != expected:
                raise PreflightUnavailable("FileObject inventory count changed")
            connection.commit()
            self.verify()
            return counts.report()
        except PreflightUnavailable:
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise PreflightUnavailable("FileObject preflight unavailable") from None


@contextmanager
def maintenance_window(engine: Engine) -> Iterator[MaintenanceWindow]:
    """Keep the same exclusive PostgreSQL session lock across caller operations."""
    if not isinstance(engine, Engine):
        raise PreflightUnavailable("PostgreSQL engine unavailable")
    connection = None
    locked = False
    try:
        connection = engine.connect()
        if (connection.dialect.name != "postgresql"
                or connection.dialect.server_version_info[:1] != (18,)):
            raise PreflightUnavailable("PostgreSQL 18 required")
        locked = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"),
                                   {"key": MAINTENANCE_LOCK_KEY}) is True
        connection.commit()
        if not locked:
            raise PreflightUnavailable("maintenance fence busy")
        state = connection.execute(STATE_SQL).one_or_none()
        if state is None or state.state != "MAINTENANCE":
            raise PreflightUnavailable("maintenance mode required")
        version = state.lock_version
        connection.commit()
        yield MaintenanceWindow(connection, version)
    except PreflightUnavailable:
        raise
    except Exception:
        raise PreflightUnavailable("FileObject preflight unavailable") from None
    finally:
        if connection is not None:
            try:
                connection.rollback()
                if locked:
                    released = connection.scalar(text("SELECT pg_advisory_unlock(:key)"),
                                                 {"key": MAINTENANCE_LOCK_KEY})
                    connection.commit()
                    if released is not True:
                        connection.invalidate()
                        raise PreflightUnavailable("maintenance fence release failed")
            finally:
                connection.close()


def audit(engine: Engine, storage: LocalFileStorage) -> dict[str, Any]:
    """One-shot read-only scan, preserving the existing CLI behavior."""
    with maintenance_window(engine) as window:
        return window.scan(storage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    engine = None
    try:
        storage = LocalFileStorage(args.data_root)
        engine = create_engine(validate_database_url(read_database_url()),
                               pool_pre_ping=True, hide_parameters=True,
                               connect_args={"connect_timeout": 5,
                                             "application_name": "plm-tiff-upgrade-preflight"})
        result = audit(engine, storage)
    except Exception:
        result = {"status": "BLOCK_UNAVAILABLE", "upgrade_allowed": False}
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(result))
    return 0 if result["upgrade_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
