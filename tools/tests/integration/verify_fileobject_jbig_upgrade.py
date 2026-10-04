"""Isolated PostgreSQL 18/local-file rehearsal for upgrade TIFF preflight.

Requires a fresh temporary cluster; verifies the server data directory before DDL.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from scan_fileobject_jbig_upgrade import (  # noqa: E402
    LocalFileStorage, MAINTENANCE_LOCK_KEY, PreflightUnavailable, audit,
    maintenance_window,
)
from tools.tests.test_scan_tiff_jbig_preflight import classic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.port != 55483 or not args.data_dir.is_absolute():
        raise RuntimeError("fixed isolated cluster required")
    engine = create_engine(f"postgresql+psycopg://plmtest@127.0.0.1:{args.port}/postgres",
                           hide_parameters=True)
    try:
        with engine.connect() as connection:
            actual = Path(connection.scalar(text("SHOW data_directory"))).resolve()
            if actual != args.data_dir.resolve():
                raise RuntimeError("database is not the requested isolated cluster")
            if connection.scalar(text("SHOW server_version_num"))[:2] != "18":
                raise RuntimeError("PostgreSQL 18 required")
            connection.rollback()
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS plm")
            connection.exec_driver_sql("""CREATE TABLE IF NOT EXISTS plm.plt_maintenance_state (
                state_id smallint PRIMARY KEY, state text NOT NULL,
                lock_version bigint NOT NULL)""")
            connection.exec_driver_sql("""CREATE TABLE IF NOT EXISTS plm.doc_file_objects (
                file_object_id uuid PRIMARY KEY, usage_kind text NOT NULL,
                scope text NOT NULL, project_id uuid, storage_class text NOT NULL,
                storage_locator text NOT NULL, original_name_metadata text NOT NULL,
                sha256 bytea, size_bytes bigint, detected_mime text, file_state text NOT NULL)""")
            connection.exec_driver_sql("TRUNCATE plm.doc_file_objects")
            connection.exec_driver_sql("DELETE FROM plm.plt_maintenance_state")
            connection.execute(text("INSERT INTO plm.plt_maintenance_state VALUES (1,'MAINTENANCE',1)"))
        with tempfile.TemporaryDirectory(prefix="plm-jbig-upgrade-data-") as temporary:
            storage = LocalFileStorage(Path(temporary))

            def insert(data: bytes, state: str = "AVAILABLE") -> uuid.UUID:
                file_id = uuid.uuid4()
                _, locator = storage.locators(scope="GLOBAL", project_id=None,
                                               file_object_id=file_id)
                path = Path(temporary).joinpath(*locator.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                with engine.begin() as connection:
                    connection.execute(text("""INSERT INTO plm.doc_file_objects
                        (file_object_id,usage_kind,scope,project_id,storage_class,
                         storage_locator,original_name_metadata,sha256,size_bytes,
                         detected_mime,file_state)
                        VALUES (:id,'DOCUMENT','GLOBAL',NULL,'PERSISTENT',:locator,
                                'synthetic.bin',:sha,:size,'application/octet-stream',:state)"""),
                        {"id": file_id, "locator": locator,
                         "sha": hashlib.sha256(data).digest(), "size": len(data),
                         "state": state})
                return file_id

            insert(classic(1))
            insert(b"synthetic non TIFF")
            clear = audit(engine, storage)
            assert clear["status"] == "CLEAR" and clear["registered"] == 2
            jbig_id = insert(classic(34661))
            blocked = audit(engine, storage)
            assert blocked["status"] == "BLOCK_JBIG" and blocked["jbig"] == 1
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM plm.doc_file_objects WHERE file_object_id=:id"),
                                   {"id": jbig_id})
            incomplete_id = insert(classic(1), state="STAGED")
            unknown = audit(engine, storage)
            assert unknown["status"] == "BLOCK_UNKNOWN" and unknown["unknown"] == 1
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM plm.doc_file_objects WHERE file_object_id=:id"),
                                   {"id": incomplete_id})
            altered_id = insert(classic(1))
            _, altered_locator = storage.locators(scope="GLOBAL", project_id=None,
                                                   file_object_id=altered_id)
            altered_path = Path(temporary).joinpath(*altered_locator.split("/"))
            altered_path.write_bytes(classic(34661))
            corrupt = audit(engine, storage)
            assert corrupt["status"] == "BLOCK_UNKNOWN" and corrupt["unknown"] == 1
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM plm.doc_file_objects WHERE file_object_id=:id"),
                                   {"id": altered_id})
                connection.execute(text("UPDATE plm.plt_maintenance_state SET state='RUNNING',lock_version=2"))
            try:
                audit(engine, storage)
            except PreflightUnavailable:
                pass
            else:
                raise AssertionError("running state was accepted")
            with engine.begin() as connection:
                connection.execute(text("UPDATE plm.plt_maintenance_state SET state='MAINTENANCE',lock_version=3"))
            with engine.connect() as other:
                assert other.scalar(text("SELECT pg_try_advisory_lock_shared(:key)"),
                                    {"key": MAINTENANCE_LOCK_KEY}) is True
                other.commit()
                try:
                    try:
                        audit(engine, storage)
                    except PreflightUnavailable:
                        pass
                    else:
                        raise AssertionError("busy fence was accepted")
                finally:
                    assert other.scalar(text("SELECT pg_advisory_unlock_shared(:key)"),
                                        {"key": MAINTENANCE_LOCK_KEY}) is True
                    other.commit()
            assert audit(engine, storage)["status"] == "CLEAR"
            with maintenance_window(engine) as window:
                assert window.scan(storage)["status"] == "CLEAR"
                window.verify()
                with engine.connect() as other:
                    assert other.scalar(text("SELECT pg_try_advisory_lock_shared(:key)"),
                                        {"key": MAINTENANCE_LOCK_KEY}) is False
                    other.rollback()
            with engine.connect() as other:
                assert other.scalar(text("SELECT pg_try_advisory_lock_shared(:key)"),
                                    {"key": MAINTENANCE_LOCK_KEY}) is True
                other.commit()
                assert other.scalar(text("SELECT pg_advisory_unlock_shared(:key)"),
                                    {"key": MAINTENANCE_LOCK_KEY}) is True
                other.commit()
            try:
                with maintenance_window(engine):
                    raise RuntimeError("synthetic upgrade step failed")
            except RuntimeError:
                pass
            with engine.connect() as other:
                assert other.scalar(text("SELECT pg_try_advisory_lock_shared(:key)"),
                                    {"key": MAINTENANCE_LOCK_KEY}) is True
                other.commit()
                assert other.scalar(text("SELECT pg_advisory_unlock_shared(:key)"),
                                    {"key": MAINTENANCE_LOCK_KEY}) is True
                other.commit()
        print("isolated PostgreSQL18 FileObject TIFF preflight: clear/JBIG/incomplete/hash/state/held-fence PASS")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
