"""Disposable PostgreSQL verification for DOC-01 Document logical identity."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement: str, params: tuple[object, ...]) -> None:
    try:
        db.execute(statement, params)
    except (psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation,
            psycopg.errors.NotNullViolation):
        pass
    else:
        raise AssertionError("invalid Document identity accepted")


def main() -> None:
    name = "doc01a01_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0020")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Document Owner','synthetic document owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('DOC','doc','Synthetic Document Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('PROJECT',%s,'TEMPORARY','temp/projects/preexisting','preexisting.pdf',%s) RETURNING file_object_id",
                    (project, actor),
                ).fetchone()[0]
            command.upgrade(migration, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_documents").fetchone()[0] == 0
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (file_id,)).fetchone() == ("STAGED",)
            command.downgrade(migration, "20260925_0020")
            command.upgrade(migration, "head")
            command.check(migration)
            insert = (
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,document_subtype,"
                "document_purpose,title,original_display_name,created_by,document_state,"
                "latest_version_ref,effective_version_ref,lock_version) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING document_id"
            )
            base = ("PROJECT", project, "PROJECT_RECORD", None, None,
                    "Customer research", "research.docx", actor, "ACTIVE", None, None, 0)
            with connect(name) as db:
                document_id = db.execute(insert, base).fetchone()[0]
                db.execute(insert, ("GLOBAL", None, "STANDARD_CAPABILITY", None, None,
                                    "Standard manual", "manual.pdf", actor, "ACTIVE", None, None, 0))
                db.execute(insert, ("PROJECT", project, "OTHER", "CUSTOM_SPEC",
                                    "Project implementation", "Other document", "other.pdf",
                                    actor, "ACTIVE", None, None, 0))
                db.execute(insert, ("PROJECT", project, "GENERATED_ARTIFACT", None, None,
                                    "Generated report", "report.docx", actor, "ACTIVE", None, None, 0))
                invalid = (
                    ("PROJECT", None, *base[2:]),
                    ("GLOBAL", project, *base[2:]),
                    ("PROJECT", uuid.uuid4(), *base[2:]),
                    (*base[:2], "UNKNOWN", *base[3:]),
                    (*base[:2], "OTHER", None, None, *base[5:]),
                    ("GLOBAL", None, "GENERATED_ARTIFACT", *base[3:]),
                    (*base[:5], " Title", *base[6:]),
                    (*base[:6], "", *base[7:]),
                    (*base[:8], "UNKNOWN", *base[9:]),
                    (*base[:9], uuid.uuid4(), *base[10:]),
                    (*base[:11], -1),
                )
                for params in invalid:
                    rejected(db, insert, params)
                assert db.execute("SELECT scope,project_id,document_state,lock_version FROM plm.doc_documents WHERE document_id=%s", (document_id,)).fetchone() == ("PROJECT", project, "ACTIVE", 0)
                for statement, params in (
                    ("UPDATE plm.doc_documents SET scope='GLOBAL' WHERE document_id=%s", (document_id,)),
                    ("UPDATE plm.doc_documents SET project_id=%s WHERE document_id=%s", (None, document_id)),
                ):
                    try:
                        db.execute(statement, params)
                    except psycopg.errors.RaiseException:
                        pass
                    else:
                        raise AssertionError("Document immutable identity was changed")
            try:
                command.downgrade(migration, "20260925_0020")
            except RuntimeError as exc:
                assert "Document metadata exists" in str(exc)
            else:
                raise AssertionError("nonempty Document downgrade unexpectedly allowed")
            print("PASS: DOC-01-A01 Document empty/upgraded migration, ORM parity, scope/category/pointer checks and downgrade guard")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
