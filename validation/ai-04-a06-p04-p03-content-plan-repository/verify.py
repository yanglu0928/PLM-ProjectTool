"""Windows/PostgreSQL proof for the Content Plan Repository and Owner."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
    content_plan_fingerprint,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
    AIExecutionContentPlanPersistenceError,
)
from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load_schema_helper():
    path = (Path(__file__).resolve().parents[1]
            / "ai-04-a06-p04-p02-content-plan-schema" / "verify.py")
    spec = importlib.util.spec_from_file_location("ai_content_plan_schema_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_plan(seed: dict[str, object], preview: uuid.UUID, object_id: uuid.UUID,
               version_id: uuid.UUID, canonical: bytes) -> tuple[AIExecutionContentPlan,
                                                                  AIExecutionEnvelope]:
    source = AIExecutionContentSourceIdentity(
        1, "DOC-02", "document", "DOCUMENT_VERSION", object_id, version_id,
        seed["project"], "DOCUMENT_PARSED_TEXT", uuid.uuid4(), uuid.uuid4(),
        "document-parser.standard", "1.0.0", "document.parse-result.v1",
        "document.parse.fixed.v1", b"r" * 32, b"c" * 32, b"q" * 32,
        2048, 6,
    )
    prompt = AIExecutionPromptIdentity(
        "gap-analysis.v1", 1, seed["prompt"], 1,
        seed["system_hash"], seed["user_hash"], "content-plan-chat.v1",
        "gap-output.v1", 1, "strict-placeholders.v1", 1,
    )
    plan = AIExecutionContentPlan(
        uuid.uuid4(), 1, seed["project"], "project-gap-analysis.v1",
        "GAP_ANALYSIS", b"s" * 32, (source,), prompt, b"t" * 32,
        AIExecutionContextIdentity("no-retrieval.v1", "NONE"),
        seed["provider"], seed["provider_config"], seed["model"],
        "content-plan-chat", "PROVIDER_MANAGED", "cn-beijing",
        ("DOCUMENT_TEXT",), "document-minimal.v1",
        "provider-neutral-json.v1", 1, "utf8-byte-upper-bound.v1", 1,
    )
    envelope = AIExecutionEnvelope(
        plan.content_plan_id, content_plan_fingerprint(plan),
        "provider-neutral-json.v1", 1, (source.projection_fingerprint,),
        canonical, 6, 128, "utf8-byte-upper-bound.v1", 1,
    )
    assert preview.int
    return plan, envelope


def main() -> None:
    helper = load_schema_helper()
    suffix = uuid.uuid4().hex[:10]
    database = f"ai04a06p04p03_{suffix}"
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    )
    with psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres",
                         autocommit=True, connect_timeout=5) as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            migration_config = create_migration_config(url)
            command.upgrade(migration_config, "head")
            command.check(migration_config)
            canonical = b'{"messages":[]}'
            with helper.connect(database) as db:
                seed = helper.seed_foundation(db, suffix)
                preview, object_id, version_id = helper.create_preview(
                    db, seed, payload_fingerprint=hashlib.sha256(canonical).digest(),
                )
                rollback_preview, rollback_object, rollback_version = helper.create_preview(
                    db, seed, payload_fingerprint=hashlib.sha256(canonical).digest(),
                )

            engine = create_engine(url, hide_parameters=True)
            factory = sessionmaker(
                bind=engine, autoflush=False, expire_on_commit=False, autobegin=False,
            )
            repository = SqlAlchemyAIExecutionContentPlanRepository()
            owner = AIExecutionContentPlanOwner(repository)
            plan, envelope = build_plan(
                seed, preview, object_id, version_id, canonical,
            )
            with SqlAlchemyUnitOfWork(factory) as transaction:
                persisted = owner.persist(
                    transaction, egress_preview_id=preview,
                    plan=plan, envelope=envelope,
                )
                assert persisted.plan == plan
                transaction.commit()

            with SqlAlchemyUnitOfWork(factory) as transaction:
                loaded = owner.get(
                    transaction, content_plan_id=plan.content_plan_id,
                )
                assert loaded == persisted
                replayed = owner.persist(
                    transaction, egress_preview_id=preview,
                    plan=plan, envelope=envelope,
                )
                assert replayed == persisted
                try:
                    owner.persist(
                        transaction, egress_preview_id=preview, plan=plan,
                        envelope=replace(envelope, input_tokens=129),
                    )
                except AIExecutionContentPlanPersistenceError as error:
                    assert error.code == "AI_EXECUTION_CONTENT_PLAN_CONFLICT"
                else:
                    raise AssertionError("drifted persisted Envelope replay accepted")
                transaction.commit()

            rollback_plan, rollback_envelope = build_plan(
                seed, rollback_preview, rollback_object, rollback_version, canonical,
            )
            with SqlAlchemyUnitOfWork(factory) as transaction:
                owner.persist(
                    transaction, egress_preview_id=rollback_preview,
                    plan=rollback_plan, envelope=rollback_envelope,
                )
                transaction.rollback()

            with engine.connect() as connection:
                assert connection.scalar(text(
                    "SELECT count(*) FROM plm.ai_execution_content_plans"
                )) == 1
                assert connection.scalar(text(
                    "SELECT count(*) FROM plm.ai_execution_content_sources"
                )) == 1
                assert connection.scalar(text(
                    "SELECT count(*) FROM plm.ai_invocations"
                )) == 0
            engine.dispose()
            print(
                "AI_04_A06_P04_P03_CONTENT_PLAN_REPOSITORY_PASS: exact no-content "
                "transactional persist/read/replay, plan/envelope fingerprint recompute, "
                "drift conflict, rollback and zero Invocation/provider I/O"
            )
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)
            ))


if __name__ == "__main__":
    main()
