"""Disposable Win11 PG18 proof of closed GLOBAL publication event schema."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_publication_pg_helper",
    ROOT / "validation/sol-03-a03-outline-reference-schema/verify.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
PREVIOUS = "20261009_0156"
CURRENT = "20261009_0157"
TABLE = "plm.sol_global_reference_publication_events"
TRIGGER = "trg_sol_global_publications__owner"


def rejects(fragment: str, operation) -> None:
    try:
        operation()
    except Exception as error:
        if fragment not in str(error):
            raise AssertionError(f"expected {fragment!r}: {error}") from error
    else:
        raise AssertionError(f"expected rejection: {fragment}")


def _seed(port: int):
    actor, root, version, confirmation = (uuid.uuid4() for _ in range(4))
    now = datetime.now(timezone.utc)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            # Fixture-only synthetic upstream setup; no publication Owner is bypassed.
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'Publication Schema Actor','publication schema actor')",
                (actor,))
            db.execute(
                "INSERT INTO plm.sol_reference_deidentification_confirmations"
                "(confirmation_id,source_fingerprint,source_project_class,"
                "deidentification_class,applicability,attestation_statement,"
                "confirmed_by,confirmed_at,expires_at,trace_id) VALUES "
                "(%s,%s,'PLM','SYNTHETIC','{}'::jsonb,"
                "'I_VERIFIED_DEIDENTIFICATION',%s,%s,%s,%s)",
                (confirmation, b"s" * 32, actor, now, now + timedelta(days=1),
                 uuid.uuid4()))
            db.execute(
                "INSERT INTO plm.sol_reference_solutions"
                "(reference_solution_id,scope,name,current_version_ref,created_by) "
                "VALUES (%s,'GLOBAL','Unpublished raw source',%s,%s)",
                (root, version, actor))
            db.execute(
                "INSERT INTO plm.sol_reference_versions"
                "(reference_version_id,reference_solution_id,scope,version_no,"
                "applicability,source_project_class,deidentification_class,"
                "content_fingerprint,source_fingerprint,deidentification_confirmation_id,"
                "declared_document_count,declared_evidence_count,created_by) "
                "VALUES (%s,%s,'GLOBAL',1,'{}'::jsonb,'PLM','SYNTHETIC',"
                "%s,%s,%s,1,0,%s)",
                (version, root, b"c" * 32, b"s" * 32, confirmation, actor))
    return actor, root, version


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    actor, root, version = _seed(port)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        insert = (f"INSERT INTO {TABLE}(publication_event_id,reference_solution_id,"
                  "reference_version_id,scope,event_no,event_kind,display_label,"
                  "reason,actor_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        valid = (uuid.uuid4(), root, version, "GLOBAL", 1, "PUBLISH",
                 "审定的合成能力标签", "已人工审定无客户信息", actor)
        rejects("Owner is not installed", lambda: db.execute(insert, valid))
        rejects("history cannot be truncated", lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            rejects("ck_sol_global_publications__scope",
                    lambda: db.execute(insert, valid[:3] + ("PROJECT",) + valid[4:]))
            rejects("fk_sol_global_publications__version",
                    lambda: db.execute(insert, (uuid.uuid4(), root, uuid.uuid4()) + valid[3:]))
            rejects("ck_sol_global_publications__label",
                    lambda: db.execute(insert, valid[:6] + (" raw label ",) + valid[7:]))
            rejects("ck_sol_global_publications__label",
                    lambda: db.execute(insert, valid[:5] + ("REVOKE", "invalid") + valid[7:]))
            db.execute(insert, valid)
            rejects("uq_sol_global_publications__root_no",
                    lambda: db.execute(insert, (uuid.uuid4(),) + valid[1:]))
            revoked = (uuid.uuid4(), root, version, "GLOBAL", 2, "REVOKE",
                       None, "发布已撤回", actor)
            db.execute(insert, revoked)
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
        assert db.execute(f"SELECT event_no,event_kind,display_label FROM {TABLE} "
                          "ORDER BY event_no").fetchall() == [
                              (1, "PUBLISH", "审定的合成能力标签"), (2, "REVOKE", None)]
        rejects("Owner is not installed",
                lambda: db.execute(f"UPDATE {TABLE} SET reason='overwrite'"))
        rejects("Owner is not installed", lambda: db.execute(f"DELETE FROM {TABLE}"))
    rejects("history prevents downgrade", lambda: command.downgrade(cfg, PREVIOUS))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            db.execute(f"DELETE FROM {TABLE}")
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    print("SOL_03_A04_P03_P03_P06_A03_P01_GLOBAL_PUBLICATION_SCHEMA_PASS: "
          "empty/existing up/down/re-up, drift, default unpublished, "
          "GLOBAL version FK, checks, closed DML and nonempty downgrade refusal")


if __name__ == "__main__":
    helper.verify = verify
    helper.main()
