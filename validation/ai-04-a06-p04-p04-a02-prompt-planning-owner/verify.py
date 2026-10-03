"""Windows/PostgreSQL proof for the current Prompt planning Owner."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptContentError,
    AIExecutionPromptPlanningOwner,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
    ResolvedAITaskSubmissionPolicy,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_planning_repository import (
    SqlAlchemyAIExecutionPromptPlanningRepository,
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


def main() -> None:
    helper = load_schema_helper()
    suffix = uuid.uuid4().hex[:10]
    database = f"ai04a06p04p04a02_{suffix}"
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
            with helper.connect(database) as db:
                seed = helper.seed_foundation(db, suffix)

            policy_definition = AITaskSubmissionPolicy(
                "gap-analysis.v1", 1, "GAP_ANALYSIS", seed["prompt"],
                "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
                (AITaskParameterField("language", "STRING", True, 16),),
            )
            policy = AITaskSubmissionPolicyRegistry({
                policy_definition.reference: policy_definition,
            }).resolve(
                reference="gap-analysis.v1", task_type="GAP_ANALYSIS",
                output_schema_ref="gap-output.v1",
                context_policy_ref="no-retrieval.v1",
                parameters={"language": "zh-CN"},
            )
            engine = create_engine(url, hide_parameters=True)
            factory = sessionmaker(
                bind=engine, autoflush=False, expire_on_commit=False,
                autobegin=False,
            )
            owner = AIExecutionPromptPlanningOwner(
                SqlAlchemyAIExecutionPromptPlanningRepository(),
            )
            with SqlAlchemyUnitOfWork(factory) as transaction:
                content = owner.resolve_current(transaction, policy=policy)
                assert content.prompt_template_id == seed["prompt"]
                assert content.prompt_version_no == 1
                assert content.system_template_hash == seed["system_hash"]
                assert content.user_template_hash == seed["user_hash"]
                assert dict(content.task_parameters) == {"language": "zh-CN"}
                assert "zh-CN" not in repr(content)
                assert "System" not in repr(content)
                with helper.connect(database) as verifier:
                    expected = verifier.execute(
                        "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))",
                        (Jsonb({"language": "zh-CN"}),),
                    ).fetchone()[0]
                    assert content.task_parameters_fingerprint == expected
                    verifier.execute("SET lock_timeout='250ms'")
                    try:
                        with verifier.transaction():
                            verifier.execute(
                                "UPDATE plm.ai_prompt_templates "
                                "SET lock_version=lock_version+1 "
                                "WHERE prompt_template_id=%s", (seed["prompt"],),
                            )
                    except psycopg.Error as error:
                        assert error.sqlstate in {"55P03", "57014"}, error.sqlstate
                    else:
                        raise AssertionError("Prompt planning read did not retain a row lock")
                transaction.rollback()

            drifted = ResolvedAITaskSubmissionPolicy(
                policy.reference, policy.policy_version, policy.task_type,
                policy.prompt_template_id, policy.purpose_ref, "other-output.v1",
                policy.context_policy_ref, policy.task_parameters_json,
            )
            with SqlAlchemyUnitOfWork(factory) as transaction:
                try:
                    owner.resolve_current(transaction, policy=drifted)
                except AIExecutionPromptContentError:
                    pass
                else:
                    raise AssertionError("Prompt metadata drift was accepted")
                transaction.rollback()

            with engine.connect() as connection:
                assert connection.scalar(text(
                    "SELECT count(*) FROM plm.ai_execution_content_plans"
                )) == 0
                assert connection.scalar(text(
                    "SELECT count(*) FROM plm.ai_invocations"
                )) == 0
            engine.dispose()
            print(
                "AI_04_A06_P04_P04_A02_PROMPT_PLANNING_OWNER_PASS: active-version "
                "projection, server-side JSONB fingerprint, transaction row lock, "
                "sensitive repr exclusion, drift fail-closed and zero provider I/O"
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
