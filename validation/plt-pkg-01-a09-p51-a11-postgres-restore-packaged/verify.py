"""Packaged PostgreSQL logical backup/restore proof for P51-A11."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
postgres_restart = runpy.run_path(
    str(ROOT / "validation/plt-pkg-01-a09-p51-a10-postgres-restart-packaged/verify.py"))
AFTER_RESTORE_PROBE = None


def foreign_key_violations(connect) -> list[tuple[str, str, int]]:
    """Independently anti-join every PLM FK after pg_restore's trigger-disabled load."""
    violations = []
    with connect() as db:
        constraints = db.execute(
            """SELECT c.conname,c.conrelid,cn.nspname,child.relname,
                      c.confrelid,pn.nspname,parent.relname,c.conkey,c.confkey,
                      c.confmatchtype
                 FROM pg_constraint c
                 JOIN pg_class child ON child.oid=c.conrelid
                 JOIN pg_namespace cn ON cn.oid=child.relnamespace
                 JOIN pg_class parent ON parent.oid=c.confrelid
                 JOIN pg_namespace pn ON pn.oid=parent.relnamespace
                WHERE c.contype='f' AND cn.nspname='plm'
                ORDER BY c.conname"""
        ).fetchall()
        for (name, child_oid, child_schema, child_table, parent_oid,
             parent_schema, parent_table, child_keys, parent_keys, match_type) in constraints:
            if match_type == "p" or len(child_keys) != len(parent_keys):
                raise AssertionError(f"unsupported FK shape: {name}")
            child_columns = db.execute(
                "SELECT attname FROM pg_attribute WHERE attrelid=%s "
                "AND attnum=ANY(%s) ORDER BY array_position(%s,attnum)",
                (child_oid, list(child_keys), list(child_keys)),
            ).fetchall()
            parent_columns = db.execute(
                "SELECT attname FROM pg_attribute WHERE attrelid=%s "
                "AND attnum=ANY(%s) ORDER BY array_position(%s,attnum)",
                (parent_oid, list(parent_keys), list(parent_keys)),
            ).fetchall()
            if (len(child_columns) != len(child_keys) or
                    len(parent_columns) != len(parent_keys)):
                raise AssertionError(f"incomplete FK metadata: {name}")
            child_cols = [sql.Identifier("child", column[0]) for column in child_columns]
            parent_cols = [sql.Identifier("parent", column[0]) for column in parent_columns]
            all_null = sql.SQL(" AND ").join(sql.SQL("{} IS NULL").format(c)
                                              for c in child_cols)
            any_null = sql.SQL(" OR ").join(sql.SQL("{} IS NULL").format(c)
                                             for c in child_cols)
            all_set = sql.SQL(" AND ").join(sql.SQL("{} IS NOT NULL").format(c)
                                             for c in child_cols)
            matches = sql.SQL(" AND ").join(
                sql.SQL("{} = {}").format(child_col, parent_col)
                for child_col, parent_col in zip(child_cols, parent_cols, strict=True))
            missing_parent = sql.SQL("NOT EXISTS (SELECT 1 FROM {} AS parent WHERE {})").format(
                sql.Identifier(parent_schema, parent_table), matches)
            if match_type == "f":
                invalid = sql.SQL("NOT ({}) AND (({}) OR ({} AND {}))").format(
                    all_null, any_null, all_set, missing_parent)
            else:
                invalid = sql.SQL("({}) AND ({})").format(all_set, missing_parent)
            query = sql.SQL("SELECT count(*) FROM {} AS child WHERE {}").format(
                sql.Identifier(child_schema, child_table), invalid)
            count = db.execute(query).fetchone()[0]
            if count:
                violations.append((child_table, name, count))
    return violations


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
            coherent_synthetic_review = db.execute(
                """SELECT count(*) FROM plm.req_requirement_versions v
                   JOIN plm.req_requirements q ON q.requirement_id=v.requirement_id
                     AND q.project_id=v.project_id
                   JOIN plm.rvw_reviews r ON r.review_id=v.review_ref
                   JOIN plm.rvw_review_rounds rr ON rr.review_round_id=v.review_round_ref
                     AND rr.review_id=r.review_id
                   WHERE q.requirement_code='REQ-P51-PROTOTYPE-001'
                     AND r.subject_type='REQ-03' AND r.subject_id=q.requirement_id
                     AND rr.subject_version_id=v.requirement_version_id
                     AND r.review_state='APPROVED' AND rr.round_state='APPROVED'"""
            ).fetchone()[0]
            assert coherent_synthetic_review == 1, coherent_synthetic_review
        violations = foreign_key_violations(restored["connect_restored_db"])
        assert not violations, violations
        if callable(AFTER_RESTORE_PROBE):
            AFTER_RESTORE_PROBE(context, restored, source, source_counts)
        print("P51_A13_FK_DATA_AUDIT_PASS: every restored plm foreign key anti-join is clean",
              flush=True)
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
