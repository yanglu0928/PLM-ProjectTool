"""Disposable PostgreSQL proof; never operates on a production database."""
import uuid

import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=55432, user="poc_admin", dbname=name, autocommit=True)


def initialize(db, project, actor, *, incomplete=False, altered=False):
    workflow = db.execute(
        "INSERT INTO plm.wfl_project_workflows(project_id,workflow_version,definition_fingerprint,created_by) VALUES(%s,1,%s,%s) RETURNING workflow_id",
        (project, definition_fingerprint(six_stage_definition()), actor),
    ).fetchone()[0]
    for stage in six_stage_definition().stages:
        stage_id = db.execute(
            "INSERT INTO plm.wfl_stages(workflow_id,project_id,stage_key,stage_order,gate_policy_ref) VALUES(%s,%s,%s,%s,%s) RETURNING stage_id",
            (workflow, project, stage.stage_key, stage.order, stage.gate_policy_ref),
        ).fetchone()[0]
        checklist = db.execute(
            "INSERT INTO plm.wfl_stage_checklists(stage_id,workflow_id,project_id) VALUES(%s,%s,%s) RETURNING stage_checklist_id",
            (stage_id, workflow, project),
        ).fetchone()[0]
        for item in stage.checklist_items:
            if incomplete and item.item_key == "PLAN_WBS_VALIDATION":
                continue
            db.execute(
                "INSERT INTO plm.wfl_checklist_items(stage_checklist_id,workflow_id,project_id,item_key,required,evidence_policy_ref,review_policy_ref) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (checklist, workflow, project, item.item_key, False if altered else item.required,
                 item.evidence_policy_ref, item.review_policy_ref),
            )
    return workflow


def reject(db, action):
    try:
        with db.transaction():
            action()
    except psycopg.Error:
        return
    raise AssertionError("invalid Workflow change accepted")


def main():
    name = "wfl01a03_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name,
            ))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0029")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES('Workflow Owner','workflow owner') RETURNING user_id").fetchone()[0]
                projects = [db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES(%s,%s,%s,%s) RETURNING project_id",
                    (f"WFL{i}", f"wfl{i}", f"Workflow {i}", actor),
                ).fetchone()[0] for i in range(3)]
                before = db.execute("SELECT * FROM plm.prj_projects ORDER BY project_id").fetchall()
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0029")
            command.upgrade(config, "head")
            with connect(name) as db:
                assert before == db.execute("SELECT * FROM plm.prj_projects ORDER BY project_id").fetchall()
                assert db.execute("SELECT count(*) FROM plm.wfl_project_workflows").fetchone()[0] == 0
                reject(db, lambda: initialize(db, projects[0], actor, incomplete=True))
                reject(db, lambda: initialize(db, projects[0], actor, altered=True))
                reject(db, lambda: db.execute("INSERT INTO plm.wfl_project_workflows(project_id,workflow_version,definition_fingerprint,created_by) VALUES(%s,2,%s,%s)", (projects[0], b"x"*32, actor)))
                reject(db, lambda: db.execute("INSERT INTO plm.wfl_project_workflows(project_id,workflow_version,definition_fingerprint,created_by) VALUES(%s,1,%s,%s)", (projects[0], b"x"*32, actor)))
                with db.transaction():
                    workflow = initialize(db, projects[0], actor)
                    second = initialize(db, projects[1], actor)
                reject(db, lambda: initialize(db, projects[0], actor))
                for table in ("wfl_project_workflows", "wfl_stages", "wfl_stage_checklists", "wfl_checklist_items"):
                    reject(db, lambda table=table: db.execute(sql.SQL("DELETE FROM plm.{} WHERE workflow_id=%s").format(sql.Identifier(table)), (workflow,)))
                for statement in (
                    "UPDATE plm.wfl_stages SET stage_order=20 WHERE workflow_id=%s AND stage_key='HANDOVER'",
                    "UPDATE plm.wfl_checklist_items SET required=false WHERE workflow_id=%s",
                    "UPDATE plm.wfl_project_workflows SET workflow_version=2,lock_version=1 WHERE workflow_id=%s",
                    "UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER' WHERE workflow_id=%s",
                    "UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'",
                ):
                    reject(db, lambda statement=statement: db.execute(statement, (workflow,)))
                reject(db, lambda: db.execute("INSERT INTO plm.wfl_stages(workflow_id,project_id,stage_key,stage_order,gate_policy_ref) VALUES(%s,%s,'EXTRA',7,'GATE_EXTRA_V1')", (workflow, projects[1])))
                # Full initial state is committed before a separate start transaction.
                with db.transaction():
                    db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1 WHERE workflow_id=%s", (workflow,))
                    db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                reject(db, lambda: db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='SURVEY'", (workflow,)))
                reject(db, lambda: db.execute("UPDATE plm.wfl_checklist_items SET review_policy_ref='FAKE',lock_version=1,item_state='PASS' WHERE workflow_id=%s", (workflow,)))
                reject(db, lambda: db.execute("UPDATE plm.wfl_checklist_items SET item_state='PASS' WHERE workflow_id=%s", (workflow,)))
                db.execute("UPDATE plm.wfl_stages SET stage_state='BLOCKED' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                reject(db, lambda: db.execute("UPDATE plm.wfl_stages SET stage_state='COMPLETED' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,)))
                db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                reject(db, lambda: db.execute("UPDATE plm.wfl_project_workflows SET current_stage_key='REQUIREMENT',lock_version=2 WHERE workflow_id=%s", (workflow,)))
                reject(db, lambda: db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='COMPLETED',lock_version=2 WHERE workflow_id=%s", (workflow,)))
                # Structural test only: no actual business Gate/Review is implied.
                keys = tuple(s.stage_key for s in six_stage_definition().stages)
                for index in range(1, len(keys)):
                    with db.transaction():
                        db.execute("UPDATE plm.wfl_stages SET stage_state='COMPLETED' WHERE workflow_id=%s AND stage_key=%s", (workflow, keys[index-1]))
                        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key=%s", (workflow, keys[index]))
                        db.execute("UPDATE plm.wfl_project_workflows SET current_stage_key=%s,lock_version=lock_version+1 WHERE workflow_id=%s", (keys[index], workflow))
                with db.transaction():
                    db.execute("UPDATE plm.wfl_stages SET stage_state='COMPLETED' WHERE workflow_id=%s AND stage_key='PLAN'", (workflow,))
                    db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='COMPLETED',lock_version=lock_version+1 WHERE workflow_id=%s", (workflow,))
                reject(db, lambda: db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',lock_version=lock_version+1 WHERE workflow_id=%s", (workflow,)))
                assert db.execute("SELECT workflow_state,current_stage_key FROM plm.wfl_project_workflows WHERE workflow_id=%s", (workflow,)).fetchone() == ("COMPLETED", "PLAN")
            try:
                command.downgrade(config, "20260926_0029")
            except RuntimeError as exc:
                assert "Workflow history exists" in str(exc)
            else:
                raise AssertionError("nonempty Workflow downgrade accepted")
            print("PASS: WFL-01 four tables, existing-data upgrade, empty down/re-up, ORM parity, deferred completeness, scope/identity/state/retention guards (not business Gate)")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
