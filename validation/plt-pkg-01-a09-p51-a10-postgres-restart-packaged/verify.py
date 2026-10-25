"""Packaged isolated PostgreSQL restart persistence proof for P51-A10."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
cross_project = runpy.run_path(
    str(ROOT / "validation/plt-pkg-01-a09-p51-a08-plan-cross-project-packaged/verify.py"))


def postgres_restart_probe(**context) -> None:
    from smoke_packaged_platform_write_https import current_packaged_postgres_restart
    restart = current_packaged_postgres_restart()
    project = context["project"]
    observer = context["observer_client"]
    with context["connect_db"]() as db:
        plan = db.execute(
            "SELECT plan_id,name,plan_state,current_approved_version_ref,created_by "
            "FROM plm.pln_plans WHERE project_id=%s "
            "AND name='P51-A07 Synthetic Implementation Plan' "
            "ORDER BY created_at DESC,plan_id DESC LIMIT 1", (project,),
        ).fetchone()
        assert plan is not None, "synthetic Plan identity missing before PostgreSQL restart"
        counts_before = (
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
    first = observer.get(f"/api/v1/projects/{project}/plans/{plan[0]}")
    assert first.status_code == 200, (first.status_code, first.text[:1000])
    first_data = first.json()["data"]
    assert (first_data["plan_id"], first_data["project_id"], first_data["name"],
            first_data["plan_state"], first_data["created_by"]) == (
                str(plan[0]), str(project), plan[1], plan[2], str(plan[4])), first_data

    restart()

    with context["connect_db"]() as db:
        assert db.execute("SELECT 1").fetchone() == (1,)
        assert db.execute(
            "SELECT plan_state,name,current_approved_version_ref,created_by "
            "FROM plm.pln_plans WHERE plan_id=%s AND project_id=%s",
            (plan[0], project),
        ).fetchone() == (plan[2], plan[1], plan[3], plan[4])
    second = observer.get(f"/api/v1/projects/{project}/plans/{plan[0]}")
    assert second.status_code == 200, (second.status_code, second.text[:1000])
    assert second.json()["data"] == first_data, second.json()
    with context["connect_db"]() as db:
        counts_after = (
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
    assert counts_after == counts_before, (counts_before, counts_after)
    print("P51_A10_POSTGRES_RESTART_PLAN_SESSION_PASS: same PG data, API, Caddy and member "
          "Session; Plan read stable; no extra Plan/Audit/receipt/Review decision", flush=True)


def main() -> int:
    namespace = cross_project["main"].__globals__
    original = namespace["cross_project_probe"]
    ran = False

    def cross_project_then_pg_restart(**context):
        nonlocal ran
        original(**context)
        postgres_restart_probe(**context)
        ran = True

    namespace["cross_project_probe"] = cross_project_then_pg_restart
    result = cross_project["main"]()
    if not ran:
        raise RuntimeError("P51-A10 PostgreSQL restart probe callback did not execute")
    return result


if __name__ == "__main__":
    sys.exit(main())
