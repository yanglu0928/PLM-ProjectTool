"""Isolated Windows 11 / PG18 proof for Prototype's actual document bytes."""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.prototype_workflow_integrity import (
    SqlAlchemyPrototypeWorkflowArtifactIntegrityProof,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
USER = "poc_admin"


def _run(arguments: list[str], *, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(
        arguments, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
        text=True, errors="replace", timeout=120, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(arguments[0]).name}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _verify(port: int, scratch: Path) -> None:
    url = URL.create(
        "postgresql+psycopg", username=USER, host="127.0.0.1",
        port=port, database="postgres",
    )
    config = create_migration_config(url)
    command.upgrade(config, "head")
    command.check(config)
    payload = b"Synthetic Prototype Workflow fixed artifact for physical PG proof."
    digest = hashlib.sha256(payload).digest()
    file_id = uuid.uuid4()
    storage_root = scratch / "private-documents"
    storage_root.mkdir()
    storage = LocalFileStorage(storage_root)
    with psycopg.connect(
        host="127.0.0.1", port=port, user=USER, dbname="postgres",
        autocommit=True,
    ) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Prototype Proof','prototype proof') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PRTP','prtp','Prototype proof',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        other_project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PRTO','prto','Other proof',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        staging, final = LocalFileStorage.locators(
            scope="PROJECT", project_id=project, file_object_id=file_id,
        )
        with storage.reserve_staging(staging) as stream:
            stream.write(payload)
        storage.publish_verified(
            staging, final, expected_sha256=digest,
            expected_size=len(payload), max_bytes=100_000_000,
        )
        document = db.execute(
            "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('PROJECT',%s,'PROJECT_RECORD','Prototype proof','proof.txt',%s) "
            "RETURNING document_id", (project, actor),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
            "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
            "detected_mime,available_at) VALUES "
            "(%s,'PROJECT',%s,'PERSISTENT',%s,'proof.txt',%s,'AVAILABLE',%s,%s,"
            "'text/plain',statement_timestamp())",
            (file_id, project, final, actor, digest, len(payload)),
        )
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
            "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, project, file_id, digest, len(payload), Jsonb({}), actor),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
            "WHERE document_id=%s", (version, version, document),
        )
    facts = PrototypeVersionDocumentArtifactProof(
        version, document, "PROJECT", project, digest.hex(), len(payload),
        "text/plain",
    )
    proof = SqlAlchemyPrototypeWorkflowArtifactIntegrityProof(storage=storage)
    runtime = create_database_runtime(url)
    try:
        started = time.perf_counter()
        with runtime.unit_of_work() as tx:
            assert proof.prove_actual_content(tx, project_id=project, metadata=facts) is not None
        elapsed_ms = (time.perf_counter() - started) * 1000
        with runtime.unit_of_work() as tx:
            assert proof.prove_actual_content(tx, project_id=other_project, metadata=facts) is None
        file_path = storage_root / final
        file_path.write_bytes(payload[:-1] + b"!")
        with runtime.unit_of_work() as tx:
            assert proof.prove_actual_content(tx, project_id=project, metadata=facts) is None
        file_path.unlink()
        with runtime.unit_of_work() as tx:
            assert proof.prove_actual_content(tx, project_id=project, metadata=facts) is None
        print(
            "PRT_01_A11_A05_P01_PHYSICAL_PG_PASS: isolated Windows 11/PG18.6 "
            "real fixed bytes accepted; cross-project, tampered and missing bytes rejected; "
            f"single synthetic proof {elapsed_ms:.2f} ms; Alembic head/drift PASS"
        )
    finally:
        runtime.dispose()


def main() -> None:
    temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    scratch = Path(tempfile.mkdtemp(prefix="plm-prt-a05-p01-", dir=temp_root)).resolve()
    if not scratch.is_relative_to(temp_root) or scratch == temp_root or not str(scratch).isascii():
        raise RuntimeError("isolated ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    try:
        for name in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / name, install / name)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(path, install / "share/extension" / path.name)
        binaries = install / "bin"
        data = scratch / "data"
        log = scratch / "postgres.log"
        port = _free_port()
        _run([str(binaries / "initdb.exe"), "-D", str(data), "-U", USER,
              "-A", "trust", "--no-locale", "-E", "UTF8"])
        _run([str(binaries / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
              "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"], detached=True)
        _verify(port, scratch)
    finally:
        control = install / "bin/pg_ctl.exe"
        data = scratch / "data"
        if control.is_file() and data.is_dir():
            status = subprocess.run(
                [str(control), "-D", str(data), "status"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
            if status.returncode == 0:
                _run([str(control), "-D", str(data), "-m", "fast", "-w", "stop"])
                status = subprocess.run(
                    [str(control), "-D", str(data), "status"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30, check=False,
                )
            if status.returncode == 0:
                raise RuntimeError("isolated PostgreSQL still running; temporary data preserved")
        if (scratch.is_relative_to(temp_root) and scratch != temp_root
                and scratch.name.startswith("plm-prt-a05-p01-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
