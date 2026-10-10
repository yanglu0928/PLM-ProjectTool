"""Windows 11/PostgreSQL 18 proof for atomic Checklist record append."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.workflow.application.append_checklist_record import (
    AppendChecklistRecord,
    ChecklistRecordAppendError,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
    ChecklistRecordReadError,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.current_checklist_repository import (
    SqlAlchemyCurrentChecklistRecordRepository,
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
    "wfl_01_a07_p07_a02_fixture",
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
            "current_stage_key='HANDOVER',lock_version=1,"
            "updated_at=statement_timestamp() WHERE workflow_id=%s",
            (workflow_id,),
        )
        db.execute(
            "UPDATE plm.wfl_stages SET stage_state='ACTIVE' "
            "WHERE workflow_id=%s AND stage_key='HANDOVER'",
            (workflow_id,),
        )


def evidence_basis(db, evidence_id: uuid.UUID, project_id: uuid.UUID,
                   *, observed_state: str = "ELIGIBLE") -> ChecklistBasisObservation:
    scope, evidence_project, lock_version, fingerprint = db.execute(
        "SELECT scope,project_id,lock_version,content_fingerprint "
        "FROM plm.evd_evidence_records WHERE evidence_id=%s",
        (evidence_id,),
    ).fetchone()
    return ChecklistBasisObservation(
        "EVIDENCE", evidence_id, scope, evidence_project, observed_state,
        lock_version, bytes(fingerprint), datetime.now(timezone.utc), 1,
    )


def main() -> None:
    database = "wflappend_" + uuid.uuid4().hex[:12]
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
                    username_display="Synthetic Checklist writer",
                    username_normalized="synthetic checklist writer",
                ), "user_id")
                projects = [insert(db, "prj_projects", dict(
                    project_code=f"WAPPEND{index}",
                    project_code_normalized=f"wappend{index}",
                    name=f"Synthetic append {index}", created_by=actor,
                ), "project_id") for index in range(2)]
                with db.transaction():
                    workflows = [initialize(db, project, actor)
                                 for project in projects]
                for workflow in workflows:
                    start(db, workflow)
                evidence = seed_evidence(db, projects[0], actor)
                evidence_observation = evidence_basis(
                    db, evidence, projects[0],
                )

            runtime = create_database_runtime(url)
            writer = SqlAlchemyChecklistRecordAppendRepository()
            reader = SqlAlchemyCurrentChecklistRecordRepository()

            def command_for(result: ChecklistState, *, basis=()):
                return AppendChecklistRecord(
                    actor, uuid.uuid4(), result, basis,
                    datetime.now(timezone.utc),
                )

            # The repository owns neither commit nor rollback.
            with runtime.unit_of_work() as tx:
                lock = writer.lock_current(
                    tx, project_id=projects[1],
                    item_key="HANDOVER_BASELINE",
                    expected_workflow_version=1,
                )
                uncommitted = writer.append(
                    tx, lock=lock, command=command_for(ChecklistState.FAIL),
                )
                assert uncommitted.record.after_item_version == 1
            with connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s", (projects[1],),
                ).fetchone()[0] == 0
                assert db.execute(
                    "SELECT lock_version FROM plm.wfl_project_workflows "
                    "WHERE project_id=%s", (projects[1],),
                ).fetchone()[0] == 1

            review = ChecklistBasisObservation(
                "REVIEW_ROUND", uuid.uuid4(), "PROJECT", projects[0],
                "APPROVED", 0, b"r" * 32,
                datetime.now(timezone.utc), 1,
            )
            basis = tuple(sorted(
                (evidence_observation, review),
                key=lambda value: (value.ref_kind, str(value.ref_id)),
            ))
            with runtime.unit_of_work() as tx:
                lock = writer.lock_current(
                    tx, project_id=projects[0],
                    item_key="HANDOVER_BASELINE",
                    expected_workflow_version=1,
                )
                # Current mutable facts remain locked until caller completion.
                with connect(database) as rival:
                    rival.execute("SET lock_timeout='150ms'")
                    for table, predicate, values in (
                        ("wfl_project_workflows", "workflow_id=%s",
                         (workflows[0],)),
                        ("wfl_stages", "workflow_id=%s AND stage_key=%s",
                         (workflows[0], "HANDOVER")),
                        ("wfl_checklist_items",
                         "workflow_id=%s AND item_key=%s",
                         (workflows[0], "HANDOVER_BASELINE")),
                    ):
                        try:
                            rival.execute(
                                f"SELECT 1 FROM plm.{table} WHERE {predicate} "
                                "FOR UPDATE NOWAIT", values,
                            )
                        except psycopg.errors.LockNotAvailable:
                            rival.rollback()
                        else:
                            raise AssertionError(f"{table} lock escaped")
                first = writer.append(
                    tx, lock=lock,
                    command=command_for(ChecklistState.PASS, basis=basis),
                )
                tx.commit()
            assert first.record.result is ChecklistState.PASS
            assert first.current_workflow_version == 2
            assert {value.ref_kind for value in first.basis} == {
                "EVIDENCE", "REVIEW_ROUND",
            }

            with runtime.unit_of_work() as tx:
                lock = writer.lock_current(
                    tx, project_id=projects[0],
                    item_key="HANDOVER_BASELINE",
                    expected_workflow_version=2,
                )
                corrected = writer.append(
                    tx, lock=lock, command=command_for(ChecklistState.FAIL),
                )
                tx.commit()
            assert corrected.record.supersedes_record_id == first.record.record_id
            assert corrected.record.after_item_version == 2
            assert corrected.current_workflow_version == 3
            with runtime.unit_of_work() as tx:
                current = reader.get(
                    tx, projects[0], workflows[0], "HANDOVER_BASELINE",
                )
                assert current == corrected

            # Two writers using one expected version serialize; exactly one wins.
            barrier = Barrier(2)

            def compete(_index: int) -> str:
                barrier.wait(timeout=10)
                try:
                    with runtime.unit_of_work() as tx:
                        lock = writer.lock_current(
                            tx, project_id=projects[1],
                            item_key="HANDOVER_BASELINE",
                            expected_workflow_version=1,
                        )
                        writer.append(
                            tx, lock=lock,
                            command=command_for(ChecklistState.FAIL),
                        )
                        tx.commit()
                    return "success"
                except ChecklistRecordAppendError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(compete, range(2)))
            assert sorted(outcomes) == ["CONFLICT_VERSION", "success"], outcomes

            # Database truth rejects a forged positive Evidence observation.
            forged = ChecklistBasisObservation(
                "EVIDENCE", evidence_observation.ref_id,
                evidence_observation.ref_scope,
                evidence_observation.ref_project_id, "INELIGIBLE",
                evidence_observation.observed_lock_version,
                evidence_observation.content_fingerprint,
                datetime.now(timezone.utc), 1,
            )
            with connect(database) as db:
                before = db.execute(
                    "SELECT lock_version FROM plm.wfl_project_workflows "
                    "WHERE project_id=%s", (projects[0],),
                ).fetchone()[0]
            try:
                with runtime.unit_of_work() as tx:
                    lock = writer.lock_current(
                        tx, project_id=projects[0],
                        item_key="HANDOVER_BASELINE",
                        expected_workflow_version=before,
                    )
                    writer.append(
                        tx, lock=lock,
                        command=command_for(
                            ChecklistState.FAIL, basis=(forged,),
                        ),
                    )
                    tx.commit()
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "P0001"
            else:
                raise AssertionError("forged Evidence observation committed")
            with connect(database) as db:
                assert db.execute(
                    "SELECT lock_version FROM plm.wfl_project_workflows "
                    "WHERE project_id=%s", (projects[0],),
                ).fetchone()[0] == before
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records "
                    "WHERE project_id=%s", (projects[0],),
                ).fetchone()[0] == 2

                # Test-only corruption injection proves read-side digest closure.
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "UPDATE plm.wfl_checklist_records "
                        "SET content_fingerprint=%s WHERE record_id=%s",
                        (b"x" * 32, corrected.record.record_id),
                    )
            try:
                with runtime.unit_of_work() as tx:
                    reader.get(
                        tx, projects[0], workflows[0],
                        "HANDOVER_BASELINE",
                    )
            except ChecklistRecordReadError:
                pass
            else:
                raise AssertionError("corrupted Checklist digest accepted")

            print(
                "WFL_01_A07_P07_A02_CHECKLIST_APPEND_PASS: PostgreSQL 18 "
                "first/correction append, exact basis digest, caller rollback, "
                "ordered locks, two-writer serialization, database Evidence "
                "truth and read-side corruption rejection verified; synthetic "
                "Review identity only, no authorization/Audit/Gate claim"
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


if __name__ == "__main__":
    main()
