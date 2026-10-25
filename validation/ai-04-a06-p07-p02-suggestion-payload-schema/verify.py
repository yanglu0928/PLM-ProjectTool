"""Disposable PostgreSQL 18 proof for Schema0074 SuggestionPayload ownership."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb


PREVIOUS = "20261003_0073"


def load_invocation_helper():
    path = (
        Path(__file__).resolve().parents[1]
        / "ai-04-a06-p05-p02-invocation-plan-guard"
        / "verify.py"
    )
    spec = importlib.util.spec_from_file_location("suggestion_invocation_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid AI SuggestionPayload operation accepted")


PAYLOAD_INSERT = """
INSERT INTO plm.ai_suggestion_payloads(
 ai_invocation_id,ai_task_id,scope,project_id,output_schema_ref,schema_version,
 canonical_payload,payload_fingerprint,quality_flags)
VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,%s,%s)
RETURNING suggestion_payload_id
"""


EVIDENCE_INSERT = """
INSERT INTO plm.ai_suggestion_evidence_refs(
 suggestion_payload_id,ref_ordinal,scope,project_id,owner_module,object_type,
 object_id,version_id,content_fingerprint)
VALUES (%s,%s,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s,%s)
RETURNING suggestion_evidence_ref_id
"""


def create_bound_invocation(db, helper, content_helper, seed, suffix):
    parameters = Jsonb({"language": "zh-CN"})
    parameters_fingerprint = db.execute(
        "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
    ).fetchone()[0]
    plan = helper.create_plan(db, content_helper, seed, parameters_fingerprint)
    task = helper.create_task(
        db, seed, input_fingerprint=b"s" * 32,
        parameters_fingerprint=parameters_fingerprint, content_plan=plan,
    )
    snap = helper.snapshot(
        db, seed, task, input_fingerprint=b"s" * 32,
        payload_fingerprint=b"p" * 32, content_plan=plan,
    )
    invocation = db.execute(
        helper.INVOCATION_INSERT,
        helper.invocation_params(
            seed, task, 1, snap, input_fingerprint=b"s" * 32,
            payload_fingerprint=b"p" * 32, content_plan=plan,
        ),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.ai_tasks SET current_invocation_ref=%s,task_state='RUNNING',"
        "started_at=statement_timestamp(),lock_version=1 WHERE ai_task_id=%s",
        (invocation, task),
    )
    return task, invocation


def payload_params(seed, task, invocation, payload, fingerprint, flags=None):
    return (
        invocation, task, seed["project"], "gap-output.v1", 1,
        Jsonb(payload), fingerprint, Jsonb(flags or []),
    )


def main() -> None:
    helper = load_invocation_helper()
    content_helper = helper.load_helper()
    suffix = uuid.uuid4().hex[:10]
    names = {kind: f"ai04a06p07p02_{suffix}_{kind}"
             for kind in ("empty", "legacy", "bound")}
    created: list[str] = []
    with content_helper.connect("postgres") as admin:
        try:
            for name in names.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty_cfg = content_helper.config(names["empty"])
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)
            command.downgrade(empty_cfg, PREVIOUS)
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)

            legacy_cfg = content_helper.config(names["legacy"])
            command.upgrade(legacy_cfg, PREVIOUS)
            with content_helper.connect(names["legacy"]) as db:
                seed = content_helper.seed_foundation(db, suffix + "l")
                task, invocation = create_bound_invocation(
                    db, helper, content_helper, seed, suffix + "l",
                )
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)
            with content_helper.connect(names["legacy"]) as db:
                assert db.execute(
                    "SELECT suggestion_payload_ref FROM plm.ai_invocations "
                    "WHERE ai_invocation_id=%s", (invocation,),
                ).fetchone() == (None,)
                assert db.execute(
                    "SELECT to_regclass('plm.ai_suggestion_payloads'),"
                    "to_regclass('plm.ai_suggestion_evidence_refs')",
                ).fetchone() == (
                    "plm.ai_suggestion_payloads", "plm.ai_suggestion_evidence_refs",
                )
            command.downgrade(legacy_cfg, PREVIOUS)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)

            bound_cfg = content_helper.config(names["bound"])
            command.upgrade(bound_cfg, "head")
            command.check(bound_cfg)
            with content_helper.connect(names["bound"]) as db:
                seed = content_helper.seed_foundation(db, suffix + "b")
                task, invocation = create_bound_invocation(
                    db, helper, content_helper, seed, suffix + "b",
                )
                payload = {"items": [{"kind": "gap", "summary": "synthetic"}]}
                fingerprint = db.execute(
                    "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))",
                    (Jsonb(payload),),
                ).fetchone()[0]
                reject(
                    db, PAYLOAD_INSERT,
                    payload_params(seed, task, invocation, payload, fingerprint),
                )
                db.execute(
                    "UPDATE plm.ai_invocations SET invocation_state='RUNNING',"
                    "started_at=statement_timestamp(),lock_version=1 "
                    "WHERE ai_invocation_id=%s", (invocation,),
                )
                reject(
                    db, PAYLOAD_INSERT,
                    payload_params(
                        seed, task, invocation, payload, fingerprint,
                        ["DUPLICATE", "DUPLICATE"],
                    ),
                )
                reject(
                    db, PAYLOAD_INSERT,
                    (
                        invocation, task, seed["project"], "other-output.v1", 1,
                        Jsonb(payload), fingerprint, Jsonb([]),
                    ),
                )
                suggestion = db.execute(
                    PAYLOAD_INSERT,
                    payload_params(
                        seed, task, invocation, payload, fingerprint,
                        ["SYNTHETIC_EVIDENCE"],
                    ),
                ).fetchone()[0]
                object_id, version_id = uuid.uuid4(), uuid.uuid4()
                db.execute(
                    EVIDENCE_INSERT,
                    (suggestion, 1, seed["project"], object_id, version_id, b"e" * 32),
                )
                wrong_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES (%s,%s,'Other',%s) RETURNING project_id",
                    (f"OTH{suffix.upper()}", f"oth{suffix.lower()}", seed["actor"]),
                ).fetchone()[0]
                reject(
                    db, EVIDENCE_INSERT,
                    (suggestion, 2, wrong_project, uuid.uuid4(), uuid.uuid4(), b"e" * 32),
                )
                with db.transaction():
                    db.execute(
                        "UPDATE plm.ai_invocations SET suggestion_payload_ref=%s,"
                        "response_fingerprint=%s,schema_validation_state='VALID',"
                        "invocation_state='SUCCEEDED',completed_at=statement_timestamp(),"
                        "lock_version=2 WHERE ai_invocation_id=%s",
                        (suggestion, fingerprint, invocation),
                    )
                    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
                assert db.execute(
                    "SELECT fact_status,quality_flags FROM plm.ai_suggestion_payloads "
                    "WHERE suggestion_payload_id=%s", (suggestion,),
                ).fetchone() == ("NOT_FORMAL_FACT", ["SYNTHETIC_EVIDENCE"])
                reject(
                    db, EVIDENCE_INSERT,
                    (suggestion, 2, seed["project"], uuid.uuid4(), uuid.uuid4(), b"e" * 32),
                )
                reject(
                    db, "UPDATE plm.ai_suggestion_payloads SET quality_flags='[]'::jsonb "
                    "WHERE suggestion_payload_id=%s", (suggestion,),
                )
                reject(
                    db, "UPDATE plm.ai_invocations SET suggestion_payload_ref=%s "
                    "WHERE ai_invocation_id=%s", (uuid.uuid4(), invocation),
                )

            try:
                command.downgrade(bound_cfg, PREVIOUS)
            except Exception as error:
                assert "AI SuggestionPayload history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated SuggestionPayload downgrade accepted")

            print(
                "AI_04_A06_P07_P02_SUGGESTION_PAYLOAD_SCHEMA_PASS: Schema0074 empty "
                "and legacy up/down/re-up, ORM drift, old NULL preserved, PENDING/schema/"
                "scope/quality invalid writes rejected, RUNNING exact owned payload and typed "
                "evidence accepted, deferred Invocation FK and immutable sealing enforced, "
                "populated downgrade rejected"
            )
        finally:
            for name in reversed(created):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(name)))


if __name__ == "__main__":
    main()
