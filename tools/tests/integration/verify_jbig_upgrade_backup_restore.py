"""Synthetic backup/block/restore rehearsal on an explicitly verified temp PG18.

Never connects to a nonmatching data directory and never touches real customer data.
Generated evidence remains under the caller's new output root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from scan_fileobject_jbig_upgrade import LocalFileStorage, audit  # noqa: E402
from tools.tests.test_scan_tiff_jbig_preflight import classic  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_pg(binary: Path, *args: str) -> None:
    result = subprocess.run([str(binary), *args], capture_output=True, text=True,
                            timeout=120, check=False)
    if result.returncode != 0:
        raise RuntimeError("isolated backup or restore command failed")


def connect(db: str):
    return create_engine(f"postgresql+psycopg://plmtest@127.0.0.1:55483/{db}",
                         hide_parameters=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    if (not args.data_dir.is_absolute() or not args.pg_bin.is_absolute()
            or not args.output_root.is_absolute() or args.output_root.exists()):
        raise RuntimeError("new isolated absolute paths required")
    if (args.data_dir.name != "data"
            or not args.data_dir.parent.name.startswith("plm-jbig-upgrade-pg-")):
        raise RuntimeError("temporary rehearsal cluster required")
    pg_dump = args.pg_bin / "pg_dump.exe"
    pg_restore = args.pg_bin / "pg_restore.exe"
    if not pg_dump.is_file() or not pg_restore.is_file():
        raise RuntimeError("PostgreSQL tools missing")
    engine = connect("plm_fulltest")
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    created = False
    try:
        with engine.connect() as connection:
            if Path(connection.scalar(text("SHOW data_directory"))).resolve() != args.data_dir.resolve():
                raise RuntimeError("database is not isolated temp cluster")
            if connection.scalar(text("SELECT version_num FROM plm.alembic_version")) != "20260930_0051":
                raise RuntimeError("full product Schema 0051 required")
            if (connection.scalar(text("SELECT count(*) FROM plm.auth_users")) != 0
                    or connection.scalar(text("SELECT count(*) FROM plm.doc_file_objects")) != 0
                    or connection.scalar(text("SELECT state FROM plm.plt_maintenance_state")) != "RUNNING"):
                raise RuntimeError("isolated test database not clean")
        args.output_root.mkdir(parents=True)
        data_root = args.output_root / "live-data"
        data_root.mkdir()
        storage = LocalFileStorage(data_root)
        _, locator = storage.locators(scope="GLOBAL", project_id=None,
                                       file_object_id=file_id)
        tiff = classic(34661)
        file_path = data_root.joinpath(*locator.split("/"))
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(tiff)
        config = args.output_root / "live-config"
        license_root = args.output_root / "live-license"
        config.mkdir()
        license_root.mkdir()
        (config / "synthetic-bootstrap.yaml").write_text("synthetic: true\n", encoding="utf-8")
        (license_root / "synthetic-license.txt").write_text("NO REAL LICENSE\n", encoding="utf-8")
        with engine.begin() as connection:
            connection.execute(text("""INSERT INTO plm.auth_users
                (user_id,username_display,username_normalized,state,deployment_role,
                 credential_version,lock_version)
                VALUES (:id,'synthetic-recovery','synthetic-recovery','DISABLED','NONE',0,0)"""),
                {"id": user_id})
            connection.execute(text("""INSERT INTO plm.doc_file_objects
                (file_object_id,usage_kind,scope,project_id,storage_class,storage_locator,
                 original_name_metadata,sha256,size_bytes,detected_mime,file_state,
                 created_by,available_at)
                VALUES (:id,'DOCUMENT','GLOBAL',NULL,'PERSISTENT',:locator,
                        'synthetic.tif',:sha,:size,'image/tiff','AVAILABLE',:user_id,
                        statement_timestamp() + interval '1 millisecond')"""),
                {"id": file_id, "locator": locator, "sha": hashlib.sha256(tiff).digest(),
                 "size": len(tiff), "user_id": user_id})
        created = True
        backup = args.output_root / "backup"
        backup.mkdir()
        dump = backup / "database.dump"
        run_pg(pg_dump, "-h", "127.0.0.1", "-p", "55483", "-U", "plmtest",
               "-d", "plm_fulltest", "-Fc", "-f", str(dump))
        shutil.copytree(data_root, backup / "data")
        shutil.copytree(config, backup / "config")
        shutil.copytree(license_root, backup / "license")
        hashes = {"database": sha(dump),
                  "file": sha(backup / "data" / Path(*locator.split("/"))),
                  "config": sha(backup / "config" / "synthetic-bootstrap.yaml"),
                  "license": sha(backup / "license" / "synthetic-license.txt")}
        if hashes["file"] != hashlib.sha256(tiff).hexdigest():
            raise RuntimeError("backup data differs")
        with engine.begin() as connection:
            connection.execute(text("""UPDATE plm.plt_maintenance_state
                SET state='MAINTENANCE',lock_version=lock_version+1 WHERE state_id=1"""))
        blocked = audit(engine, storage)
        if blocked["status"] != "BLOCK_JBIG" or blocked["upgrade_allowed"]:
            raise RuntimeError("JBIG preflight did not block upgrade")
        with engine.connect() as connection:
            if (connection.scalar(text("SELECT version_num FROM plm.alembic_version")) != "20260930_0051"
                    or connection.scalar(text("SELECT to_regclass('plm.synthetic_upgrade_marker')")) is not None):
                raise RuntimeError("blocked upgrade changed schema")
        with engine.begin() as connection:
            connection.execute(text("""UPDATE plm.plt_maintenance_state
                SET state='RUNNING',lock_version=lock_version+1 WHERE state_id=1"""))
        suffix = uuid.uuid4().hex[:8]
        failed_db = f"plm_failed_{suffix}"
        recovered_db = f"plm_recovered_{suffix}"
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f"CREATE DATABASE {failed_db}")
            admin.exec_driver_sql(f"CREATE DATABASE {recovered_db}")
        for db in (failed_db, recovered_db):
            run_pg(pg_restore, "-h", "127.0.0.1", "-p", "55483", "-U", "plmtest",
                   "-d", db, "--no-owner", "--no-privileges", str(dump))
        failed = connect(failed_db)
        recovered = connect(recovered_db)
        try:
            with failed.begin() as connection:
                connection.execute(text("""UPDATE plm.auth_users
                    SET username_display='damaged' WHERE user_id=:id"""), {"id": user_id})
            with recovered.connect() as connection:
                user = connection.scalar(text("SELECT username_display FROM plm.auth_users WHERE user_id=:id"),
                                         {"id": user_id})
                row = connection.execute(text("""SELECT sha256,size_bytes FROM plm.doc_file_objects
                    WHERE file_object_id=:id"""), {"id": file_id}).one()
                version = connection.scalar(text("SELECT version_num FROM plm.alembic_version"))
                if (user != "synthetic-recovery" or row.sha256 != hashlib.sha256(tiff).digest()
                        or row.size_bytes != len(tiff) or version != "20260930_0051"):
                    raise RuntimeError("restored database differs from backup")
        finally:
            failed.dispose()
            recovered.dispose()
        restored_data = args.output_root / "restored-data"
        restored_config = args.output_root / "restored-config"
        restored_license = args.output_root / "restored-license"
        shutil.copytree(backup / "data", restored_data)
        shutil.copytree(backup / "config", restored_config)
        shutil.copytree(backup / "license", restored_license)
        if (sha(restored_data / Path(*locator.split("/"))) != hashes["file"]
                or sha(restored_config / "synthetic-bootstrap.yaml") != hashes["config"]
                or sha(restored_license / "synthetic-license.txt") != hashes["license"]):
            raise RuntimeError("restored file set differs from backup")
        result = {"status": "SYNTHETIC_BACKUP_BLOCK_RESTORE_PASS",
                  "release_eligible": False, "schema": "20260930_0051",
                  "preflight": blocked["status"], "backup_sha256": hashes,
                  "restored_database_count": 2, "restored_file_sets": 3}
        (args.output_root / "result.json").write_text(
            json.dumps(result, sort_keys=True, indent=2), encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if created:
            with engine.begin() as connection:
                if connection.scalar(text("SELECT state FROM plm.plt_maintenance_state")) == "MAINTENANCE":
                    connection.execute(text("""UPDATE plm.plt_maintenance_state
                        SET state='RUNNING',lock_version=lock_version+1 WHERE state_id=1"""))
                connection.execute(text("DELETE FROM plm.doc_file_objects WHERE file_object_id=:id"),
                                   {"id": file_id})
                connection.execute(text("DELETE FROM plm.auth_users WHERE user_id=:id"),
                                   {"id": user_id})
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
