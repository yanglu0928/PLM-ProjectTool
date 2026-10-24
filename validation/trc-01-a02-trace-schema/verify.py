"""Disposable PostgreSQL 18 TraceLink migration and protected-history proof."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
_INSERT = (
    "INSERT INTO plm.trc_links(scope,project_id,source_owner_module,source_object_type,"
    "source_object_id,source_version_id,source_project_id,target_owner_module,"
    "target_object_type,target_object_id,target_version_id,target_project_id,"
    "relation_type,created_by,trace_id) VALUES "
    "(%(scope)s,%(project_id)s,%(source_owner_module)s,%(source_object_type)s,"
    "%(source_object_id)s,%(source_version_id)s,%(source_project_id)s,"
    "%(target_owner_module)s,%(target_object_type)s,%(target_object_id)s,"
    "%(target_version_id)s,%(target_project_id)s,%(relation_type)s,"
    "%(created_by)s,%(trace_id)s) RETURNING trace_link_id"
)


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def rejected(db, statement: str, values: object) -> None:
    try:
        db.execute(statement, values)
    except psycopg.Error:
        return
    raise AssertionError("invalid TraceLink change was accepted")


def main() -> None:
    name = "trc01a02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            migration = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT,
                database=name,
            ))
            command.upgrade(migration, "20260926_0028")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Trace Shape Owner','trace shape owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('TRC1','trc1','Trace One',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('TRC2','trc2','Trace Two',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
            command.upgrade(migration, "head")
            command.check(migration)
            command.downgrade(migration, "20260926_0028")
            command.upgrade(migration, "head")
            base = {
                "scope": "PROJECT", "project_id": project,
                "source_owner_module": "document", "source_object_type": "DOC-02",
                "source_object_id": uuid.uuid4(), "source_version_id": uuid.uuid4(),
                "source_project_id": project,
                "target_owner_module": "requirement", "target_object_type": "REQ-03",
                "target_object_id": uuid.uuid4(), "target_version_id": uuid.uuid4(),
                "target_project_id": project, "relation_type": "DERIVED_FROM",
                "created_by": actor, "trace_id": uuid.uuid4(),
            }
            with connect(name) as db:
                first = db.execute(_INSERT, base).fetchone()[0]
                rejected(db, _INSERT, base)
                for changes in (
                    {"target_project_id": other},
                    {"source_project_id": other},
                    {"source_project_id": None, "relation_type": "REFINES"},
                    {"target_project_id": None},
                    {"source_owner_module": "auth", "source_object_type": "AUT-02"},
                    {"relation_type": "SUPPORTS"},
                    {"source_object_id": base["target_object_id"],
                     "source_version_id": base["target_version_id"],
                     "source_owner_module": "requirement",
                     "source_object_type": "REQ-03"},
                    {"source_version_id": uuid.UUID(int=0)},
                    {"link_state": "SUPERSEDED"},
                ):
                    with_change = {**base, **changes, "trace_id": uuid.uuid4()}
                    if "link_state" in changes:
                        rejected(db, _INSERT.replace(
                            "created_by,trace_id) VALUES",
                            "created_by,trace_id,link_state) VALUES",
                        ).replace("%(created_by)s,%(trace_id)s) RETURNING",
                                  "%(created_by)s,%(trace_id)s,%(link_state)s) RETURNING"),
                                 with_change)
                    else:
                        rejected(db, _INSERT, with_change)
                global_ref = {
                    **base, "source_owner_module": "capability",
                    "source_object_type": "CAP-02", "source_project_id": None,
                    "relation_type": "REFERENCES_CAPABILITY",
                    "trace_id": uuid.uuid4(),
                }
                cross = db.execute(_INSERT, global_ref).fetchone()[0]
                assert cross != first
                global_edge = {
                    **base, "scope": "GLOBAL", "project_id": None,
                    "source_project_id": None, "target_project_id": None,
                    "target_owner_module": "capability", "target_object_type": "CAP-02",
                    "relation_type": "REFINES", "trace_id": uuid.uuid4(),
                }
                global_id = db.execute(_INSERT, global_edge).fetchone()[0]
                assert global_id not in (first, cross)
                rejected(db, _INSERT, {**base, "scope": "GLOBAL", "project_id": None,
                                       "target_project_id": None,
                                       "trace_id": uuid.uuid4()})
                replacement = db.execute(_INSERT, {
                    **base, "target_version_id": uuid.uuid4(),
                    "trace_id": uuid.uuid4(),
                }).fetchone()[0]
                rejected(db, "UPDATE plm.trc_links SET target_version_id=%s "
                         "WHERE trace_link_id=%s", (uuid.uuid4(), first))
                rejected(db, "UPDATE plm.trc_links SET link_state='SUPERSEDED',"
                         "superseded_by_ref=%s WHERE trace_link_id=%s", (global_id, first))
                db.execute("UPDATE plm.trc_links SET link_state='SUPERSEDED',"
                           "superseded_by_ref=%s WHERE trace_link_id=%s",
                           (replacement, first))
                rejected(db, "UPDATE plm.trc_links SET link_state='REVOKED',"
                         "superseded_by_ref=NULL WHERE trace_link_id=%s", (first,))
                db.execute("UPDATE plm.trc_links SET link_state='REVOKED' "
                           "WHERE trace_link_id=%s", (replacement,))
                rejected(db, "DELETE FROM plm.trc_links WHERE trace_link_id=%s", (first,))
                assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 4
            try:
                command.downgrade(migration, "20260926_0028")
            except RuntimeError as exc:
                assert "TraceLink history exists" in str(exc)
            else:
                raise AssertionError("nonempty TraceLink history downgrade accepted")
            print("PASS: TRC-01-A02 existing-data upgrade, empty down/re-up, ORM parity, "
                  "scope/type/unique/state/retention guards")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
