"""Disposable DB/internal Port proof, not real authorization or Owner approval."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
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
from plm_assistant.modules.workflow.application.checklist_record_integrity import checklist_record_fingerprint
from plm_assistant.modules.workflow.application.current_checklist_record import ChecklistBasisObservation, ChecklistRecordReadError
from plm_assistant.modules.workflow.domain.checklist_record import ChecklistRecordSnapshot
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.current_checklist_repository import SqlAlchemyCurrentChecklistRecordRepository

spec = spec_from_file_location("_record_fixture", Path(__file__).resolve().parents[1]
                              / "wfl-01-a05-p03-checklist-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def seal_synthetic_record(db, record_id):
    """Replace the old schema-test placeholder with the production digest."""
    root = db.execute(
        "SELECT record_id,workflow_id,project_id,actor_id,trace_id,"
        "definition_version,stage_key,item_key,before_state,result,"
        "before_item_version,after_item_version,before_workflow_version,"
        "after_workflow_version,occurred_at,supersedes_record_id,reason,"
        "impact,observed_stage_state FROM plm.wfl_checklist_records "
        "WHERE record_id=%s", (record_id,),
    ).fetchone()
    refs = db.execute(
        "SELECT ref_kind,ref_id,ref_scope,ref_project_id,observed_state,"
        "observed_lock_version,content_fingerprint,verified_at,"
        "proof_schema_version FROM plm.wfl_checklist_record_refs "
        "WHERE record_id=%s ORDER BY ref_kind,ref_id", (record_id,),
    ).fetchall()
    basis = tuple(ChecklistBasisObservation(
        value[0], value[1], value[2], value[3], value[4], value[5],
        bytes(value[6]), value[7].astimezone(timezone.utc), value[8],
    ) for value in refs)
    snapshot = ChecklistRecordSnapshot(
        root[0], root[1], root[2], root[3], root[4], root[5], root[6],
        root[7], ChecklistState(root[8]), ChecklistState(root[9]), root[10],
        root[11], root[12], root[13], root[14].astimezone(timezone.utc),
        root[15], tuple(value.ref_id for value in basis
                        if value.ref_kind == "EVIDENCE"),
        tuple(value.ref_id for value in basis
              if value.ref_kind == "REVIEW_ROUND"),
        tuple(value.ref_id for value in basis
              if value.ref_kind == "APPROVED_EXCEPTION"),
        root[16], root[17],
    )
    fingerprint = checklist_record_fingerprint(snapshot, basis, root[18])
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.wfl_checklist_records SET content_fingerprint=%s "
            "WHERE record_id=%s", (fingerprint, record_id),
        )
    return fingerprint


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
                seal_synthetic_record(db, first)
                empty = get()
                assert empty.record.record_id == first and empty.basis == ()
                with db.transaction():
                    second = fixture.record(db, workflow, projects[0], actor, evidence, "PASS")
                second_hash = seal_synthetic_record(db, second)
                before = fixture.snapshot(db)
                passed = get()
                assert passed.record.record_id == second and passed.record.supersedes_record_id == first
                assert passed.record.after_item_version == 2 and passed.record.result.value == "PASS"
                assert {r.ref_kind for r in passed.basis} == {"EVIDENCE", "REVIEW_ROUND"}
                assert passed.content_fingerprint == second_hash
                assert fixture.snapshot(db) == before
                # Another Item advances Workflow without invalidating this Item's current record.
                with db.transaction():
                    waived_record = fixture.record(db, workflow, projects[0], actor, global_evidence, "WAIVED", item="HANDOVER_ISSUES")
                seal_synthetic_record(db, waived_record)
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
                seal_synthetic_record(db, corrected)
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
