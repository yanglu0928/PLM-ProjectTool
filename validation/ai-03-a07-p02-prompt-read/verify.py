"""Disposable PG18 check of Prompt metadata pagination and no-body projection."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.infrastructure.prompt_metadata_repository import SqlAlchemyPromptMetadataRepository
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a06-model-create-platform" / "verify.py"))
connect, seed_user = _helpers["connect"], _helpers["seed_user"]


def main() -> None:
    name = "ai03a07p02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = seed_user(db, "Synthetic Prompt Reader", "DEPLOYMENT_ADMIN", b"r" * 32)
                ids = [db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0] for _ in range(3)]
                system, user = "SYNTHETIC_SYSTEM_BODY_NOT_FOR_READ", "SYNTHETIC_USER_BODY_NOT_FOR_READ"
                for ident in ids[1:]:
                    db.execute(
                        "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
                        "user_template,system_template_hash,user_template_hash,output_schema_ref,"
                        "schema_version,rag_policy_ref,provider_policy_ref,created_by) "
                        "VALUES (%s,1,%s,%s,%s,%s,'schema.synthetic.v1',1,'rag.synthetic.v1',"
                        "'provider.synthetic.v1',%s)",
                        (ident, system, user, hashlib.sha256(system.encode()).hexdigest(),
                         hashlib.sha256(user.encode()).hexdigest(), actor),
                    )
                db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                           "active_version_no=1,lock_version=1 WHERE prompt_template_id=%s", (ids[1],))
                db.execute("UPDATE plm.ai_prompt_templates SET template_state='RETIRED',"
                           "active_version_no=1,lock_version=2 WHERE prompt_template_id=%s", (ids[2],))
            engine = create_engine(url)
            repo = SqlAlchemyPromptMetadataRepository()
            codec = PromptListCursorCodec(b"p" * 32)
            try:
                with Session(engine) as session:
                    session.begin()
                    tx = SimpleNamespace(session=session)
                    views = {ident: repo.get(tx, template_id=ident) for ident in ids}
                    assert views[ids[0]].state == "DRAFT" and views[ids[0]].active_version_no is None
                    assert views[ids[1]].state == "ACTIVE" and views[ids[1]].active_version_no == 1
                    assert views[ids[1]].output_schema_ref == "schema.synthetic.v1"
                    assert views[ids[2]].state == "RETIRED" and views[ids[2]].active_version_no is None
                    assert views[ids[2]].output_schema_ref is None
                    assert all(not hasattr(view, "system_template") for view in views.values())
                    assert system not in repr(views) and user not in repr(views)
                    first = repo.list_page(tx, after=None, limit=2)
                    assert len(first) == 2
                    token = codec.encode(session_token=b"r" * 32, page_size=2,
                                         created_at=first[-1].created_at,
                                         template_id=first[-1].template_id)
                    after = codec.decode(token, session_token=b"r" * 32, page_size=2)
                    second = repo.list_page(tx, after=after, limit=2)
                    assert len(second) == 1
                    assert {item.template_id for item in first + second} == set(ids)
            finally:
                engine.dispose()
            print("PASS: PG18 Prompt DRAFT/ACTIVE/RETIRED safe metadata, keyset, dedicated cursor")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
