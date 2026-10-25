"""Disposable PG18 proof of one-time revocation, replay and audit rollback."""

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
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeError, ReferenceDeidentificationRevokeService,
    RevokeReferenceDeidentification,
)
from plm_assistant.modules.solution.application.prove_reference_deidentification import (
    ReferenceDeidentificationProofService,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_repository import (
    SqlAlchemyReferenceDeidentificationRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_revocation_repository import (
    SqlAlchemyReferenceDeidentificationRevocationRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_proof_repository import (
    SqlAlchemyReferenceDeidentificationProofRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_confirmation_owner",
    ROOT / "validation/sol-01-a04-p02-p03-p02-confirm-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
source = prior.prior.prior.prior
TABLE = prior.TABLE


def rejects(action) -> None:
    try:
        action()
    except Exception:
        return
    raise AssertionError("expected rejection")


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
        row = db.execute(f"SELECT confirmation_id FROM plm.{TABLE} LIMIT 1").fetchone()[0]
        rejects(lambda: db.execute(f"UPDATE plm.{TABLE} SET deidentification_class='OTHER' "
                                   "WHERE confirmation_id=%s", (row,)))
        rejects(lambda: db.execute(f"DELETE FROM plm.{TABLE} WHERE confirmation_id=%s", (row,)))
        rejects(lambda: db.execute(f"TRUNCATE plm.{TABLE}"))

    engine = create_engine(url)
    try:
        runtime = DatabaseRuntime(engine)
        access, sources = prior._Access(actor), prior._Sources(uuid.uuid4())
        receipt = SqlAlchemyIdempotencyReceipts()
        audit = AuditService(SqlAlchemyAuditRepository())
        repo = SqlAlchemyReferenceDeidentificationRepository()
        confirm = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=access, license_guard=prior._License(),
            sources=sources, repository=repo, receipts=receipt, audit=audit,
            clock=lambda: datetime(2026, 10, 8, 13, tzinfo=timezone.utc),
        )
        request = ReferenceSourceRequest(
            b"s" * 32, uuid.uuid4(), "GLOBAL", None, (sources.version,), (),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"})
        view = confirm.confirm(ConfirmReferenceDeidentification(
            request, b"c" * 32, datetime(2026, 10, 9, 13, tzinfo=timezone.utc),
            "I_VERIFIED_DEIDENTIFICATION", "k" * 16))
        read = ReferenceDeidentificationProofService(
            admins=prior._ReadAdmin(actor),
            confirmations=SqlAlchemyReferenceDeidentificationProofRepository(),
            clock=lambda: datetime(2026, 10, 8, 13, 1, tzinfo=timezone.utc),
        )
        proof_args = dict(session_token=b"s" * 32, trace_id=request.trace_id,
                          source_fingerprint=view.source_fingerprint,
                          source_project_class="PLM", deidentification_class="DEIDENTIFIED",
                          applicability={"industry": "synthetic"})
        with runtime.unit_of_work() as tx:
            assert read.prove(tx, **proof_args) is not None
        service = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work, access=access, license_guard=prior._License(),
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=receipt, audit=audit,
            clock=lambda: datetime(2026, 10, 8, 13, 1, tzinfo=timezone.utc),
        )
        cmd = RevokeReferenceDeidentification(
            view.confirmation_id, b"s" * 32, b"c" * 32, uuid.uuid4(),
            "ADMIN_REVIEW", "r" * 16)
        failing = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work, access=access, license_guard=prior._License(),
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=receipt, audit=prior._FailAudit(),
            clock=lambda: datetime(2026, 10, 8, 13, 1, tzinfo=timezone.utc),
        )
        rejects(lambda: failing.revoke(cmd))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(f"SELECT revoked_at FROM plm.{TABLE} WHERE confirmation_id=%s",
                              (view.confirmation_id,)).fetchone()[0] is None
        first = service.revoke(cmd)
        again = service.revoke(cmd)
        assert first == again
        rejects(lambda: service.revoke(RevokeReferenceDeidentification(
            view.confirmation_id, b"s" * 32, b"c" * 32, uuid.uuid4(),
            "SCOPE_CHANGED", "z" * 16)))
        with runtime.unit_of_work() as tx:
            assert read.prove(tx, **proof_args) is None
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                              "'SOL_REFERENCE_DEIDENTIFICATION_REVOKED'").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                              "operation='V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKE'").fetchone()[0] == 1
            prior.rejects("Reference deidentification history is immutable", lambda: db.execute(
                f"UPDATE plm.{TABLE} SET revoked_at='2026-10-08 13:02:00+00' "
                "WHERE confirmation_id=%s", (view.confirmation_id,)))
        command.downgrade(cfg, "20261008_0141")
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(f"SELECT revoked_at FROM plm.{TABLE} WHERE confirmation_id=%s",
                              (view.confirmation_id,)).fetchone()[0] is not None
            prior.rejects("Reference deidentification history is immutable", lambda: db.execute(
                f"UPDATE plm.{TABLE} SET revoked_at=NULL WHERE confirmation_id=%s",
                (view.confirmation_id,)))
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        engine.dispose()
    print("SOL_01_A04_P02_P03_P03_P02_REVOKE_OWNER_PG_PASS: one-time revoke, "
          "audit/receipt rollback and replay, proof denial, history-preserving downgrade")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-revoke-owner-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
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
                and scratch.name.startswith("plm-sol-revoke-owner-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
