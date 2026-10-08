"""Disposable PG18 proof for GLOBAL Reference confirmation Owner and Audit atomicity."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmError,
    ReferenceDeidentificationConfirmService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceRequest, VerifiedReferenceDocument,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_repository import (
    SqlAlchemyReferenceDeidentificationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / "validation/sol-01-a04-p02-p03-p01-deidentification-schema/verify.py"
SPEC = importlib.util.spec_from_file_location("prior_confirmation_schema", PRIOR)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
TABLE = "sol_reference_deidentification_confirmations"


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + message)


class _Access:
    def __init__(self, actor):
        self.actor = actor

    def authorized_admin(self, tx, **kwargs):
        return self.actor


class _License:
    def require_valid(self, *, trace_id):
        return object()


class _Sources:
    def __init__(self, version):
        self.version = version
        self.digest = b"d" * 32

    def prove_sources(self, tx, request):
        return ProvenReferenceSources(
            "GLOBAL", None, (VerifiedReferenceDocument(
                uuid.uuid4(), self.version, "GLOBAL", None,
                "REFERENCE_MATERIAL", self.digest),), (), b"f" * 32,
        )


class _FailAudit:
    def append(self, tx, event):
        raise RuntimeError("synthetic audit outage")


def verify(port: int) -> None:
    prior.verify(port)
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized='section version actor'"
        ).fetchone()[0]
        row_id = uuid.uuid4()
        db.execute(
            f"INSERT INTO plm.{TABLE}(confirmation_id,source_fingerprint,"
            "source_project_class,deidentification_class,applicability,"
            "attestation_statement,confirmed_by,confirmed_at,expires_at,trace_id) "
            "VALUES (%s,%s,'PLM','DEIDENTIFIED','{}'::jsonb,"
            "'I_VERIFIED_DEIDENTIFICATION',%s,"
            "'2026-10-08 10:00:00+00','2026-10-09 10:00:00+00',%s)",
            (row_id, b"f" * 32, actor, uuid.uuid4()),
        )
        rejects("Reference deidentification history is immutable", lambda: db.execute(
            f"UPDATE plm.{TABLE} SET revoked_at='2026-10-08 11:00:00+00' "
            "WHERE confirmation_id=%s", (row_id,)))
        rejects("Reference deidentification history is immutable", lambda: db.execute(
            f"DELETE FROM plm.{TABLE} WHERE confirmation_id=%s", (row_id,)))
        rejects("Reference deidentification history cannot be truncated", lambda: db.execute(
            f"TRUNCATE plm.{TABLE}"))
        rejects("Reference confirmation history prevents Owner downgrade",
                lambda: command.downgrade(cfg, "20261008_0140"))
        db.execute(f"ALTER TABLE plm.{TABLE} DISABLE TRIGGER trg_{TABLE}__owner")
        try:
            db.execute(f"DELETE FROM plm.{TABLE} WHERE confirmation_id=%s", (row_id,))
        finally:
            db.execute(f"ALTER TABLE plm.{TABLE} ENABLE TRIGGER trg_{TABLE}__owner")
    command.downgrade(cfg, "20261008_0140")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("Reference deidentification Owner is not installed", lambda: db.execute(
            f"INSERT INTO plm.{TABLE}(source_fingerprint,source_project_class,"
            "deidentification_class,applicability,attestation_statement,confirmed_by,"
            "confirmed_at,expires_at,trace_id) VALUES (%s,'PLM','DEIDENTIFIED',"
            "'{}'::jsonb,'I_VERIFIED_DEIDENTIFICATION',%s,"
            "'2026-10-08 10:00:00+00','2026-10-09 10:00:00+00',%s)",
            (b"f" * 32, actor, uuid.uuid4()),
        ))
    command.upgrade(cfg, "head")
    command.check(cfg)

    engine = create_engine(url)
    try:
        runtime = DatabaseRuntime(engine)
        access, sources = _Access(actor), _Sources(uuid.uuid4())
        repository = SqlAlchemyReferenceDeidentificationRepository()
        receipts = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        service = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=_License(), sources=sources,
            repository=repository, receipts=receipts, audit=audit,
            clock=lambda: datetime(2026, 10, 8, 10, tzinfo=timezone.utc),
        )
        request = ReferenceSourceRequest(
            b"s" * 32, uuid.uuid4(), "GLOBAL", None, (sources.version,), (),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
        )
        cmd = ConfirmReferenceDeidentification(
            request, b"c" * 32, datetime(2026, 10, 9, 10, tzinfo=timezone.utc),
            "I_VERIFIED_DEIDENTIFICATION", "i" * 16,
        )
        first = service.confirm(cmd)
        second = service.confirm(cmd)
        assert first.confirmation_id == second.confirmation_id
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres") as db:
            count = db.execute(f"SELECT count(*) FROM plm.{TABLE}").fetchone()[0]
            audit_count = db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action="
                "'SOL_REFERENCE_DEIDENTIFICATION_CONFIRMED'"
            ).fetchone()[0]
            assert (count, audit_count) == (1, 1), (count, audit_count)
        failing = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=_License(), sources=sources,
            repository=repository, receipts=receipts, audit=_FailAudit(),
            clock=lambda: datetime(2026, 10, 8, 10, tzinfo=timezone.utc),
        )
        try:
            failing.confirm(ConfirmReferenceDeidentification(
                request, b"c" * 32, datetime(2026, 10, 9, 10, tzinfo=timezone.utc),
                "I_VERIFIED_DEIDENTIFICATION", "j" * 16,
            ))
        except ReferenceDeidentificationConfirmError:
            pass
        else:
            raise AssertionError("audit failure was accepted")
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres") as db:
            assert db.execute(f"SELECT count(*) FROM plm.{TABLE}").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation='V1_SOL_REFERENCE_DEIDENTIFICATION_CONFIRM'").fetchone()[0] == 1
    finally:
        engine.dispose()
    print("SOL_01_A04_P02_P03_P02_CONFIRM_OWNER_PG_PASS: migration 0141, immutable "
          "history, synthetic command/audit/receipt atomicity and rollback")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-confirm-owner-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    source = prior.prior.prior
    for name in ("bin", "lib", "share"):
        shutil.copytree(source.PG_SOURCE / name, install / name)
    shutil.copy2(source.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(source.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (source.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = source.free_port()
    started = False
    try:
        source.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        source.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            source.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-confirm-owner-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
