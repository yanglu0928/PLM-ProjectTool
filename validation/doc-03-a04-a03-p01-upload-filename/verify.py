"""Disposable PostgreSQL migration and upload filename contract verification."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement, args=()):
    try:
        with db.transaction():
            db.execute(statement, args)
    except psycopg.Error:
        return
    raise AssertionError("invalid upload filename accepted")


def main():
    name = "doc03a04p01_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            cfg = create_migration_config(url)
            command.upgrade(cfg, "20260925_0023")
            command.upgrade(cfg, "head")
            command.check(cfg)
            command.downgrade(cfg, "20260925_0023")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Filename Actor','synthetic filename actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('FN','fn','Filename Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Existing','old.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
                sql_insert = "INSERT INTO plm.doc_upload_intents(scope,project_id,actor_id,target_document_id,purpose_code,original_display_name,token_digest,expires_at) VALUES ('PROJECT',%s,%s,%s,'PROJECT_RECORD',%s,%s,statement_timestamp()+interval '15 minutes') RETURNING upload_id"
                old = db.execute(sql_insert, (project, actor, document, None, b"o" * 32)).fetchone()[0]
            command.upgrade(cfg, "head")
            command.check(cfg)
            with connect(name) as db:
                assert db.execute("SELECT original_display_name FROM plm.doc_upload_intents WHERE upload_id=%s", (old,)).fetchone() == (None,)
                rejected(db, sql_insert, (project, actor, document, None, b"n" * 32))
                rejected(db, sql_insert, (project, actor, document, " wrong.pdf ", b"s" * 32))
                rejected(db, "UPDATE plm.doc_upload_intents SET original_display_name='fabricated.pdf' WHERE upload_id=%s", (old,))
            command.downgrade(cfg, "20260925_0023")
            command.upgrade(cfg, "head")
            command.check(cfg)
            with connect(name) as db:
                named = db.execute(sql_insert, (project, actor, document, "new.pdf", b"v" * 32)).fetchone()[0]
                assert db.execute("SELECT original_display_name FROM plm.doc_upload_intents WHERE upload_id=%s", (named,)).fetchone() == ("new.pdf",)
            try:
                command.downgrade(cfg, "20260925_0023")
            except RuntimeError as exc:
                assert "downgrade refused" in str(exc)
            else:
                raise AssertionError("named history downgrade unexpectedly accepted")
            print("DOC-03-A04-A03-P01 PostgreSQL migration verification: PASS")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
