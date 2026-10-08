"""Disposable PG18 proof for closed GLOBAL Reference confirmation Schema0140."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / "validation/sol-01-a03-p03-reference-source-schema/verify.py"
SPEC = importlib.util.spec_from_file_location("prior_reference_verifier", PRIOR)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
TABLE = "sol_reference_deidentification_confirmations"
PREVIOUS = "20261008_0139"


def rejects(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def verify(port: int) -> None:
    # Prior verifier covers existing-data upgrade and all earlier Solution constraints.
    prior.verify(port)
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized='section version actor'"
        ).fetchone()[0]
        insert = (
            f"INSERT INTO plm.{TABLE}(source_fingerprint,source_project_class,"
            "deidentification_class,applicability,attestation_statement,confirmed_by,"
            "confirmed_at,expires_at,trace_id) VALUES (%s,%s,%s,%s::jsonb,%s,%s,"
            "'2026-10-08 10:00:00+00','2026-10-09 10:00:00+00',%s)"
        )
        valid = (b"f" * 32, "PLM", "DEIDENTIFIED", "{}",
                 "I_VERIFIED_DEIDENTIFICATION", actor, uuid.uuid4())
        rejects("Reference deidentification Owner is not installed",
                lambda: db.execute(insert, valid))
        rejects("Reference deidentification history cannot be truncated",
                lambda: db.execute(f"TRUNCATE plm.{TABLE}"))
        db.execute(f"ALTER TABLE plm.{TABLE} DISABLE TRIGGER trg_{TABLE}__owner")
        try:
            db.execute(insert, valid)
            rejects("ck_sol_reference_deidentification__fingerprint",
                    lambda: db.execute(insert, (b"bad", *valid[1:])))
            rejects("ck_sol_reference_deidentification__source_class",
                    lambda: db.execute(insert, (valid[0], " PLM", *valid[2:])))
            rejects("ck_sol_reference_deidentification__applicability",
                    lambda: db.execute(insert, (*valid[:3], "[]", *valid[4:])))
            rejects("ck_sol_reference_deidentification__statement",
                    lambda: db.execute(insert, (*valid[:4], "AI_APPROVED", *valid[5:])))
            rejects("fk_sol_reference_deidentification__actor",
                    lambda: db.execute(insert, (*valid[:5], uuid.uuid4(), valid[6])))
            rejects("ck_sol_reference_deidentification__time", lambda: db.execute(
                f"UPDATE plm.{TABLE} SET expires_at=confirmed_at"))
            rejects("ck_sol_reference_deidentification__time", lambda: db.execute(
                f"UPDATE plm.{TABLE} SET revoked_at=confirmed_at - INTERVAL '1 second'"))
            try:
                command.downgrade(cfg, PREVIOUS)
            except Exception as error:
                assert "Reference deidentification history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("confirmation history was dropped")
            db.execute(f"DELETE FROM plm.{TABLE}")
        finally:
            db.execute(f"ALTER TABLE plm.{TABLE} ENABLE TRIGGER trg_{TABLE}__owner")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("SOL_01_A04_P02_P03_P01_DEIDENTIFICATION_SCHEMA_PASS: prior regression, "
          "empty/existing upgrade, downgrade/re-upgrade, drift, constraints and guards")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-confirm-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(prior.prior.PG_SOURCE / name, install / name)
    shutil.copy2(prior.prior.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(prior.prior.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (prior.prior.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = prior.prior.free_port()
    started = False
    try:
        prior.prior.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                        "-A", "trust", "--no-locale", "-E", "UTF8")
        prior.prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                        "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            prior.prior.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-confirm-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
