"""Disposable DB/internal Port proof, not real authorization or Owner approval."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.workflow.application.current_checklist_record import ChecklistRecordReadError
from plm_assistant.modules.workflow.infrastructure.current_checklist_repository import SqlAlchemyCurrentChecklistRecordRepository

spec = spec_from_file_location("_record_fixture", Path(__file__).resolve().parents[1]
                              / "wfl-01-a05-p03-checklist-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    name = "wflcurrent_" + uuid.uuid4().hex[:12]
    engine = None
    with fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url)
            with fixture.connect(name) as db:
                actor = fixture.insert(db, "auth_users", dict(username_display="Synthetic current Owner",
                    username_normalized="synthetic current owner"), "user_id")
                projects = [fixture.insert(db, "prj_projects", dict(project_code=f"CUR{i}",
                    project_code_normalized=f"cur{i}", name=f"Synthetic current {i}", created_by=actor), "project_id") for i in range(2)]
                with db.transaction():
                    workflows = [fixture.initialize(db, p, actor) for p in projects]
                for workflow in workflows:
                    fixture.start(db, workflow)
                workflow, legacy = workflows
                evidence = fixture.seed_evidence(db, projects[0], actor)
                global_evidence = fixture.seed_evidence(db, None, actor)
                repository = SqlAlchemyCurrentChecklistRecordRepository()

                def get(item="HANDOVER_BASELINE", project=projects[0], wf=workflow):
                    with Session(engine) as session, session.begin():
                        return repository.get(SimpleNamespace(session=session), project, wf, item)

                before = fixture.snapshot(db)
                assert get() is None
                assert get(project=projects[1]) is None
                assert get(wf=uuid.uuid4()) is None
                assert fixture.snapshot(db) == before
                for bad in ("UNKNOWN", "handover_baseline", None):
                    try:
                        get(item=bad)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("invalid fixed Item accepted")
                with db.transaction():
                    first = fixture.record(db, workflow, projects[0], actor, evidence)
                empty = get()
                assert empty.record.record_id == first and empty.basis == ()
                with db.transaction():
                    second = fixture.record(db, workflow, projects[0], actor, evidence, "PASS")
                before = fixture.snapshot(db)
                passed = get()
                assert passed.record.record_id == second and passed.record.supersedes_record_id == first
                assert passed.record.after_item_version == 2 and passed.record.result.value == "PASS"
                assert {r.ref_kind for r in passed.basis} == {"EVIDENCE", "REVIEW_ROUND"}
                assert passed.content_fingerprint == fixture.HASH
                assert fixture.snapshot(db) == before
                # Another Item advances Workflow without invalidating this Item's current record.
                with db.transaction():
                    fixture.record(db, workflow, projects[0], actor, global_evidence, "WAIVED", item="HANDOVER_ISSUES")
                assert get().current_workflow_version > passed.current_workflow_version
                waived = get("HANDOVER_ISSUES")
                assert waived.record.result.value == "WAIVED" and waived.record.reason and waived.record.impact
                assert any(r.ref_scope == "GLOBAL" for r in waived.basis)
                # Later legitimate source changes preserve the recorded observation.
                db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic later change',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                assert next(r for r in get().basis if r.ref_kind == "EVIDENCE").observed_state == "ELIGIBLE"
                # Completed corrections form a full trusted chain, without auto-resuming BLOCKED.
                db.execute("UPDATE plm.wfl_stages SET stage_state='BLOCKED' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow,))
                with db.transaction():
                    corrected = fixture.record(db, workflow, projects[0], actor, evidence,
                        kinds=["EVIDENCE", "REVIEW_ROUND"], ref_changes={"observed_state": "RETURNED"},
                        ref_changes_kind="REVIEW_ROUND")
                failure = get()
                assert failure.record.record_id == corrected and failure.record.supersedes_record_id == second
                assert failure.record.result.value == "FAIL" and failure.observed_stage_state == "BLOCKED"
                assert {r.observed_state for r in failure.basis} == {"INELIGIBLE", "RETURNED"}
                # Current locks are retained until the caller ends its transaction.
                def try_update(table, condition, params):
                    with fixture.connect(name) as rival:
                        rival.execute("SET lock_timeout='150ms'")
                        try:
                            rival.execute(f"UPDATE plm.{table} SET lock_version=lock_version+1 WHERE {condition}", params)
                        except psycopg.errors.LockNotAvailable:
                            return "locked"
                        raise AssertionError("current fact escaped caller lock")
                with Session(engine) as session, session.begin():
                    repository.get(SimpleNamespace(session=session), projects[0], workflow, "HANDOVER_BASELINE")
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        tasks = [pool.submit(try_update, "wfl_project_workflows", "workflow_id=%s", (workflow,)),
                                 pool.submit(try_update, "wfl_checklist_items", "workflow_id=%s AND item_key=%s", (workflow, "HANDOVER_BASELINE"))]
                        assert [f.result() for f in tasks] == ["locked", "locked"]
                db.execute("UPDATE plm.wfl_project_workflows SET lock_version=lock_version+1 WHERE workflow_id=%s", (workflow,))
                # A raw synthetic legacy PASS and a newer unrecorded projection both fail closed.
                db.execute("UPDATE plm.wfl_checklist_items SET item_state='PASS',lock_version=1 WHERE workflow_id=%s AND item_key='HANDOVER_BASELINE'", (legacy,))
                db.execute("UPDATE plm.wfl_checklist_items SET item_state='FAIL',lock_version=lock_version+1 WHERE workflow_id=%s AND item_key='HANDOVER_BASELINE'", (workflow,))
                before = fixture.snapshot(db)
                for p, w in zip(projects, workflows):
                    try:
                        get(project=p, wf=w)
                    except ChecklistRecordReadError as exc:
                        assert str(exc) == "current Checklist record unavailable"
                    else:
                        raise AssertionError("unrecorded result accepted")
                assert fixture.snapshot(db) == before
                with Session(engine) as session:
                    try:
                        repository.get(SimpleNamespace(session=session), projects[0], workflow, "HANDOVER_BASELINE")
                    except RuntimeError:
                        assert not session.in_transaction()
                    else:
                        raise AssertionError("implicit transaction accepted")
            print("WFL-01-A05-P04 PASS: fixed current chain/basis, no writes, scope/stale rejection, caller locks; synthetic Owners only")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
