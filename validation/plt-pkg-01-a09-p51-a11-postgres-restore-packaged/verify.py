"""Packaged PostgreSQL logical backup/restore proof for P51-A11."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
postgres_restart = runpy.run_path(
    str(ROOT / "validation/plt-pkg-01-a09-p51-a10-postgres-restart-packaged/verify.py"))


def snapshot(connect, project):
    with connect() as db:
        plan = db.execute(
            "SELECT plan_id,plan_state,name,current_approved_version_ref,created_by "
            "FROM plm.pln_plans WHERE project_id=%s "
            "AND name='P51-A07 Synthetic Implementation Plan' "
            "ORDER BY created_at DESC,plan_id DESC LIMIT 1", (project,),
        ).fetchone()
        assert plan is not None, "synthetic Plan identity missing from database"
        counts = (
            db.execute("SELECT count(*) FROM plm.pln_plans WHERE project_id=%s",
                       (project,)).fetchone()[0],
            db.execute("SELECT count(*) FROM plm.aud_events WHERE action='PLAN_CREATED' "
                       "AND target_project_id=%s", (project,)).fetchone()[0],
            db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                       "WHERE project_id=%s AND operation='V1_PLAN_CREATE' "
                       "AND state='COMPLETED'", (project,)).fetchone()[0],
            db.execute("SELECT count(*) FROM plm.rvw_review_decisions d "
                       "JOIN plm.rvw_reviews r ON r.review_id=d.review_id "
                       "WHERE r.project_id=%s", (project,)).fetchone()[0],
        )
        return plan, counts


def postgres_restore_probe(**context) -> None:
    from smoke_packaged_platform_write_https import current_packaged_postgres_logical_restore

    source, source_counts = snapshot(context["connect_db"], context["project"])
    restored = current_packaged_postgres_logical_restore()()
    assert restored["backup_bytes"] > 64, restored
    assert restored["backup_removed"] is True, restored
    try:
        restored_plan, restored_counts = snapshot(
            lambda: restored["connect_restored_db"](), context["project"])
        assert restored_plan == source, (source, restored_plan)
        assert restored_counts == source_counts, (source_counts, restored_counts)
        with restored["connect_restored_db"]() as db:
            assert db.execute("SELECT version_num FROM plm.alembic_version").fetchall() == [
                ("20261024_0185",)]
        print("P51_A11_POSTGRES_LOGICAL_BACKUP_RESTORE_PASS: packaged pg_dump/pg_restore "
              "preserved Plan, Audit, receipt and Review-decision data", flush=True)
    finally:
        restored["drop_restored_db"]()


def main() -> int:
    namespace = postgres_restart["cross_project"]["main"].__globals__
    original = namespace["cross_project_probe"]
    ran = False

    def prior_checks_then_restore(**context):
        nonlocal ran
        original(**context)
        postgres_restore_probe(**context)
        ran = True

    namespace["cross_project_probe"] = prior_checks_then_restore
    result = postgres_restart["main"]()
    if not ran:
        raise RuntimeError("P51-A11 PostgreSQL restore probe callback did not execute")
    return result


if __name__ == "__main__":
    sys.exit(main())
