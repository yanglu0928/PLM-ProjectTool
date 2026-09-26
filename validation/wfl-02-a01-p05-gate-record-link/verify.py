"""Owned PostgreSQL link/atomicity proof; Review/exception observations synthetic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint

spec = spec_from_file_location("_link_record_fixture", Path(__file__).resolve().parents[1]
                              / "wfl-01-a05-p03-checklist-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
connect, insert = fixture.connect, fixture.insert
GATE_TABLES = ("wfl_stage_transitions", "wfl_transition_gate_items", "wfl_transition_gate_refs")


def snapshot(db):
    return fixture.snapshot(db) + tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(
        sql.Identifier(table))).fetchall() for table in GATE_TABLES)


def reject(db, action):
    before = snapshot(db)
    try:
        with db.transaction():
            action()
    except psycopg.Error as exc:
        assert exc.sqlstate in ("P0001", "23514", "23503", "23505", "23502"), (exc.sqlstate, exc.diag.message_primary)
        assert snapshot(db) == before
        return
    raise AssertionError("invalid fixed Gate link accepted")


def linked_gate(db, workflow, project, actor, *, link_changes=None, item_changes=None,
                root_changes=None, ref_changes=None, omit_link=False, omit_kind=None,
                extra_evidence=None, finish=True, omit_item=False, duplicate_ref=False):
    stage_key, version = db.execute("SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone()
    stage = next(s for s in six_stage_definition().stages if s.stage_key == stage_key)
    target = six_stage_definition().stages[stage.order].stage_key
    root = dict(workflow_id=workflow, project_id=project, definition_version=1,
        definition_fingerprint=definition_fingerprint(six_stage_definition()), transition_type="FORWARD",
        from_stage=stage_key, to_stage=target, before_lock_version=version, after_lock_version=version+1,
        actor_id=actor, reason="Synthetic Gate link proof, not customer approval", trace_id=uuid.uuid4(),
        occurred_at=datetime.now(timezone.utc), gate_fingerprint=b"g"*32)
    root.update(root_changes or {})
    transition = insert(db, GATE_TABLES[0], root, "stage_transition_id")
    for index, item in enumerate(stage.checklist_items):
        if omit_item and index == 1:
            continue
        row = db.execute("SELECT record_id,result,after_item_version,content_fingerprint,reason,impact FROM plm.wfl_checklist_records WHERE workflow_id=%s AND item_key=%s ORDER BY after_item_version DESC LIMIT 1", (workflow, item.item_key)).fetchone()
        record_id, result, item_version, fingerprint, reason, impact = row
        values = dict(stage_transition_id=transition, workflow_id=workflow, project_id=project,
            item_key=item.item_key, required=True, result=result,
            evidence_policy_ref=item.evidence_policy_ref, review_policy_ref=item.review_policy_ref,
            waiver_actor_id=actor if result == "WAIVED" else None,
            waiver_reason=reason if result == "WAIVED" else None,
            waiver_impact=impact if result == "WAIVED" else None)
        if not omit_link:
            values.update(checklist_record_id=record_id, observed_item_version=item_version, record_fingerprint=fingerprint)
        if index == 0:
            values.update(link_changes or {})
        values.update(item_changes or {})
        gate = insert(db, GATE_TABLES[1], values, "gate_item_id")
        refs = db.execute("SELECT ref_kind,ref_id,ref_scope,ref_project_id,observed_state,observed_lock_version,content_fingerprint FROM plm.wfl_checklist_record_refs WHERE record_id=%s ORDER BY ref_kind", (record_id,)).fetchall()
        if extra_evidence:
            scope, p, state, v, fp = db.execute("SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=%s", (extra_evidence,)).fetchone()
            refs.append(("EVIDENCE", extra_evidence, scope, p, state, v, fp))
        for kind, identity, scope, p, state, observed_version, fp in refs:
            if omit_kind == kind:
                continue
            # Genuine Evidence metadata re-observed; synthetic Review/exception kept explicitly.
            if kind == "EVIDENCE":
                scope, p, state, observed_version, fp = db.execute("SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=%s", (identity,)).fetchone()
            values = dict(gate_item_id=gate, workflow_id=workflow, project_id=project,
                ref_kind=kind, ref_id=identity, ref_scope=scope, ref_project_id=p,
                observed_state=state, observed_lock_version=observed_version,
                content_fingerprint=fp, verified_at=datetime.now(timezone.utc))
            if index == 0 and kind == "REVIEW_ROUND":
                values.update(ref_changes or {})
            insert(db, GATE_TABLES[2], values, "gate_ref_id")
            if duplicate_ref:
                insert(db, GATE_TABLES[2], values, "gate_ref_id")
    if finish:
        db.execute("UPDATE plm.wfl_stages SET stage_state='COMPLETED' WHERE workflow_id=%s AND stage_key=%s", (workflow, stage_key))
        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key=%s", (workflow, target))
        db.execute("UPDATE plm.wfl_project_workflows SET current_stage_key=%s,lock_version=lock_version+1 WHERE workflow_id=%s", (target, workflow))
    return transition


def legacy_snapshot(db, project=None):
    results = []
    for table, pk in zip(GATE_TABLES, ("stage_transition_id", "gate_item_id", "gate_ref_id")):
        query = sql.SQL("SELECT to_jsonb(t)-'checklist_record_id'-'observed_item_version'-'record_fingerprint' FROM plm.{} t").format(sql.Identifier(table))
        if project is not None:
            query += sql.SQL(" WHERE project_id=%s")
        query += sql.SQL(" ORDER BY {}").format(sql.Identifier(pk))
        results.append(db.execute(query, (project,) if project is not None else ()).fetchall())
    return tuple(results)


def main():
    name = "wflgatelink_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config = create_migration_config(URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0032")
            command.upgrade(config, "head")
            command.downgrade(config, "20260926_0032")
            with connect(name) as db:
                actor = insert(db, "auth_users", dict(username_display="Synthetic Gate link Owner", username_normalized="synthetic gate link owner"), "user_id")
                projects = [insert(db, "prj_projects", dict(project_code=f"LINK{i}", project_code_normalized=f"link{i}", name=f"Synthetic link {i}", created_by=actor), "project_id") for i in range(3)]
                with db.transaction():
                    workflows = [fixture.initialize(db, p, actor) for p in projects]
                for wf in workflows:
                    fixture.start(db, wf)
                workflow, legacy, other = workflows
                evidence = fixture.seed_evidence(db, projects[0], actor)
                global_evidence = fixture.seed_evidence(db, None, actor)
                legacy_evidence = fixture.seed_evidence(db, projects[1], actor)
                other_evidence = fixture.seed_evidence(db, projects[2], actor)
                with db.transaction():
                    fixture.fixture.history(db, legacy, projects[1], actor, legacy_evidence)
                for result in ("PASS", "FAIL", "PASS"):
                    with db.transaction():
                        current = fixture.record(db, workflow, projects[0], actor, evidence, result,
                            ref_changes={"observed_lock_version": 2}, ref_changes_kind="REVIEW_ROUND")
                with db.transaction():
                    issues = fixture.record(db, workflow, projects[0], actor, global_evidence, "WAIVED", item="HANDOVER_ISSUES")
                    foreign = fixture.record(db, other, projects[2], actor, other_evidence, "PASS")
                original_legacy = legacy_snapshot(db)
                old_records = fixture.snapshot(db)
            command.upgrade(config, "head")
            command.check(config)
            with connect(name) as db:
                assert legacy_snapshot(db) == original_legacy
                assert fixture.snapshot(db) == old_records
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NOT NULL").fetchone()[0] == 0
            # Nonempty legacy snapshots alone do not prohibit removing empty link columns.
            command.downgrade(config, "20260926_0032")
            command.upgrade(config, "head")
            with connect(name) as db:
                assert legacy_snapshot(db) == original_legacy and fixture.snapshot(db) == old_records
                def attempt(**kwargs):
                    return linked_gate(db, workflow, projects[0], actor, **kwargs)
                old = db.execute("SELECT record_id FROM plm.wfl_checklist_records WHERE workflow_id=%s AND item_key='HANDOVER_BASELINE' AND after_item_version=1", (workflow,)).fetchone()[0]
                failure = db.execute("SELECT record_id FROM plm.wfl_checklist_records WHERE workflow_id=%s AND result='FAIL'", (workflow,)).fetchone()[0]
                for changes in (dict(checklist_record_id=None), dict(observed_item_version=None),
                    dict(record_fingerprint=None), dict(record_fingerprint=b"x"), dict(record_fingerprint=b"x"*32),
                    dict(checklist_record_id=uuid.uuid4()), dict(checklist_record_id=uuid.UUID(int=0)),
                    dict(checklist_record_id=foreign), dict(checklist_record_id=issues),
                    dict(checklist_record_id=old, observed_item_version=1), dict(checklist_record_id=failure, observed_item_version=2),
                    dict(observed_item_version=0), dict(observed_item_version=2)):
                    reject(db, lambda changes=changes: attempt(link_changes=changes))
                for options in (dict(omit_link=True), dict(omit_item=True), dict(finish=False),
                    dict(omit_kind="EVIDENCE"), dict(omit_kind="REVIEW_ROUND"), dict(omit_kind="APPROVED_EXCEPTION"),
                    dict(extra_evidence=global_evidence), dict(duplicate_ref=True),
                    dict(ref_changes={"ref_id": uuid.uuid4()}), dict(ref_changes={"content_fingerprint": b"z"*32}),
                    dict(ref_changes={"observed_lock_version": 1}),
                    dict(ref_changes={"verified_at": datetime.now(timezone.utc)-timedelta(days=1)}),
                    dict(item_changes={"waiver_reason": "Other reason", "waiver_impact": "Other impact"})):
                    reject(db, lambda options=options: attempt(**options))
                def combined():
                    fixture.record(db, workflow, projects[0], actor, evidence, "PASS")
                    attempt()
                reject(db, combined)
                before = snapshot(db)
                try:
                    with db.transaction():
                        attempt()
                        raise RuntimeError("Synthetic Audit failure")
                except RuntimeError:
                    assert snapshot(db) == before
                # Reproof may have a newer Evidence version, but the fixed identity/hash is unchanged.
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_reason='Synthetic recheck',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                version = db.execute("SELECT lock_version FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone()[0]
                barrier = Barrier(2)
                def concurrent():
                    try:
                        with connect(name) as rival, rival.transaction():
                            barrier.wait(timeout=10)
                            linked_gate(rival, workflow, projects[0], actor,
                                root_changes=dict(from_stage="HANDOVER", to_stage="SURVEY", before_lock_version=version, after_lock_version=version+1))
                        return "success"
                    except psycopg.Error as exc:
                        assert exc.sqlstate == "P0001" and "current facts mismatch" in exc.diag.message_primary
                        return "conflict"
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert sorted(pool.map(lambda _: concurrent(), range(2))) == ["conflict", "success"]
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NOT NULL").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NULL").fetchone()[0] == 2
                assert db.execute("SELECT DISTINCT observed_lock_version FROM plm.wfl_transition_gate_refs WHERE workflow_id=%s AND ref_id=%s", (workflow, evidence)).fetchall() == [(2,)]
                # All five forward stages use current committed fixed records, not raw PASS fixtures.
                for stage in six_stage_definition().stages[1:-1]:
                    assert db.execute("SELECT current_stage_key FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone()[0] == stage.stage_key
                    for item in stage.checklist_items:
                        with db.transaction():
                            fixture.record(db, workflow, projects[0], actor, global_evidence, "PASS", item=item.item_key)
                    with db.transaction():
                        attempt()
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions WHERE workflow_id=%s", (workflow,)).fetchone()[0] == 5
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NOT NULL").fetchone()[0] == 10
                assert db.execute("SELECT current_stage_key FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone()[0] == "PLAN"
                assert legacy_snapshot(db, projects[1]) == original_legacy
                for operation in ("UPDATE", "DELETE", "TRUNCATE"):
                    statement = "UPDATE plm.wfl_transition_gate_items SET checklist_record_id=checklist_record_id" if operation == "UPDATE" else "DELETE FROM plm.wfl_transition_gate_items" if operation == "DELETE" else "TRUNCATE plm.wfl_transition_gate_items CASCADE"
                    reject(db, lambda statement=statement: db.execute(statement))
                # A committed legacy Gate cannot later acquire an inferred link.
                gate_id = db.execute("SELECT gate_item_id FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NULL LIMIT 1").fetchone()[0]
                reject(db, lambda: db.execute("UPDATE plm.wfl_transition_gate_items SET checklist_record_id=%s,observed_item_version=3,record_fingerprint=%s WHERE gate_item_id=%s", (current, fixture.HASH, gate_id)))
                before = snapshot(db)
            try:
                command.downgrade(config, "20260926_0032")
            except RuntimeError as exc:
                assert "Gate fixed record history exists" in str(exc)
            else:
                raise AssertionError("nonempty link down accepted")
            command.check(config)
            with connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260926_0034"
                assert snapshot(db) == before
            print("WFL-02-A01-P05 PASS: 0033 ORM/empty/legacy upgrade-down-reup, fixed current PASS/WAIVED records/exact basis, reproof/rollback/concurrency/immutability/nonempty down; synthetic Review/exception, not actual Gate")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
