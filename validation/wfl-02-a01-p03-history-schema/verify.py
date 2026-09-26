"""Owned disposable PostgreSQL schema proof; synthetic Review/exception facts only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import uuid

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint


TABLES = ("wfl_stage_transitions", "wfl_transition_gate_items", "wfl_transition_gate_refs")
HASH = b"h" * 32


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=55432, user="poc_admin",
                          dbname=name, autocommit=True)


def insert(db, table, values, pk):
    return db.execute(sql.SQL("INSERT INTO plm.{} ({}) VALUES ({}) RETURNING {}").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, values)),
        sql.SQL(",").join(sql.Placeholder() for _ in values), sql.Identifier(pk)),
        tuple(values.values())).fetchone()[0]


def reject(db, action):
    before = db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0]
    try:
        with db.transaction():
            action()
    except psycopg.Error as exc:
        assert exc.sqlstate in ("P0001", "23514", "23503", "23505", "23502"), (exc.sqlstate, exc.diag.message_primary)
        assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == before
        return
    raise AssertionError("invalid Workflow history accepted")


def initialize(db, project, actor):
    workflow = insert(db, "wfl_project_workflows", dict(
        project_id=project, workflow_version=1,
        definition_fingerprint=definition_fingerprint(six_stage_definition()),
        created_by=actor), "workflow_id")
    for stage in six_stage_definition().stages:
        stage_id = insert(db, "wfl_stages", dict(workflow_id=workflow,
            project_id=project, stage_key=stage.stage_key, stage_order=stage.order,
            gate_policy_ref=stage.gate_policy_ref), "stage_id")
        checklist = insert(db, "wfl_stage_checklists", dict(stage_id=stage_id,
            workflow_id=workflow, project_id=project), "stage_checklist_id")
        for item in stage.checklist_items:
            insert(db, "wfl_checklist_items", dict(stage_checklist_id=checklist,
                workflow_id=workflow, project_id=project, item_key=item.item_key,
                required=item.required, evidence_policy_ref=item.evidence_policy_ref,
                review_policy_ref=item.review_policy_ref), "checklist_item_id")
    return workflow


def seed_evidence(db, project, actor):
    scope = "GLOBAL" if project is None else "PROJECT"
    document = insert(db, "doc_documents", dict(scope=scope, project_id=project,
        document_category="STANDARD_CAPABILITY" if project is None else "PROJECT_RECORD",
        title="Synthetic Gate basis", original_display_name="synthetic.pdf", created_by=actor), "document_id")
    file_id = insert(db, "doc_file_objects", dict(scope=scope, project_id=project,
        storage_class="PERSISTENT", storage_locator="synthetic/" + uuid.uuid4().hex,
        original_name_metadata="synthetic.pdf", created_by=actor, file_state="AVAILABLE",
        sha256=HASH, size_bytes=7, detected_mime="application/pdf",
        available_at=datetime.now(timezone.utc) + timedelta(minutes=1)), "file_object_id")
    with db.transaction():
        version = insert(db, "doc_document_versions", dict(document_id=document,
            scope=scope, project_id=project, version_no=1, file_object_id=file_id,
            content_sha256=HASH, size_bytes=7, detected_mime="application/pdf",
            source_metadata=Jsonb({}), created_by=actor), "document_version_id")
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s WHERE document_id=%s",
                   (version, version, document))
    evidence = insert(db, "evd_evidence_records", dict(scope=scope, project_id=project,
        document_id=document, document_version_id=version, locator_type="DOCUMENT",
        locator_payload=Jsonb({"locator_type": "DOCUMENT"}), content_fingerprint=HASH,
        display_label="Synthetic fixed basis", created_by=actor), "evidence_id")
    db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',eligibility_reason='Synthetic test',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s",
               (actor, evidence))
    return evidence


def history(db, workflow, project, actor, evidence, *, root_changes=None,
            item_changes=None, ref_changes=None, omit_item=False, omit_kind=None,
            waived=False, extra_exception=False, finish=True, change_evidence=False,
            duplicate_item=False, duplicate_ref=False):
    current, lock = db.execute("SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows WHERE workflow_id=%s",
                               (workflow,)).fetchone()
    stages = six_stage_definition().stages
    stage = next(s for s in stages if s.stage_key == current)
    next_index = stages.index(stage) + 1
    target = stages[next_index].stage_key if next_index < len(stages) else "HANDOVER"
    root = dict(workflow_id=workflow, project_id=project, definition_version=1,
        definition_fingerprint=definition_fingerprint(six_stage_definition()),
        transition_type="FORWARD", from_stage=current, to_stage=target,
        before_lock_version=lock, after_lock_version=lock+1, actor_id=actor,
        reason="Synthetic structure verification, not customer approval",
        occurred_at=datetime.now(timezone.utc), trace_id=uuid.uuid4(),
        gate_fingerprint=HASH, created_xid=1)
    root.update(root_changes or {})
    transition = insert(db, TABLES[0], root, "stage_transition_id")
    assert db.execute("SELECT created_xid=txid_current() FROM plm.wfl_stage_transitions WHERE stage_transition_id=%s",
                      (transition,)).fetchone()[0]
    for index, item in enumerate(stage.checklist_items):
        if omit_item and index == 1:
            continue
        result = "WAIVED" if waived and index == 0 else "PASS"
        db.execute("UPDATE plm.wfl_checklist_items SET item_state=%s,lock_version=lock_version+1 WHERE workflow_id=%s AND item_key=%s",
                   (result, workflow, item.item_key))
        values = dict(stage_transition_id=transition, workflow_id=workflow,
            project_id=project, item_key=item.item_key, required=True, result=result,
            evidence_policy_ref=item.evidence_policy_ref, review_policy_ref=item.review_policy_ref,
            waiver_actor_id=actor if result == "WAIVED" else None,
            waiver_reason="Synthetic approved exception" if result == "WAIVED" else None,
            waiver_impact="Synthetic bounded risk" if result == "WAIVED" else None)
        if index == 0:
            values.update(item_changes or {})
        gate = insert(db, TABLES[1], values, "gate_item_id")
        if duplicate_item and index == 0:
            insert(db, TABLES[1], values, "gate_item_id")
        kinds = ["EVIDENCE", "REVIEW_ROUND"]
        if result == "WAIVED" or extra_exception:
            kinds.append("APPROVED_EXCEPTION")
        for kind in kinds:
            if kind == omit_kind:
                continue
            scope, ref_project, state, version, fingerprint = db.execute(
                "SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=%s",
                (evidence,)).fetchone()
            values = dict(gate_item_id=gate, workflow_id=workflow, project_id=project,
                ref_kind=kind, ref_id=evidence if kind == "EVIDENCE" else uuid.uuid4(),
                ref_scope=scope if kind == "EVIDENCE" else "PROJECT",
                ref_project_id=ref_project if kind == "EVIDENCE" else project,
                observed_state=state if kind == "EVIDENCE" else "APPROVED",
                observed_lock_version=version if kind == "EVIDENCE" else 0,
                content_fingerprint=fingerprint, verified_at=datetime.now(timezone.utc))
            if index == 0 and kind == "EVIDENCE":
                values.update(ref_changes or {})
            insert(db, TABLES[2], values, "gate_ref_id")
            if duplicate_ref and index == 0 and kind == "EVIDENCE":
                insert(db, TABLES[2], values, "gate_ref_id")
    if finish:
        db.execute("UPDATE plm.wfl_stages SET stage_state='COMPLETED' WHERE workflow_id=%s AND stage_key=%s", (workflow, current))
        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key=%s", (workflow, target))
        db.execute("UPDATE plm.wfl_project_workflows SET current_stage_key=%s,lock_version=lock_version+1 WHERE workflow_id=%s", (target, workflow))
    if change_evidence:
        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic changed fact',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
    return transition


def main():
    name = "wflhist_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config = create_migration_config(URL.create("postgresql+psycopg",
                username="poc_admin", host="127.0.0.1", port=55432, database=name))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0030")
            command.upgrade(config, "head")
            command.downgrade(config, "20260926_0030")
            with connect(name) as db:
                actor = insert(db, "auth_users", dict(username_display="Synthetic History Owner",
                    username_normalized="synthetic history owner"), "user_id")
                projects = [insert(db, "prj_projects", dict(project_code=f"HIST{i}",
                    project_code_normalized=f"hist{i}", name=f"Synthetic history {i}",
                    created_by=actor), "project_id") for i in range(2)]
                with db.transaction():
                    workflow = initialize(db, projects[0], actor)
                    initialize(db, projects[1], actor)
                with db.transaction():
                    db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1 WHERE workflow_id=%s", (workflow,))
                    db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                before = db.execute("SELECT * FROM plm.wfl_project_workflows ORDER BY workflow_id").fetchall()
            command.upgrade(config, "head")
            command.check(config)
            # Empty history down is allowed even with existing Workflow instances.
            command.downgrade(config, "20260926_0030")
            command.upgrade(config, "head")
            # The original raw-state fixture is a legacy 0032 control, not a new
            # Gate bypass. 0033 new fixed-record insertion is tested separately.
            command.downgrade(config, "20260926_0032")
            with connect(name) as db:
                assert before == db.execute("SELECT * FROM plm.wfl_project_workflows ORDER BY workflow_id").fetchall()
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 0
                evidence = seed_evidence(db, projects[0], actor)
                global_evidence = seed_evidence(db, None, actor)
                other_evidence = seed_evidence(db, projects[1], actor)
                def attempt(**kwargs):
                    return history(db, workflow, projects[0], actor, evidence, **kwargs)
                for changes in ({"project_id": projects[1]}, {"definition_version": 2},
                                {"definition_fingerprint": b"x"*32}, {"before_lock_version": 0},
                                {"after_lock_version": 9}, {"actor_id": uuid.uuid4()},
                                {"trace_id": uuid.UUID(int=0)}, {"reason": ""},
                                {"gate_fingerprint": b"x"}, {"transition_type": "START"}):
                    reject(db, lambda changes=changes: attempt(root_changes=changes))
                for kwargs in (dict(omit_item=True), dict(omit_kind="EVIDENCE"),
                               dict(omit_kind="REVIEW_ROUND"), dict(waived=True, omit_kind="APPROVED_EXCEPTION"),
                               dict(extra_exception=True), dict(finish=False), dict(change_evidence=True),
                               dict(duplicate_item=True), dict(duplicate_ref=True)):
                    reject(db, lambda kwargs=kwargs: attempt(**kwargs))
                for changes in ({"required": False}, {"result": "FAIL"},
                                {"review_policy_ref": "FAKE"}, {"item_key": "SURVEY_CONCLUSION"},
                                {"project_id": projects[1]}, {"waiver_reason": "unapproved"}):
                    reject(db, lambda changes=changes: attempt(item_changes=changes))
                for changes in ({"ref_scope": "GLOBAL", "ref_project_id": None},
                                {"ref_project_id": projects[1]}, {"ref_id": uuid.uuid4()},
                                {"content_fingerprint": b"z"*32}, {"observed_state": "APPROVED"},
                                {"observed_lock_version": 9}, {"ref_id": uuid.UUID(int=0)},
                                {"proof_schema_version": 2}, {"project_id": projects[1]}):
                    reject(db, lambda changes=changes: attempt(ref_changes=changes))
                reject(db, lambda: history(db, workflow, projects[0], actor, other_evidence))
                stages = six_stage_definition().stages
                for index, stage in enumerate(stages):
                    for target_index, target in enumerate(stages):
                        if target_index != index + 1:
                            reject(db, lambda target=target: history(db, workflow, projects[0], actor,
                                global_evidence, root_changes={"to_stage": target.stage_key}))
                    if index == len(stages)-1:
                        break
                    if index == 0:
                        barrier = Barrier(2)
                        def concurrent():
                            try:
                                with connect(name) as child, child.transaction():
                                    barrier.wait(timeout=10)
                                    history(child, workflow, projects[0], actor, evidence,
                                            root_changes={"from_stage": "HANDOVER", "before_lock_version": 1, "after_lock_version": 2})
                                return "success"
                            except psycopg.Error as exc:
                                assert exc.sqlstate == "P0001" and "current facts mismatch" in exc.diag.message_primary
                                return "conflict"
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            assert sorted(pool.map(lambda _: concurrent(), range(2))) == ["conflict", "success"]
                    else:
                        with db.transaction():
                            history(db, workflow, projects[0], actor, global_evidence, waived=index == 1)
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 5
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items").fetchone()[0] == 10
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_refs").fetchone()[0] == 21
                # Alembic warns computed defaults cannot be changed; prove the generated result directly.
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_refs WHERE evidence_id IS DISTINCT FROM CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END").fetchone()[0] == 0
                assert db.execute("SELECT is_generated FROM information_schema.columns WHERE table_schema='plm' AND table_name='wfl_transition_gate_refs' AND column_name='evidence_id'").fetchone()[0] == "ALWAYS"
                for table in TABLES:
                    for operation in ("UPDATE", "DELETE", "TRUNCATE"):
                        statement = (sql.SQL("UPDATE plm.{} SET project_id=project_id").format(sql.Identifier(table))
                                     if operation == "UPDATE" else sql.SQL(operation + " plm.{} CASCADE").format(sql.Identifier(table))
                                     if operation == "TRUNCATE" else sql.SQL("DELETE FROM plm.{}").format(sql.Identifier(table)))
                        reject(db, lambda statement=statement: db.execute(statement))
                gate = db.execute("SELECT gate_item_id FROM plm.wfl_transition_gate_items LIMIT 1").fetchone()[0]
                reject(db, lambda: insert(db, TABLES[2], dict(gate_item_id=gate,
                    workflow_id=workflow, project_id=projects[0], ref_kind="REVIEW_ROUND",
                    ref_id=uuid.uuid4(), ref_scope="PROJECT", ref_project_id=projects[0],
                    observed_state="APPROVED", observed_lock_version=0,
                    content_fingerprint=HASH, verified_at=datetime.now(timezone.utc)), "gate_ref_id"))
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',eligibility_reason='Synthetic later revoke',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                assert db.execute("SELECT DISTINCT observed_state,observed_lock_version FROM plm.wfl_transition_gate_refs WHERE ref_id=%s", (evidence,)).fetchall() == [("ELIGIBLE", 1)]
            try:
                command.downgrade(config, "20260926_0030")
            except RuntimeError as exc:
                assert "Workflow success history exists" in str(exc)
            else:
                raise AssertionError("nonempty history downgrade accepted")
            command.upgrade(config, "head")
            command.check(config)
            with connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260926_0033"
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 5
            print("PASS: 0031 three-table ORM parity, empty up/down/re-up and existing Workflow unchanged; all 36 stage pairs, five valid histories, waiver/global basis, rejection rollback, concurrent expected version, immutability/sealing and retained observed Evidence after revoke; synthetic Review/exception, not Gate/production")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
