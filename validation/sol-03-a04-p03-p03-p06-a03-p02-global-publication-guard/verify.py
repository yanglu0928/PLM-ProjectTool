"""Disposable Win11 PostgreSQL 18 publication INSERT-only migration proof."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_publication_closed_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p01-global-publication-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)

PREVIOUS = "20261009_0157"
CURRENT = "20261009_0158"
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


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    actor, root, version = fixture._seed(port)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    insert = (
        f"INSERT INTO {TABLE}(publication_event_id,reference_solution_id,"
        "reference_version_id,scope,event_no,event_kind,display_label,"
        "reason,actor_id) VALUES (%s,%s,%s,'GLOBAL',%s,%s,%s,%s,%s)")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        def row(number: int, kind: str, label: str | None):
            return (uuid.uuid4(), root, version, number, kind, label,
                    "Synthetic admin review", actor)

        rejects("requires current eligibility", lambda: db.execute(
            insert, row(1, "PUBLISH", "Reviewed label")))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_reference_eligibility_events"
                "(eligibility_event_id,reference_solution_id,reference_version_id,"
                "scope,event_kind,prior_state,result_state,reason,actor_id,"
                "prior_lock_version,result_lock_version) VALUES "
                "(%s,%s,%s,'GLOBAL','HUMAN','REFERENCE_ONLY','ELIGIBLE',"
                "'Synthetic admin review',%s,0,1)",
                (uuid.uuid4(), root, version, actor))
            db.execute(
                "UPDATE plm.sol_reference_solutions SET eligibility_state='ELIGIBLE',"
                "eligibility_reason='Synthetic admin review',lock_version=1 "
                "WHERE reference_solution_id=%s", (root,))
        rejects("event number mismatch", lambda: db.execute(
            insert, row(2, "PUBLISH", "Reviewed label")))
        rejects("current version mismatch", lambda: db.execute(
            insert, (uuid.uuid4(), root, uuid.uuid4(), 1, "PUBLISH",
                     "Reviewed label", "Synthetic admin review", actor)))
        db.execute(insert, row(1, "PUBLISH", "Reviewed label"))
        rejects("unpublished version", lambda: db.execute(
            insert, row(2, "PUBLISH", "Other label")))
        rejects("event number mismatch", lambda: db.execute(
            insert, row(3, "REVOKE", None)))
        db.execute(insert, row(2, "REVOKE", None))
        rejects("revoke requires current publish", lambda: db.execute(
            insert, row(3, "REVOKE", None)))
        db.execute(insert, row(3, "PUBLISH", "Reviewed again"))
        rejects("history is immutable", lambda: db.execute(
            f"UPDATE {TABLE} SET reason='Changed' WHERE reference_solution_id=%s",
            (root,)))
        rejects("history is immutable", lambda: db.execute(
            f"DELETE FROM {TABLE} WHERE reference_solution_id=%s", (root,)))
        rejects("history cannot be truncated", lambda: db.execute(f"TRUNCATE {TABLE}"))
        assert db.execute(f"SELECT event_no,event_kind FROM {TABLE} "
                          "WHERE reference_solution_id=%s ORDER BY event_no",
                          (root,)).fetchall() == [
                              (1, "PUBLISH"), (2, "REVOKE"), (3, "PUBLISH")]
    rejects("history prevents Owner downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
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
    print("SOL_03_A04_P03_P03_P06_A03_P02_PUBLICATION_GUARD_PASS: "
          "empty/existing up/down/re-up, drift, current eligibility, "
          "event ordering/state, immutable history and nonempty downgrade refusal")


if __name__ == "__main__":
    fixture.helper.verify = verify
    fixture.helper.main()
