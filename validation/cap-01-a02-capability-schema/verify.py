"""Windows 11/PostgreSQL 18 proof for Schema0091 Capability foundation."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261004_0090"


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    ))


def create_database(prefix: str) -> str:
    database = prefix + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    return database


def drop_database(database: str) -> None:
    with connect("postgres") as admin:
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
        )
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(database)))


def source_ref(document_version_id: uuid.UUID) -> str:
    body = f"capability-source-set.v1\n{document_version_id}".encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def reject(operation, expected: str) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"database operation unexpectedly succeeded: {expected}")


def seed_global_source(
    db,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    actor, file_id, document_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    version_id, evidence_id = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.auth_users(user_id,username_display,username_normalized,"
            "state,deployment_role) VALUES (%s,'Capability schema actor',"
            "'capability-schema-actor','DISABLED','DEPLOYMENT_ADMIN')", (actor,),
        )
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("""
            INSERT INTO plm.doc_file_objects(
              file_object_id,scope,storage_class,storage_locator,
              original_name_metadata,sha256,size_bytes,detected_mime,file_state,
              created_by,available_at)
            VALUES (%s,'GLOBAL','PERSISTENT','capability/schema-source.pdf',
              'schema-source.pdf',%s,16,'application/pdf','AVAILABLE',%s,
              statement_timestamp())
        """, (file_id, b"f" * 32, actor))
        db.execute("""
            INSERT INTO plm.doc_documents(
              document_id,scope,document_category,title,original_display_name,
              document_state,created_by)
            VALUES (%s,'GLOBAL','STANDARD_CAPABILITY','Schema source',
              'schema-source.pdf','ACTIVE',%s)
        """, (document_id, actor))
        db.execute("""
            INSERT INTO plm.doc_document_versions(
              document_version_id,document_id,scope,version_no,file_object_id,
              content_sha256,size_bytes,detected_mime,source_metadata,created_by,
              availability_state,integrity_checked_at)
            VALUES (%s,%s,'GLOBAL',1,%s,%s,16,'application/pdf','{}'::jsonb,
              %s,'AVAILABLE',statement_timestamp())
        """, (version_id, document_id, file_id, b"c" * 32, actor))
        db.execute("""
            INSERT INTO plm.evd_evidence_records(
              evidence_id,scope,document_id,document_version_id,locator_type,
              locator_schema_version,locator_payload,content_fingerprint,
              display_label,eligibility_state,eligibility_reason,created_by)
            VALUES (%s,'GLOBAL',%s,%s,'DOCUMENT',1,
              '{"locator_type":"DOCUMENT"}'::jsonb,%s,'Schema source evidence',
              'ELIGIBLE','schema fixture',%s)
        """, (evidence_id, document_id, version_id, b"e" * 32, actor))
    return actor, document_id, version_id, evidence_id


def insert_capability(db, actor: uuid.UUID, document_id: uuid.UUID,
                      version_id: uuid.UUID, evidence_id: uuid.UUID, *,
                      code: str, collection_ref: str | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    baseline_id, baseline_version_id = uuid.uuid4(), uuid.uuid4()
    item_row_id, stable_item_id = uuid.uuid4(), uuid.uuid4()
    ref = collection_ref or source_ref(version_id)
    db.execute("""
        INSERT INTO plm.cap_baselines(
          baseline_id,baseline_code,name,description,source_collection_ref,created_by)
        VALUES (%s,%s,'Capability schema baseline','synthetic schema proof',%s,%s)
    """, (baseline_id, code, ref, actor))
    db.execute("""
        INSERT INTO plm.cap_baseline_versions(
          baseline_version_id,baseline_id,version_no,source_collection_ref,
          content_fingerprint,declared_item_count,declared_document_ref_count,
          declared_evidence_ref_count,created_by)
        VALUES (%s,%s,1,%s,%s,1,1,1,%s)
    """, (baseline_version_id, baseline_id, ref, b"v" * 32, actor))
    db.execute("""
        INSERT INTO plm.cap_items(
          capability_item_row_id,baseline_version_id,baseline_id,
          capability_item_id,ordinal,capability_code,domain_name,module_name,
          feature_name,name,description,boundary_text,prerequisites,
          interface_refs,item_state)
        VALUES (%s,%s,%s,%s,0,%s,'PLM','Document','Versioning',
          'Document versioning','Immutable versions','GLOBAL standard only',
          ARRAY['PostgreSQL 18'],ARRAY['DOC-V1'],'AVAILABLE')
    """, (item_row_id, baseline_version_id, baseline_id, stable_item_id,
            code + ".ITEM"))
    db.execute("""
        INSERT INTO plm.cap_item_document_refs(
          capability_item_row_id,baseline_version_id,baseline_id,document_id,
          document_version_id,ordinal)
        VALUES (%s,%s,%s,%s,%s,0)
    """, (item_row_id, baseline_version_id, baseline_id, document_id, version_id))
    db.execute("""
        INSERT INTO plm.cap_item_evidence_refs(
          capability_item_row_id,baseline_version_id,baseline_id,evidence_id,ordinal)
        VALUES (%s,%s,%s,%s,0)
    """, (item_row_id, baseline_version_id, baseline_id, evidence_id))
    return baseline_id, baseline_version_id


def verify_empty_existing_and_drift() -> None:
    database = create_database("cap01a02empty_")
    try:
        cfg = config(database)
        command.upgrade(cfg, PREVIOUS)
        actor = uuid.uuid4()
        with connect(database) as db:
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized,state,deployment_role) VALUES "
                "(%s,'Existing actor','existing-capability-actor','DISABLED','NONE')",
                (actor,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s",
                              (actor,)).fetchone()[0] == 1
            tables = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='plm' AND table_name LIKE 'cap_%'"
            )}
            assert tables == {
                "cap_baselines", "cap_baseline_versions", "cap_items",
                "cap_item_document_refs", "cap_item_evidence_refs",
            }, tables
            project_columns = db.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema='plm' AND table_name LIKE 'cap_%' "
                "AND column_name='project_id'"
            ).fetchone()[0]
            assert project_columns == 0
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        drop_database(database)


def verify_constraints_and_retained_history() -> None:
    database = create_database("cap01a02data_")
    try:
        cfg = config(database)
        command.upgrade(cfg, "head")
        with connect(database) as db:
            actor, document_id, document_version_id, evidence_id = seed_global_source(db)
            with db.transaction():
                baseline_id, baseline_version_id = insert_capability(
                    db, actor, document_id, document_version_id, evidence_id,
                    code="CAP.SCHEMA.ONE",
                )
            row = db.execute("""
                SELECT b.current_approved_version_ref,v.version_state,
                       count(DISTINCT i.capability_item_row_id),
                       count(DISTINCT d.capability_item_document_ref_id),
                       count(DISTINCT e.capability_item_evidence_ref_id)
                  FROM plm.cap_baselines b
                  JOIN plm.cap_baseline_versions v ON v.baseline_id=b.baseline_id
                  JOIN plm.cap_items i ON i.baseline_version_id=v.baseline_version_id
                  JOIN plm.cap_item_document_refs d ON d.capability_item_row_id=i.capability_item_row_id
                  JOIN plm.cap_item_evidence_refs e ON e.capability_item_row_id=i.capability_item_row_id
                 WHERE b.baseline_id=%s AND v.baseline_version_id=%s
                 GROUP BY b.current_approved_version_ref,v.version_state
            """, (baseline_id, baseline_version_id)).fetchone()
            assert row == (None, "DRAFT", 1, 1, 1), row

            reject(lambda: _bad_fingerprint(
                db, actor, document_id, document_version_id, evidence_id),
                "source collection fingerprint is invalid")
            reject(lambda: db.execute(
                "UPDATE plm.cap_items SET name='changed' "
                "WHERE baseline_version_id=%s", (baseline_version_id,)),
                "immutable")
            reject(lambda: db.execute(
                "INSERT INTO plm.cap_baselines(baseline_code,name,"
                "source_collection_ref,current_approved_version_ref,created_by) "
                "VALUES ('CAP.BAD.POINTER','Bad pointer',%s,%s,%s)",
                (source_ref(document_version_id), uuid.uuid4(), actor)),
                "CapabilityBaseline initial state is invalid")
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Capability history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0091 downgrade accepted Capability history")
    finally:
        drop_database(database)


def _bad_fingerprint(db, actor, document_id, document_version_id, evidence_id) -> None:
    with db.transaction():
        insert_capability(
            db, actor, document_id, document_version_id, evidence_id,
            code="CAP.SCHEMA.BAD", collection_ref="sha256:" + "0" * 64,
        )


def main() -> None:
    verify_empty_existing_and_drift()
    verify_constraints_and_retained_history()
    print(
        "CAP_01_A02_CAPABILITY_SCHEMA_PASS: Schema0091 empty/existing upgrade, "
        "empty downgrade/re-upgrade, drift, complete GLOBAL source binding, "
        "owner closure and retained-history refusal verified on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
