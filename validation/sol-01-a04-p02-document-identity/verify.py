"""Isolated PG18 check for fixed Reference DocumentVersion identity lookup."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from plm_assistant.modules.document.infrastructure.reference_version_identity import (
    SqlAlchemyReferenceVersionIdentity,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / "validation/sol-01-a03-p02-section-version-schema/verify.py"
SPEC = importlib.util.spec_from_file_location("prior_section_verifier", PRIOR)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def verify(port: int) -> None:
    prior.verify(port)
    engine = create_engine(
        f"postgresql+psycopg://poc_admin@127.0.0.1:{port}/postgres")
    lookup = SqlAlchemyReferenceVersionIdentity()
    try:
        with Session(engine) as session, session.begin():
            project = session.execute(text(
                "SELECT project_id FROM plm.prj_projects "
                "WHERE project_code_normalized='solsec1'"
            )).scalar_one()
            other = session.execute(text(
                "SELECT project_id FROM plm.prj_projects "
                "WHERE project_code_normalized='solsec2'"
            )).scalar_one()
            document_version = session.execute(text(
                "SELECT document_version_id FROM plm.doc_document_versions "
                "WHERE project_id=:project"
            ), {"project": project}).scalar_one()
            tx = SimpleNamespace(session=session)
            result = lookup.get(
                tx, scope="PROJECT", project_id=project,
                document_version_id=document_version)
            assert result is not None
            assert result.project_id == project
            assert result.document_version_id == document_version
            assert lookup.get(tx, scope="PROJECT", project_id=other,
                              document_version_id=document_version) is None
            assert lookup.get(tx, scope="GLOBAL", project_id=None,
                              document_version_id=document_version) is None
            assert lookup.get(tx, scope="PROJECT", project_id=project,
                              document_version_id=uuid.uuid4()) is None
        with Session(engine) as inactive:
            try:
                lookup.get(SimpleNamespace(session=inactive), scope="PROJECT",
                           project_id=project, document_version_id=document_version)
            except RuntimeError as error:
                assert "active Document transaction" in str(error)
            else:
                raise AssertionError("inactive transaction accepted")
    finally:
        engine.dispose()
    print("SOL_01_A04_P02_DOCUMENT_IDENTITY_PG_PASS: same-scope identity, "
          "cross-project/global/missing and inactive-transaction rejection")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-ref-document-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(prior.PG_SOURCE / name, install / name)
    shutil.copy2(prior.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(prior.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (prior.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port, started = prior.free_port(), False
    try:
        prior.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                  "-A", "trust", "--no-locale", "-E", "UTF8")
        prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                  "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-ref-document-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
