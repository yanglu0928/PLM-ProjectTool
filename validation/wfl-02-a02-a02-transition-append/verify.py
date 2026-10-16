"""Windows 11/PostgreSQL 18 proof for atomic Stage Transition append."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.workflow.application.append_checklist_record import (
    AppendChecklistRecord,
)
from plm_assistant.modules.workflow.application.append_stage_transition import (
    AppendStageTransition, StageTransitionAppendError, TransitionGateProof,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.stage_transition_repository import (
    SqlAlchemyStageTransitionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
PORT = 55434


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py",
    "wfl_02_a02_a02_fixture",
)
insert = fixture.insert
initialize = fixture.initialize
seed_evidence = fixture.seed_evidence


def connect(name: str):
    return psycopg.connect(
        host="127.0.0.1", port=PORT, user="poc_admin",
        dbname=name, autocommit=True,
    )


def start(db, workflow_id: uuid.UUID) -> None:
    with db.transaction():
        db.execute(
            "UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',"
            "current_stage_key='HANDOVER',lock_version=1 "
            "WHERE workflow_id=%s", (workflow_id,),
        )
        db.execute(
            "UPDATE plm.wfl_stages SET stage_state='ACTIVE' "
            "WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow_id,),
        )


def evidence_observation(db, evidence_id: uuid.UUID,
                         project_id: uuid.UUID) -> ChecklistBasisObservation:
    scope, evidence_project, state, version, fingerprint = db.execute(
        "SELECT scope,project_id,eligibility_state,lock_version,"
        "content_fingerprint FROM plm.evd_evidence_records "
        "WHERE evidence_id=%s", (evidence_id,),
    ).fetchone()
    assert evidence_project == project_id
    return ChecklistBasisObservation(
        "EVIDENCE", evidence_id, scope, evidence_project, state, version,
        bytes(fingerprint), datetime.now(timezone.utc), 1,
    )


def record_handover(runtime, writer, database: str, *, actor: uuid.UUID,
                    project: uuid.UUID, evidence: uuid.UUID):
    records = []
    for item_key in ("HANDOVER_BASELINE", "HANDOVER_ISSUES"):
        with connect(database) as db:
            evidence_value = evidence_observation(db, evidence, project)
        review = ChecklistBasisObservation(
            "REVIEW_ROUND", uuid.uuid4(), "PROJECT", project, "APPROVED",
            0, bytes(item_key.encode().ljust(32, b"r")[:32]),
            evidence_value.verified_at, 1,
        )
        basis = tuple(sorted(
            (evidence_value, review),
            key=lambda value: (value.ref_kind, str(value.ref_id)),
        ))
        with runtime.unit_of_work() as tx:
            version = 1 + len(records)
            lock = writer.lock_current(
                tx, project_id=project, item_key=item_key,
                expected_workflow_version=version,
            )
            current = writer.append(
                tx, lock=lock, command=AppendChecklistRecord(
                    actor, uuid.uuid4(), ChecklistState.PASS, basis,
                    datetime.now(timezone.utc),
                ),
            )
            tx.commit()
        records.append(current)
    return tuple(records)


def proofs_from(records, *, evidence_version: int | None = None):
    proofs = []
    for current in records:
        basis = current.basis
        if evidence_version is not None:
            basis = tuple(
                replace(value, observed_lock_version=evidence_version,
                        verified_at=datetime.now(timezone.utc))
                if value.ref_kind == "EVIDENCE" else value
                for value in basis
            )
        proofs.append(TransitionGateProof(current.record.item_key, basis))
    return tuple(proofs)


def snapshot(db, project: uuid.UUID):
    return tuple(db.execute(statement, (project,)).fetchall() for statement in (
        "SELECT workflow_state,current_stage_key,lock_version FROM "
        "plm.wfl_project_workflows WHERE project_id=%s",
        "SELECT stage_key,stage_state FROM plm.wfl_stages "
        "WHERE project_id=%s ORDER BY stage_order",
        "SELECT stage_transition_id,from_stage,to_stage,before_lock_version,"
        "after_lock_version,gate_fingerprint FROM plm.wfl_stage_transitions "
        "WHERE project_id=%s ORDER BY stage_transition_id",
        "SELECT item_key,result,checklist_record_id,observed_item_version,"
        "record_fingerprint FROM plm.wfl_transition_gate_items "
        "WHERE project_id=%s ORDER BY item_key",
        "SELECT ref_kind,ref_id,observed_lock_version,content_fingerprint "
        "FROM plm.wfl_transition_gate_refs WHERE project_id=%s "
        "ORDER BY gate_item_id,ref_kind,ref_id",
    ))


def main() -> None:
    database = "wfltransition_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database),
        ))
        runtime = None
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=database,
            )
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.check(config)
            with connect(database) as db:
                actor = insert(db, "auth_users", dict(
                    username_display="Synthetic Transition owner",
                    username_normalized="synthetic transition owner",
                ), "user_id")
                projects = [insert(db, "prj_projects", dict(
                    project_code=f"WTR{index}",
                    project_code_normalized=f"wtr{index}",
                    name=f"Synthetic transition {index}", created_by=actor,
                ), "project_id") for index in range(3)]
                with db.transaction():
                    workflows = [initialize(db, project, actor)
                                 for project in projects]
                for workflow in workflows:
                    start(db, workflow)
                evidence = [seed_evidence(db, project, actor)
                            for project in projects]
            runtime = create_database_runtime(url)
            checklist = SqlAlchemyChecklistRecordAppendRepository()
            transitions = SqlAlchemyStageTransitionRepository()
            records = [record_handover(
                runtime, checklist, database, actor=actor,
                project=project, evidence=evidence[index],
            ) for index, project in enumerate(projects)]

            # The repository owns no commit: leaving the UOW rolls everything back.
            rollback_command = AppendStageTransition(
                projects[0], "SURVEY", 3, actor, uuid.uuid4(),
                "Synthetic caller rollback", datetime.now(timezone.utc),
                proofs_from(records[0]),
            )
            with connect(database) as db:
                before = snapshot(db, projects[0])
            with runtime.unit_of_work() as tx:
                uncommitted = transitions.append(tx, command=rollback_command)
                assert uncommitted.snapshot.to_stage == "SURVEY"
            with connect(database) as db:
                assert snapshot(db, projects[0]) == before

            # Re-observe a mutable Evidence row at a newer lock version while
            # retaining the fixed identity/content fingerprint.
            with connect(database) as db:
                db.execute(
                    "UPDATE plm.evd_evidence_records SET "
                    "eligibility_reason='Synthetic current reproof',updated_by=%s,"
                    "lock_version=lock_version+1 WHERE evidence_id=%s",
                    (actor, evidence[0]),
                )
                evidence_version = db.execute(
                    "SELECT lock_version FROM plm.evd_evidence_records "
                    "WHERE evidence_id=%s", (evidence[0],),
                ).fetchone()[0]
            fresh_gates = proofs_from(
                records[0], evidence_version=evidence_version,
            )
            accepted = replace(
                rollback_command, trace_id=uuid.uuid4(),
                reason="Synthetic current Handover Gate reproof",
                occurred_at=datetime.now(timezone.utc),
                gates=fresh_gates,
            )
            with runtime.unit_of_work() as tx:
                result = transitions.append(tx, command=accepted)
                # Root/Stages remain locked until caller completion.
                with connect(database) as rival:
                    try:
                        rival.execute(
                            "SELECT 1 FROM plm.wfl_project_workflows "
                            "WHERE project_id=%s FOR UPDATE NOWAIT", (projects[0],),
                        )
                    except psycopg.errors.LockNotAvailable:
                        rival.rollback()
                    else:
                        raise AssertionError("Workflow transition lock escaped")
                tx.commit()
            assert result.snapshot.from_stage == "HANDOVER"
            assert result.snapshot.to_stage == "SURVEY"
            assert result.snapshot.before_lock_version == 3
            assert result.snapshot.after_lock_version == 4
            assert len(result.gates) == 2
            with runtime.unit_of_work() as tx:
                replay = transitions.get_transition(
                    tx, project_id=projects[0],
                    stage_transition_id=result.stage_transition_id,
                )
                assert replay == result
            with connect(database) as db:
                assert db.execute(
                    "SELECT current_stage_key,lock_version FROM "
                    "plm.wfl_project_workflows WHERE project_id=%s",
                    (projects[0],),
                ).fetchone() == ("SURVEY", 4)
                assert db.execute(
                    "SELECT stage_key,stage_state FROM plm.wfl_stages "
                    "WHERE project_id=%s AND stage_key IN ('HANDOVER','SURVEY') "
                    "ORDER BY stage_order", (projects[0],),
                ).fetchall() == [("HANDOVER", "COMPLETED"),
                                 ("SURVEY", "ACTIVE")]
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_transition_gate_items "
                    "WHERE project_id=%s AND checklist_record_id IS NOT NULL",
                    (projects[0],),
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_transition_gate_refs "
                    "WHERE project_id=%s", (projects[0],),
                ).fetchone()[0] == 4

            # A stale current Owner observation is rejected before any write.
            stale_basis = tuple(
                replace(value, content_fingerprint=b"z" * 32)
                if value.ref_kind == "EVIDENCE" else value
                for value in records[1][0].basis
            )
            stale_gates = (
                TransitionGateProof("HANDOVER_BASELINE", stale_basis),
                TransitionGateProof("HANDOVER_ISSUES", records[1][1].basis),
            )
            stale_command = AppendStageTransition(
                projects[1], "SURVEY", 3, actor, uuid.uuid4(),
                "Synthetic stale proof rejection", datetime.now(timezone.utc),
                stale_gates,
            )
            with connect(database) as db:
                before = snapshot(db, projects[1])
            try:
                with runtime.unit_of_work() as tx:
                    transitions.append(tx, command=stale_command)
                    tx.commit()
            except StageTransitionAppendError as error:
                assert error.code == "WORKFLOW_GATE_NOT_SATISFIED"
            else:
                raise AssertionError("stale Gate proof accepted")
            with connect(database) as db:
                assert snapshot(db, projects[1]) == before

            # Two callers with one expected version converge to one transition.
            concurrent_command = AppendStageTransition(
                projects[2], "SURVEY", 3, actor, uuid.uuid4(),
                "Synthetic concurrent transition",
                datetime.now(timezone.utc), proofs_from(records[2]),
            )
            barrier = Barrier(2)

            def compete(_index: int) -> str:
                barrier.wait(timeout=10)
                try:
                    with runtime.unit_of_work() as tx:
                        transitions.append(tx, command=concurrent_command)
                        tx.commit()
                    return "success"
                except StageTransitionAppendError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(compete, range(2)))
            assert sorted(outcomes) == ["CONFLICT_VERSION", "success"], outcomes
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_stage_transitions "
                    "WHERE project_id=%s", (projects[2],),
                ).fetchone()[0] == 1
            print(
                "WFL_02_A02_A02_TRANSITION_APPEND_PG_PASS: caller rollback, "
                "fresh Evidence reproof, immutable readback, fixed Record/refs, "
                "atomic Handover->Survey state, locks and concurrency verified"
            )
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(
                sql.Identifier(database),
            ))
    print("WFL_02_A02_A02_TRANSITION_APPEND_CLEANUP_PASS")


if __name__ == "__main__":
    main()
