"""Disposable PG18 proof for AI-03 Prompt schema; synthetic data only."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a01-model-schema" / "verify.py"))
connect, reject = _helpers["connect"], _helpers["reject"]
PREVIOUS = "20261002_0058"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                      port=55434, database=name)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai03a02_{suffix}_{kind}" for kind in ("empty", "data")]
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            empty_config, data_config = create_migration_config(url(empty)), create_migration_config(url(data))
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_prompt_templates").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_prompt_templates')").fetchone()[0] is None
                assert db.execute("SELECT to_regclass('plm.ai_prompt_versions')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Prompt Owner','synthetic prompt owner') RETURNING user_id"
                ).fetchone()[0]
                # Existing auth data proves upgrade over a non-empty predecessor.
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                template = db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('SURVEY_GENERATE',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0]
                system, user = "Synthetic system template", "Synthetic user template {input}"
                system_hash = hashlib.sha256(system.encode()).hexdigest()
                user_hash = hashlib.sha256(user.encode()).hexdigest()
                insert_version = (
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
                    "user_template,system_template_hash,user_template_hash,output_schema_ref,schema_version,"
                    "rag_policy_ref,provider_policy_ref,created_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'schema.synthetic.v1',1,'rag.synthetic.v1',"
                    "'provider.synthetic.v1',%s)"
                )
                db.execute(insert_version, (template, 1, system, user, system_hash, user_hash, actor))
                db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                           "active_version_no=1,lock_version=1 WHERE prompt_template_id=%s", (template,))
                assert db.execute("SELECT template_state,active_version_no FROM plm.ai_prompt_templates "
                                  "WHERE prompt_template_id=%s", (template,)).fetchone() == ("ACTIVE", 1)
                reject(db, "UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                       "active_version_no=1 WHERE prompt_template_id=%s", (other,))
                reject(db, "UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                       "active_version_no=2 WHERE prompt_template_id=%s", (template,))
                reject(db, "UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                       "active_version_no=NULL WHERE prompt_template_id=%s", (other,))
                reject(db, "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                       "VALUES ('INVALID',%s)", (actor,))
                reject(db, insert_version, (other, 0, system, user, system_hash, user_hash, actor))
                reject(db, insert_version, (other, 1, system, user, "not-a-hash", user_hash, actor))
                reject(db, "UPDATE plm.ai_prompt_versions SET system_template='changed' "
                       "WHERE prompt_template_id=%s", (template,))
                reject(db, "DELETE FROM plm.ai_prompt_versions WHERE prompt_template_id=%s", (template,))
                reject(db, "TRUNCATE plm.ai_prompt_versions CASCADE")
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "Prompt history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated Prompt downgrade accepted")
            print("PASS: 0059 empty up/down/re-up, predecessor-data upgrade, drift=0, active FK, immutable version, nonempty downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
