"""Full migrated-schema rehearsal against an explicitly verified temp PG18 cluster."""

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
from scan_fileobject_jbig_upgrade import LocalFileStorage, audit  # noqa: E402
from tools.tests.test_scan_tiff_jbig_preflight import classic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.data_dir.is_absolute():
        raise RuntimeError("isolated data directory required")
    engine = create_engine("postgresql+psycopg://plmtest@127.0.0.1:55483/plm_fulltest",
                           hide_parameters=True)
    try:
        with engine.connect() as connection:
            if Path(connection.scalar(text("SHOW data_directory"))).resolve() != args.data_dir.resolve():
                raise RuntimeError("unexpected cluster")
            if connection.scalar(text("SELECT version_num FROM plm.alembic_version")) != "20260930_0051":
                raise RuntimeError("not the complete migrated schema")
        with tempfile.TemporaryDirectory(prefix="plm-jbig-full-schema-") as temporary:
            storage = LocalFileStorage(Path(temporary))
            user_id = uuid.uuid4()
            file_id = uuid.uuid4()
            data = classic(34661)
            _, locator = storage.locators(scope="GLOBAL", project_id=None,
                                           file_object_id=file_id)
            path = Path(temporary).joinpath(*locator.split("/"))
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
            with engine.begin() as connection:
                connection.execute(text("""INSERT INTO plm.auth_users
                    (user_id,username_display,username_normalized,state,deployment_role,
                     credential_version,lock_version)
                    VALUES (:id,'synthetic-upgrade','synthetic-upgrade','DISABLED','NONE',0,0)"""),
                    {"id": user_id})
                connection.execute(text("""INSERT INTO plm.doc_file_objects
                    (file_object_id,usage_kind,scope,project_id,storage_class,storage_locator,
                     original_name_metadata,sha256,size_bytes,detected_mime,file_state,
                     created_by,available_at)
                    VALUES (:id,'DOCUMENT','GLOBAL',NULL,'PERSISTENT',:locator,
                            'synthetic.tif',:sha,:size,'image/tiff','AVAILABLE',:user_id,
                            statement_timestamp() + interval '1 millisecond')"""),
                    {"id": file_id, "locator": locator, "sha": hashlib.sha256(data).digest(),
                     "size": len(data), "user_id": user_id})
                connection.execute(text("""UPDATE plm.plt_maintenance_state
                    SET state='MAINTENANCE',lock_version=lock_version+1 WHERE state_id=1"""))
            result = audit(engine, storage)
            assert result["status"] == "BLOCK_JBIG" and result["registered"] == 1
            with engine.begin() as connection:
                connection.execute(text("""UPDATE plm.plt_maintenance_state
                    SET state='RUNNING',lock_version=lock_version+1 WHERE state_id=1"""))
                connection.execute(text("DELETE FROM plm.doc_file_objects WHERE file_object_id=:id"),
                                   {"id": file_id})
                connection.execute(text("DELETE FROM plm.auth_users WHERE user_id=:id"),
                                   {"id": user_id})
            print("full migrated schema 0051 FileObject JBIG upgrade block PASS")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
