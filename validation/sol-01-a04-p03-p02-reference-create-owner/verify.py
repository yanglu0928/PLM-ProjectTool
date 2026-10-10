"""Disposable PG18/full private-source proof of initial Reference Owner."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateError, ReferenceCreateService,
)
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_reference_sources",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
helper = prior.helper


class BrokenAudit:
    def append(self, tx, event):
        raise RuntimeError("synthetic Audit failure")


def rejects(code: str, action) -> None:
    try:
        action()
    except ReferenceCreateError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def verify(port: int, scratch: Path) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)

    def on_qualified(*, runtime, request, sources, audit, license_guard,
                     qualified, confirmed) -> None:
        command.downgrade(cfg, "20261008_0143")
        command.upgrade(cfg, "head")
        command.check(cfg)
        receipts = SqlAlchemyIdempotencyReceipts()
        repository = SqlAlchemyReferenceCreateRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        dependencies = dict(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=authorization,
            license_guard=license_guard, sources=sources,
            repository=repository, receipts=receipts,
        )
        service = ReferenceCreateService(**dependencies, audit=audit)
        command_request = CreateReferenceSolution(
            request, prior.CSRF, "Synthetic Reference", "r" * 16)
        rejects("AUTH_ACCESS_DENIED", lambda: service.create(
            replace(command_request, csrf_token=b"x" * 32)))
        first = service.create(command_request)
        assert first.scope == "GLOBAL" and first.project_id is None
        assert first.deidentification_confirmation_id == confirmed.confirmation_id
        assert first.source_fingerprint == qualified.content_fingerprint
        assert first.eligibility_state == "REFERENCE_ONLY"
        assert first.version_state == "DRAFT" and first.etag == '"v0"'
        again = service.create(replace(
            command_request, sources=replace(request, trace_id=uuid.uuid4())))
        assert first == again
        rejects("CONFLICT_IDEMPOTENCY", lambda: service.create(replace(
            command_request, name="Other Reference")))
        failed = ReferenceCreateService(**dependencies, audit=BrokenAudit())
        rejects("SOLUTION_UNAVAILABLE", lambda: failed.create(replace(
            command_request, idempotency_key="f" * 16)))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            refs = tuple(db.execute(
                "SELECT document_version_id FROM plm.sol_reference_document_refs "
                "WHERE reference_version_id=%s ORDER BY ordinal",
                (first.reference_version_id,)).fetchall())
            evidence = tuple(db.execute(
                "SELECT evidence_id FROM plm.sol_reference_evidence_refs "
                "WHERE reference_version_id=%s ORDER BY ordinal",
                (first.reference_version_id,)).fetchall())
            assert tuple(row[0] for row in refs) == request.document_version_ids
            assert tuple(row[0] for row in evidence) == request.evidence_ids
            assert db.execute("SELECT count(*) FROM plm.sol_reference_solutions").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.sol_reference_versions").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                              "'SOL_REFERENCE_CREATED'").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation='V1_SOL_REFERENCE_CREATE'").fetchone()[0] == 1
            def db_reject(message, action):
                try:
                    action()
                except Exception as error:
                    assert message in str(error), str(error)
                else:
                    raise AssertionError("expected " + message)
            db_reject("ReferenceSolution history is immutable", lambda: db.execute(
                "UPDATE plm.sol_reference_versions SET version_no=2 "
                "WHERE reference_version_id=%s", (first.reference_version_id,)))
            db_reject("ReferenceSolution history cannot be truncated", lambda: db.execute(
                "TRUNCATE plm.sol_reference_document_refs"))
        try:
            command.downgrade(cfg, "20261008_0143")
        except Exception as error:
            assert "ReferenceSolution history prevents Owner downgrade" in str(error), str(error)
        else:
            raise AssertionError("nonempty Reference Owner downgrade accepted")

    prior.verify(port, scratch, on_qualified=on_qualified)
    print("SOL_01_A04_P03_P02_REFERENCE_CREATE_OWNER_PG_PASS: real Auth, "
          "Document/Evidence source files, reference root/version/ordered refs, "
          "Audit/receipt rollback and replay, history and downgrade guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-ref-create-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(helper.PG_SOURCE / name, install / name)
    shutil.copy2(helper.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(helper.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (helper.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = helper.free_port()
    started = False
    try:
        helper.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        helper.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                   "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port, scratch)
    finally:
        if started:
            helper.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-ref-create-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
