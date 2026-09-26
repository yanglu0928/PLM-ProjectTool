"""Owned disposable PostgreSQL proof; Review/exception identities are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
import uuid

import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

# Reuse only synthetic seed helpers, never run the other verifier's main().
spec = spec_from_file_location("_history_fixture", Path(__file__).resolve().parents[1]
                              / "wfl-02-a01-p03-history-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
connect, insert, initialize, seed_evidence = (
    fixture.connect, fixture.insert, fixture.initialize, fixture.seed_evidence)
TABLES = ("wfl_checklist_records", "wfl_checklist_record_refs")
HASH = b"c"*32


def snapshot(db):
    return tuple(db.execute(statement).fetchall() for statement in (
        "SELECT * FROM plm.wfl_project_workflows ORDER BY workflow_id",
        "SELECT * FROM plm.wfl_checklist_items ORDER BY checklist_item_id",
        "SELECT * FROM plm.wfl_stages ORDER BY stage_id",
        "SELECT * FROM plm.evd_evidence_records ORDER BY evidence_id",
        "SELECT * FROM plm.wfl_checklist_records ORDER BY record_id",
        "SELECT * FROM plm.wfl_checklist_record_refs ORDER BY record_ref_id"))


def reject(db, action):
    before = snapshot(db)
    try:
        with db.transaction():
            action()
    except psycopg.Error as exc:
        assert exc.sqlstate in ("P0001", "23514", "23503", "23505", "23502"), (exc.sqlstate, exc.diag.message_primary)
        assert snapshot(db) == before
        return
    raise AssertionError("invalid Checklist history accepted")


def record(db, workflow, project, actor, evidence, result="FAIL", *,
           item="HANDOVER_BASELINE", root_changes=None, ref_changes=None,
           kinds=None, omit_kind=None, finish=True, item_update=True,
           workflow_update=True, duplicate_ref=False, change_evidence=False,
           resume_stage=False, ref_changes_kind=None):
    stage, workflow_version = db.execute("SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone()
    before_state, item_version = db.execute("SELECT item_state,lock_version FROM plm.wfl_checklist_items WHERE workflow_id=%s AND item_key=%s", (workflow, item)).fetchone()
    previous = db.execute("SELECT record_id FROM plm.wfl_checklist_records WHERE workflow_id=%s AND item_key=%s AND after_item_version=%s", (workflow, item, item_version)).fetchone()
    root = dict(workflow_id=workflow, project_id=project, definition_version=1,
        stage_key=stage, item_key=item, before_state=before_state, result=result,
        before_item_version=item_version, after_item_version=item_version+1,
        before_workflow_version=workflow_version, after_workflow_version=workflow_version+1,
        supersedes_record_id=previous[0] if previous else None, actor_id=actor,
        trace_id=uuid.uuid4(), occurred_at=datetime.now(timezone.utc),
        reason="Synthetic approved bounded exception" if result == "WAIVED" else None,
        impact="Synthetic impact" if result == "WAIVED" else None,
        content_fingerprint=HASH, created_xid=1)
    root.update(root_changes or {})
    identity = insert(db, TABLES[0], root, "record_id")
    assert db.execute("SELECT created_xid=txid_current() FROM plm.wfl_checklist_records WHERE record_id=%s", (identity,)).fetchone()[0]
    if kinds is None:
        kinds = [] if result == "FAIL" else ["EVIDENCE", "REVIEW_ROUND"]
        if result == "WAIVED":
            kinds.append("APPROVED_EXCEPTION")
    for kind in kinds:
        if kind == omit_kind:
            continue
        scope, ref_project, state, version, fingerprint = db.execute(
            "SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=%s", (evidence,)).fetchone()
        values = dict(record_id=identity, workflow_id=workflow, project_id=project,
            item_key=item, ref_kind=kind, ref_id=evidence if kind == "EVIDENCE" else uuid.uuid4(),
            ref_scope=scope if kind == "EVIDENCE" else "PROJECT",
            ref_project_id=ref_project if kind == "EVIDENCE" else project,
            observed_state=state if kind == "EVIDENCE" else "APPROVED",
            observed_lock_version=version if kind == "EVIDENCE" else 0,
            content_fingerprint=fingerprint, verified_at=datetime.now(timezone.utc))
        if ref_changes_kind is None or kind == ref_changes_kind:
            values.update(ref_changes or {})
        insert(db, TABLES[1], values, "record_ref_id")
        if duplicate_ref:
            insert(db, TABLES[1], values, "record_ref_id")
    if finish:
        if item_update:
            db.execute("UPDATE plm.wfl_checklist_items SET item_state=%s,lock_version=lock_version+1 WHERE workflow_id=%s AND item_key=%s", (result, workflow, item))
        if workflow_update:
            db.execute("UPDATE plm.wfl_project_workflows SET lock_version=lock_version+1 WHERE workflow_id=%s", (workflow,))
    if change_evidence:
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic changed fact',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
    if resume_stage:
        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key=%s", (workflow, stage))
    return identity


def start(db, workflow):
    with db.transaction():
        db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1 WHERE workflow_id=%s", (workflow,))
        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))


def main():
    name = "wflrecord_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config = create_migration_config(URL.create("postgresql+psycopg",
                username="poc_admin", host="127.0.0.1", port=55432, database=name))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0031")
            command.upgrade(config, "head")
            command.downgrade(config, "20260926_0031")
            with connect(name) as db:
                actor = insert(db, "auth_users", dict(username_display="Synthetic Checklist Owner",
                    username_normalized="synthetic checklist owner"), "user_id")
                projects = [insert(db, "prj_projects", dict(project_code=f"REC{i}",
                    project_code_normalized=f"rec{i}", name=f"Synthetic record {i}",
                    created_by=actor), "project_id") for i in range(3)]
                with db.transaction():
                    workflows = [initialize(db, project, actor) for project in projects]
                workflow, legacy, not_started = workflows
                start(db, workflow)
                start(db, legacy)
                db.execute("UPDATE plm.wfl_checklist_items SET item_state='PASS',lock_version=1 WHERE workflow_id=%s AND item_key='HANDOVER_BASELINE'", (legacy,))
                before = (db.execute("SELECT * FROM plm.wfl_project_workflows ORDER BY workflow_id").fetchall(),
                          db.execute("SELECT * FROM plm.wfl_checklist_items ORDER BY checklist_item_id").fetchall())
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0031")
            command.upgrade(config, "head")
            with connect(name) as db:
                assert before == (db.execute("SELECT * FROM plm.wfl_project_workflows ORDER BY workflow_id").fetchall(),
                                  db.execute("SELECT * FROM plm.wfl_checklist_items ORDER BY checklist_item_id").fetchall())
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_records").fetchone()[0] == 0
                evidence = seed_evidence(db, projects[0], actor)
                global_evidence = seed_evidence(db, None, actor)
                other_evidence = seed_evidence(db, projects[1], actor)
                def attempt(**kwargs):
                    return record(db, workflow, projects[0], actor, evidence, **kwargs)
                for values in ({"project_id": projects[1]}, {"definition_version": 2},
                               {"before_state": "PASS"}, {"result": "PENDING"},
                               {"after_item_version": 2}, {"before_workflow_version": 0},
                               {"after_workflow_version": 7}, {"actor_id": uuid.uuid4()},
                               {"trace_id": uuid.UUID(int=0)}, {"content_fingerprint": b"x"},
                               {"reason": " "}, {"impact": "\u3000"},
                               {"stage_key": "SURVEY"}, {"supersedes_record_id": uuid.uuid4()}):
                    reject(db, lambda values=values: attempt(root_changes=values))
                reject(db, lambda: record(db, legacy, projects[1], actor, other_evidence,
                                         root_changes={"supersedes_record_id": uuid.uuid4()}))
                reject(db, lambda: record(db, not_started, projects[2], actor, evidence))
                reject(db, lambda: attempt(item="SURVEY_CONCLUSION"))
                for options in (dict(finish=False), dict(item_update=False), dict(workflow_update=False),
                                dict(result="PASS", omit_kind="EVIDENCE"),
                                dict(result="PASS", omit_kind="REVIEW_ROUND"),
                                dict(result="PASS", ref_changes={"observed_state": "RETURNED"}, ref_changes_kind="REVIEW_ROUND"),
                                dict(result="WAIVED", omit_kind="APPROVED_EXCEPTION"),
                                dict(result="WAIVED", root_changes={"reason": None}),
                                dict(result="PASS", duplicate_ref=True), dict(result="PASS", change_evidence=True),
                                dict(kinds=["APPROVED_EXCEPTION"])):
                    reject(db, lambda options=options: attempt(**options))
                for values in ({"project_id": projects[1]}, {"item_key": "HANDOVER_ISSUES"},
                               {"ref_project_id": projects[1]}, {"ref_scope": "GLOBAL", "ref_project_id": None},
                               {"ref_id": uuid.uuid4()}, {"content_fingerprint": b"z"*32},
                               {"observed_lock_version": 999}, {"proof_schema_version": 2},
                               {"ref_kind": "UNKNOWN"}):
                    reject(db, lambda values=values: attempt(result="PASS", ref_changes=values))
                reject(db, lambda: record(db, workflow, projects[0], actor, other_evidence, "PASS"))
                # Caller/Audit-port failure after complete writes must roll back, not become a successful record.
                before = snapshot(db)
                try:
                    with db.transaction():
                        attempt()
                        raise RuntimeError("Synthetic Audit port failure")
                except RuntimeError:
                    pass
                assert snapshot(db) == before
                barrier = Barrier(2)
                def concurrent():
                    try:
                        with connect(name) as child, child.transaction():
                            barrier.wait(timeout=10)
                            record(child, workflow, projects[0], actor, evidence,
                                root_changes={"before_workflow_version": 1, "after_workflow_version": 2,
                                              "before_item_version": 0, "after_item_version": 1, "before_state": "PENDING"})
                        return "success"
                    except psycopg.Error as exc:
                        assert exc.sqlstate == "P0001" and "current facts mismatch" in exc.diag.message_primary
                        return "conflict"
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert sorted(pool.map(lambda _: concurrent(), range(2))) == ["conflict", "success"]
                first = db.execute("SELECT record_id FROM plm.wfl_checklist_records").fetchone()[0]
                all_pairs = set()
                for before_state in ("PASS", "FAIL", "WAIVED"):
                    for result in ("PASS", "FAIL", "WAIVED"):
                        if db.execute("SELECT item_state FROM plm.wfl_checklist_items WHERE workflow_id=%s AND item_key='HANDOVER_BASELINE'", (workflow,)).fetchone()[0] != before_state:
                            with db.transaction():
                                attempt(result=before_state)
                        with db.transaction():
                            identity = attempt(result=result)
                        assert db.execute("SELECT before_state,result FROM plm.wfl_checklist_records WHERE record_id=%s", (identity,)).fetchone() == (before_state, result)
                        all_pairs.add((before_state, result))
                assert len(all_pairs) == 9
                for values in ({"supersedes_record_id": first}, {"supersedes_record_id": uuid.uuid4()},
                               {"record_id": first}, {"supersedes_record_id": None}):
                    reject(db, lambda values=values: attempt(root_changes=values))
                db.execute("UPDATE plm.wfl_stages SET stage_state='BLOCKED' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                reject(db, lambda: attempt(resume_stage=True))
                with db.transaction():
                    blocked_record = attempt()
                assert db.execute("SELECT observed_stage_state FROM plm.wfl_checklist_records WHERE record_id=%s", (blocked_record,)).fetchone()[0] == "BLOCKED"
                with db.transaction():
                    record(db, workflow, projects[0], actor, global_evidence, "PASS", item="HANDOVER_ISSUES")
                other_record = db.execute("SELECT record_id FROM plm.wfl_checklist_records WHERE item_key='HANDOVER_ISSUES'").fetchone()[0]
                reject(db, lambda: attempt(root_changes={"supersedes_record_id": other_record}))
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic later change',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                reject(db, lambda: attempt(result="PASS"))
                with db.transaction():
                    failed = attempt(kinds=["EVIDENCE"])
                assert db.execute("SELECT observed_state FROM plm.wfl_checklist_record_refs WHERE record_id=%s", (failed,)).fetchone()[0] == "INELIGIBLE"
                with db.transaction():
                    returned = attempt(kinds=["REVIEW_ROUND"], ref_changes={"observed_state": "RETURNED"})
                assert db.execute("SELECT observed_state FROM plm.wfl_checklist_record_refs WHERE record_id=%s", (returned,)).fetchone()[0] == "RETURNED"
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_record_refs WHERE ref_id=%s AND observed_state='ELIGIBLE'", (evidence,)).fetchone()[0] > 0
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_record_refs WHERE evidence_id IS DISTINCT FROM CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END").fetchone()[0] == 0
                assert db.execute("SELECT is_generated FROM information_schema.columns WHERE table_schema='plm' AND table_name='wfl_checklist_record_refs' AND column_name='evidence_id'").fetchone()[0] == "ALWAYS"
                for table in TABLES:
                    for query in (sql.SQL("UPDATE plm.{} SET project_id=project_id"),
                                  sql.SQL("DELETE FROM plm.{}"), sql.SQL("TRUNCATE plm.{} CASCADE")):
                        reject(db, lambda query=query, table=table: db.execute(query.format(sql.Identifier(table))))
                reject(db, lambda: insert(db, TABLES[1], dict(record_id=first,
                    workflow_id=workflow, project_id=projects[0], item_key="HANDOVER_BASELINE",
                    ref_kind="REVIEW_ROUND", ref_id=uuid.uuid4(), ref_scope="PROJECT",
                    ref_project_id=projects[0], observed_state="APPROVED", observed_lock_version=0,
                    content_fingerprint=HASH, verified_at=datetime.now(timezone.utc)), "record_ref_id"))
                count = db.execute("SELECT count(*) FROM plm.wfl_checklist_records").fetchone()[0]
            try:
                command.downgrade(config, "20260926_0031")
            except RuntimeError as exc:
                assert "Checklist history exists" in str(exc)
            else:
                raise AssertionError("nonempty Checklist history downgrade accepted")
            command.check(config)
            with connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260926_0032"
                assert db.execute("SELECT count(*) FROM plm.wfl_checklist_records").fetchone()[0] == count
            print("PASS: 0032 two-table ORM parity, empty and existing-state upgrade/down/re-up unchanged; nine correction pairs, legacy-chain rejection, version/concurrency/rollback/atomicity, blocked stage retained, scoped/generated Evidence, basis/sealing/immutability and nonempty down refusal; synthetic Review/exception/Audit failure, not actual Gate/production")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
