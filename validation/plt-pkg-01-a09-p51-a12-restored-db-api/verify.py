"""Verify the existing packaged API session reads Plan from the restored DB."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
restore = runpy.run_path(
    str(ROOT / "validation/plt-pkg-01-a09-p51-a11-postgres-restore-packaged/verify.py"))


def restored_database_api_probe(context, restored, source, source_counts) -> None:
    project = context["project"]
    plan_id = source[0]
    client = context["observer_client"]
    path = f"/api/v1/projects/{project}/plans/{plan_id}"
    before = client.get(path)
    assert before.status_code == 200, (before.status_code, before.text[:1000])
    restore_source = restored["activate_restored_api_database"]()
    try:
        after = client.get(path)
        assert after.status_code == 200, (after.status_code, after.text[:1000])
        data = after.json()["data"]
        assert data == before.json()["data"], (before.json(), after.json())
        assert (data["plan_id"], data["project_id"], data["name"],
                data["plan_state"], data["created_by"]) == (
                    str(source[0]), str(project), source[2], source[1], str(source[4])), data
        with restored["connect_restored_db"]() as db:
            assert db.execute(
                "SELECT count(*) FROM plm.pln_plans WHERE project_id=%s", (project,),
            ).fetchone()[0] == source_counts[0]
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='PLAN_CREATED' "
                "AND target_project_id=%s", (project,),
            ).fetchone()[0] == source_counts[1]
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE project_id=%s AND operation='V1_PLAN_CREATE' "
                "AND state='COMPLETED'", (project,),
            ).fetchone()[0] == source_counts[2]
            assert db.execute(
                "SELECT count(*) FROM plm.rvw_review_decisions d "
                "JOIN plm.rvw_reviews r ON r.review_id=d.review_id "
                "WHERE r.project_id=%s", (project,),
            ).fetchone()[0] == source_counts[3]
    finally:
        assert restore_source() is True, "original database credential was not restored"
    final = client.get(path)
    assert final.status_code == 200, (final.status_code, final.text[:1000])
    assert final.json()["data"] == before.json()["data"]
    print("P51_A12_RESTORED_DATABASE_API_SESSION_PASS: same HTTPS session read the restored "
          "Plan, then API/credential returned to source DB", flush=True)


def main() -> int:
    restore["postgres_restore_probe"].__globals__["AFTER_RESTORE_PROBE"] = (
        restored_database_api_probe)
    prototype_chain = restore["postgres_restart"]["cross_project"]["plan"]["base"]
    prototype_probe = prototype_chain.get("prototype_probe")
    if not callable(prototype_probe):
        raise RuntimeError("A12 expected previously verified P51-A05 callback is unavailable")

    def reuse_existing_prototype_evidence(**_context) -> None:
        fixture_db = _context.get("fixture_db")
        if not callable(fixture_db):
            raise RuntimeError("A12 requires the current smoke's fixture DB for rate-bucket cleanup")
        seed_requirement = prototype_probe.__globals__.get("seed_current_requirement")
        if not callable(seed_requirement):
            raise RuntimeError("A12 requires the established synthetic Prototype source fixture")
        seed_requirement(_context, _context["project"])
        with fixture_db() as db:
            db.execute("DELETE FROM plm.auth_login_rate_buckets")
        print("P51_A12_REUSE_P51_A05_PRIOR_PASS: prototype UI probe not repeated; "
              "its coherent synthetic Requirement/Review source fixture was seeded and "
              "owned synthetic login buckets cleared",
              flush=True)

    prototype_probe.__globals__["prototype_probe"] = reuse_existing_prototype_evidence
    return restore["main"]()


if __name__ == "__main__":
    sys.exit(main())
