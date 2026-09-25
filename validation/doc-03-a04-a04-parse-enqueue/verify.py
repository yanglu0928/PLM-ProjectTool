"""Synthetic isolated PostgreSQL proof of cross-owner Parse Job enqueue."""

from __future__ import annotations

import uuid
from dataclasses import replace

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import func, select, text
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.application.parse_enqueue import ParseEnqueueError, ParseJobQueue, ParseJobRequest
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def verify() -> None:
    name = "parse_queue_" + uuid.uuid4().hex[:12]
    admin = psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        runtime = create_database_runtime(url)
        queue = ParseJobQueue(SqlAlchemyParseJobQueueRepository())
        actor = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.execute(text(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized,deployment_role) VALUES (:id,'parse-test','parse-test','DEPLOYMENT_ADMIN')"
            ), {"id": actor})
            tx.commit()
        global_request = ParseJobRequest(
            upload_id=uuid.uuid4(), document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(), version_no=1,
            scope="GLOBAL", project_id=None, actor_id=actor,
            trace_id=uuid.uuid4(),
        )
        try:
            with runtime.unit_of_work() as tx:
                queue.enqueue_parse(tx, request=global_request)
                raise RuntimeError("caller failed")
        except RuntimeError:
            pass
        with runtime.unit_of_work() as tx:
            assert tx.session.scalar(select(func.count()).select_from(JobRow)) == 0
            assert tx.session.scalar(select(func.count()).select_from(OutboxEventRow)) == 0
        with runtime.unit_of_work() as tx:
            first = queue.enqueue_parse(tx, request=global_request)
            tx.commit()
        with runtime.unit_of_work() as tx:
            replay = queue.enqueue_parse(tx, request=global_request)
            tx.commit()
        assert first == replay
        with runtime.unit_of_work() as tx:
            assert tx.session.scalar(select(func.count()).select_from(JobRow)) == 1
            assert tx.session.scalar(select(func.count()).select_from(OutboxEventRow)) == 1
            job = tx.session.get(JobRow, first.job_id)
            event = tx.session.get(OutboxEventRow, first.event_id)
            assert job.payload_refs == {"document_id": str(global_request.document_id),
                                        "document_version_id": str(global_request.document_version_id)}
            assert event.payload_refs == {"job_id": str(first.job_id),
                                          "document_version_id": str(global_request.document_version_id)}
        try:
            with runtime.unit_of_work() as tx:
                queue.enqueue_parse(tx, request=replace(global_request, document_version_id=uuid.uuid4()))
        except ParseEnqueueError as exc:
            assert exc.code == "CONFLICT_STATE"
        else:
            raise AssertionError("same upload accepted different version")
        with runtime.unit_of_work() as tx:
            project = tx.session.execute(text(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('PARSER','parser','Synthetic Parser Project',:actor) RETURNING project_id"
            ), {"actor": actor}).scalar_one()
            tx.commit()
        project_request = replace(global_request, upload_id=uuid.uuid4(),
                                  scope="PROJECT", project_id=project)
        with runtime.unit_of_work() as tx:
            queued = queue.enqueue_parse(tx, request=project_request)
            tx.commit()
        with runtime.unit_of_work() as tx:
            job = tx.session.get(JobRow, queued.job_id)
            event = tx.session.get(OutboxEventRow, queued.event_id)
            assert job.scope == event.scope == "PROJECT"
            assert job.project_id == event.project_id == project
        print("PASS: caller rollback, same-key replay/conflict, minimal refs and GLOBAL/PROJECT scope")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
