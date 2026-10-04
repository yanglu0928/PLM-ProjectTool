from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

import alembic.command
from alembic.config import Config
import psycopg

from schema_contract import ROOT_TABLE_NAMES, metadata
from schema_manifest import QUERY_IDS, ROOTS, SCHEMA_CONTRACT_VERSION, VALIDATION_ONLY


EMPTY_DB = "sc04_empty"
DATA_DB = "sc04_data"
RESTORE_DB = "sc04_restore"
DATABASES = (EMPTY_DB, DATA_DB, RESTORE_DB)
FORBIDDEN_COLUMNS = {"api_key", "private_key", "password_plain", "session_token"}


def admin_url(port: int, database: str = "postgres") -> str:
    return f"postgresql://poc_admin@127.0.0.1:{port}/{database}"


def sqlalchemy_url(port: int, database: str) -> str:
    return f"postgresql+psycopg://poc_admin@127.0.0.1:{port}/{database}"


def recreate_database(port: int, database: str) -> None:
    with psycopg.connect(admin_url(port), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname=%s AND pid<>pg_backend_pid()",
            (database,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{database}"')
        connection.execute(f'CREATE DATABASE "{database}"')


def drop_database(port: int, database: str) -> None:
    with psycopg.connect(admin_url(port), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname=%s AND pid<>pg_backend_pid()",
            (database,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{database}"')


def alembic_config(root: Path, port: int, database: str) -> Config:
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlalchemy_url(port, database))
    return config


def manifest_validation(root: Path) -> dict[str, object]:
    root_ids = [item.root_id for item in ROOTS]
    table_names = [item.table for item in ROOTS]
    pk_names = [item.pk for item in ROOTS]
    if len(ROOTS) != 65 or len(set(root_ids)) != 65 or len(set(table_names)) != 65:
        raise RuntimeError("Root manifest must contain 65 unique Root IDs and tables")
    if len(QUERY_IDS) != 20 or len(set(QUERY_IDS)) != 20:
        raise RuntimeError("Query catalog must contain 20 unique IDs")
    if ROOT_TABLE_NAMES != set(table_names):
        raise RuntimeError("SQLAlchemy metadata does not cover every Root primary table")
    if any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in table_names + pk_names):
        raise RuntimeError("Table and PK names must be ASCII lower_snake_case")

    names: list[str] = []
    for table in metadata.tables.values():
        names.append(table.name)
        names.extend(item.name for item in table.constraints if item.name)
        names.extend(item.name for item in table.indexes if item.name)
    if any(len(name.encode("ascii")) > 63 for name in names):
        raise RuntimeError("A Schema identifier exceeds PostgreSQL's 63-byte limit")

    literal_markers = ("k" + "-ws-", "o" + "1_", "Admin" + "123")
    forbidden_value_pattern = re.compile(
        "(?i)(" + "|".join(re.escape(value) for value in literal_markers) +
        r"|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY)"
    )
    source_hits = 0
    for source in root.rglob("*"):
        if source.is_file() and source.suffix.lower() in {".py", ".ini", ".md", ".txt"}:
            source_hits += len(forbidden_value_pattern.findall(source.read_text(encoding="utf-8")))
    if source_hits:
        raise RuntimeError("Secret-like value detected in SC-04 validation sources")

    return {
        "status": "PASS",
        "root_count": len(ROOTS),
        "query_id_count": len(QUERY_IDS),
        "metadata_table_count": len(metadata.tables),
        "identifier_count": len(names),
        "secret_like_value_hits": source_hits,
    }


def database_root_count(connection: psycopg.Connection) -> int:
    return connection.execute(
        "SELECT count(*) FROM pg_tables WHERE schemaname='plm' AND tablename=ANY(%s)",
        (list(ROOT_TABLE_NAMES),),
    ).fetchone()[0]


def empty_migration_validation(root: Path, port: int) -> dict[str, object]:
    recreate_database(port, EMPTY_DB)
    config = alembic_config(root, port, EMPTY_DB)
    alembic.command.upgrade(config, "head")
    with psycopg.connect(admin_url(port, EMPTY_DB)) as connection:
        revision = connection.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]
        root_count = database_root_count(connection)
        extension = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
        index_count = connection.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname='plm' AND "
            "(indexname LIKE 'ix_%' OR indexname LIKE 'uq_%')"
        ).fetchone()[0]
    alembic.command.downgrade(config, "base")
    with psycopg.connect(admin_url(port, EMPTY_DB)) as connection:
        remaining_roots = database_root_count(connection)
    if revision != "0002" or root_count != 65 or remaining_roots != 0 or index_count < 22:
        raise RuntimeError("Empty database up/down or index manifest validation failed")
    return {
        "status": "PASS",
        "head_revision": revision,
        "root_table_count": root_count,
        "representative_index_count": index_count,
        "pgvector_version": extension,
        "downgrade_root_table_count": remaining_roots,
    }


def expect_rejected(port: int, sql: str, params: tuple[object, ...], label: str) -> str:
    try:
        with psycopg.connect(admin_url(port, DATA_DB)) as connection:
            connection.execute(sql, params)
            connection.commit()
    except psycopg.Error as error:
        return error.sqlstate or type(error).__name__
    raise RuntimeError(f"Negative database case was accepted: {label}")


def vector_literal(value: float, dimension: int = 32) -> str:
    return "[" + ",".join(f"{value:.6f}" for _ in range(dimension)) + "]"


def seed_core_data(port: int) -> dict[str, uuid.UUID]:
    ids = {name: uuid.uuid4() for name in (
        "p1", "p2", "user", "member", "document", "version", "review", "round",
        "index", "chunk", "audit", "file_free", "file_held", "hold", "plan", "wbs1", "wbs2",
        "job", "lease",
    )}
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        connection.execute(
            "INSERT INTO plm.prj_projects(project_id,project_code_normalized,name,state) "
            "VALUES (%s,'p-001','Project One','ACTIVE'),(%s,'p-002','Project Two','ACTIVE')",
            (ids["p1"], ids["p2"]),
        )
        connection.execute(
            "INSERT INTO plm.auth_users(user_id,username_normalized,display_name,state) "
            "VALUES (%s,'schema-validator','Schema Validator','ACTIVE')",
            (ids["user"],),
        )
        connection.execute(
            "INSERT INTO plm.prj_project_members(project_member_id,project_id,user_id,project_role,membership_state) "
            "VALUES (%s,%s,%s,'PROJECT_MANAGER','ACTIVE')",
            (ids["member"], ids["p1"], ids["user"]),
        )
        connection.execute(
            "INSERT INTO plm.doc_documents(document_id,scope,project_id,title,state) "
            "VALUES (%s,'PROJECT',%s,'Migration retained document','ACTIVE')",
            (ids["document"], ids["p1"]),
        )
        connection.execute(
            "INSERT INTO plm.doc_document_versions"
            "(document_version_id,document_id,scope,project_id,version_no,version_state,content_fingerprint) "
            "VALUES (%s,%s,'PROJECT',%s,1,'DRAFT',%s)",
            (ids["version"], ids["document"], ids["p1"], bytes(32)),
        )
        connection.execute(
            "INSERT INTO plm.rvw_reviews"
            "(review_id,scope,project_id,subject_owner_module,subject_object_type,subject_object_id,state) "
            "VALUES (%s,'PROJECT',%s,'document','Document',%s,'IN_REVIEW')",
            (ids["review"], ids["p1"], ids["document"]),
        )
        connection.execute(
            "INSERT INTO plm.rvw_review_rounds"
            "(review_round_id,review_id,scope,project_id,subject_version_id,round_no,round_state) "
            "VALUES (%s,%s,'PROJECT',%s,%s,1,'IN_REVIEW')",
            (ids["round"], ids["review"], ids["p1"], ids["version"]),
        )
        connection.execute(
            "INSERT INTO plm.rag_embedding_indexes"
            "(embedding_index_id,scope,project_id,index_purpose,index_version,embedding_dimension,state) "
            "VALUES (%s,'PROJECT',%s,'DOCUMENT_RETRIEVAL',1,32,'ACTIVE')",
            (ids["index"], ids["p1"]),
        )
        connection.execute(
            "INSERT INTO plm.rag_document_chunks"
            "(chunk_id,scope,project_id,document_version_id,state,search_body) "
            "VALUES (%s,'PROJECT',%s,%s,'AVAILABLE','合同 项目 实施 方案')",
            (ids["chunk"], ids["p1"], ids["version"]),
        )
        connection.execute(
            "INSERT INTO plm.rag_embedding_records"
            "(scope,project_id,embedding_index_id,chunk_id,embedding_dimension,embedding,state) "
            "VALUES ('PROJECT',%s,%s,%s,32,%s::vector,'AVAILABLE')",
            (ids["p1"], ids["index"], ids["chunk"], vector_literal(0.1)),
        )
        connection.execute(
            "INSERT INTO plm.aud_events"
            "(audit_event_id,target_project_id,actor_id,target_owner_module,target_object_type,target_object_id,action) "
            "VALUES (%s,%s,%s,'document','Document',%s,'CREATED')",
            (ids["audit"], ids["p1"], ids["user"], ids["document"]),
        )
        connection.execute(
            "INSERT INTO plm.job_jobs"
            "(job_id,scope,project_id,owner_module,job_type,idempotency_key,state,priority,available_at) "
            "VALUES (%s,'PROJECT',%s,'document','PARSE','negative-job','RUNNING',0,statement_timestamp())",
            (ids["job"], ids["p1"]),
        )
        connection.execute(
            "INSERT INTO plm.job_leases"
            "(job_lease_id,job_id,worker_id,state,fencing_token,lease_expires_at,heartbeat_at) "
            "VALUES (%s,%s,'worker-1','ACTIVE',1,statement_timestamp()+interval '1 minute',statement_timestamp())",
            (ids["lease"], ids["job"]),
        )
        for key, locator in (("file_free", "staged/free.bin"), ("file_held", "staged/held.bin")):
            connection.execute(
                "INSERT INTO plm.doc_file_objects"
                "(file_object_id,scope,project_id,storage_locator,sha256,size_bytes,state,retention_due_at) "
                "VALUES (%s,'PROJECT',%s,%s,%s,64,'STAGED',statement_timestamp()-interval '2 days')",
                (ids[key], ids["p1"], locator, bytes(32)),
            )
        connection.execute(
            "INSERT INTO plm.plt_retention_holds"
            "(retention_hold_id,scope,project_id,object_owner,object_type,object_id,state,reason) "
            "VALUES (%s,'PROJECT',%s,'document','FileObject',%s,'ACTIVE','validation hold')",
            (ids["hold"], ids["p1"], ids["file_held"]),
        )
        connection.execute(
            "INSERT INTO plm.pln_wbs_items"
            "(wbs_item_id,project_id,plan_version_id,parent_item_id,ordinal,wbs_code_normalized,level,state) "
            "VALUES (%s,%s,%s,NULL,1,'1',1,'NOT_STARTED'),"
            "(%s,%s,%s,%s,1,'1.1',2,'NOT_STARTED')",
            (ids["wbs1"], ids["p1"], ids["plan"], ids["wbs2"], ids["p1"], ids["plan"], ids["wbs1"]),
        )
        connection.commit()
    return ids


def negative_constraint_validation(port: int, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    cases = {
        "scope_project_pair": expect_rejected(
            port,
            "INSERT INTO plm.doc_documents(document_id,scope,project_id,title,state) "
            "VALUES (uuidv7(),'PROJECT',NULL,'invalid','ACTIVE')",
            (),
            "PROJECT without project_id",
        ),
        "cross_project_version": expect_rejected(
            port,
            "INSERT INTO plm.doc_document_versions"
            "(document_id,scope,project_id,version_no,version_state,content_fingerprint) "
            "VALUES (%s,'PROJECT',%s,2,'DRAFT',%s)",
            (ids["document"], ids["p2"], bytes(32)),
            "cross-project document version",
        ),
        "review_single_active_round": expect_rejected(
            port,
            "INSERT INTO plm.rvw_review_rounds"
            "(review_id,scope,project_id,subject_version_id,round_no,round_state) "
            "VALUES (%s,'PROJECT',%s,%s,2,'IN_REVIEW')",
            (ids["review"], ids["p1"], ids["version"]),
            "second IN_REVIEW round",
        ),
        "embedding_dimension": expect_rejected(
            port,
            "INSERT INTO plm.rag_embedding_records"
            "(scope,project_id,embedding_index_id,chunk_id,embedding_dimension,embedding,state) "
            "VALUES ('PROJECT',%s,%s,%s,32,'[0.1,0.2]'::vector,'FAILED')",
            (ids["p1"], ids["index"], ids["chunk"]),
            "vector dimension mismatch",
        ),
        "append_only_audit": expect_rejected(
            port,
            "UPDATE plm.aud_events SET action='CHANGED' WHERE audit_event_id=%s",
            (ids["audit"],),
            "audit update",
        ),
        "wbs_cross_project": expect_rejected(
            port,
            "INSERT INTO plm.pln_wbs_dependencies"
            "(project_id,plan_version_id,predecessor_item_id,successor_item_id,dependency_type) "
            "VALUES (%s,%s,%s,%s,'FS')",
            (ids["p2"], ids["plan"], ids["wbs1"], ids["wbs2"]),
            "cross-project WBS dependency",
        ),
        "username_unique": expect_rejected(
            port,
            "INSERT INTO plm.auth_users(username_normalized,display_name,state) "
            "VALUES ('schema-validator','Duplicate','ACTIVE')",
            (),
            "duplicate username",
        ),
        "job_idempotency": expect_rejected(
            port,
            "INSERT INTO plm.job_jobs"
            "(scope,project_id,owner_module,job_type,idempotency_key,state,priority,available_at) "
            "VALUES ('PROJECT',%s,'document','PARSE','negative-job','QUEUED',0,statement_timestamp())",
            (ids["p1"],),
            "duplicate job idempotency key",
        ),
        "single_active_lease": expect_rejected(
            port,
            "INSERT INTO plm.job_leases"
            "(job_id,worker_id,state,fencing_token,lease_expires_at,heartbeat_at) "
            "VALUES (%s,'worker-2','ACTIVE',2,statement_timestamp()+interval '1 minute',statement_timestamp())",
            (ids["job"],),
            "second active lease",
        ),
        "embedding_available_unique": expect_rejected(
            port,
            "INSERT INTO plm.rag_embedding_records"
            "(scope,project_id,embedding_index_id,chunk_id,embedding_dimension,embedding,state) "
            "VALUES ('PROJECT',%s,%s,%s,32,%s::vector,'AVAILABLE')",
            (ids["p1"], ids["index"], ids["chunk"], vector_literal(0.2)),
            "second AVAILABLE embedding",
        ),
    }
    return {"status": "PASS", "rejected_case_count": len(cases), "sqlstates": cases}


def index_names_from_plan(plan: object) -> set[str]:
    found: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            index_name = value.get("Index Name")
            if isinstance(index_name, str):
                found.add(index_name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(plan)
    return found


def explain_indexes(connection: psycopg.Connection, sql: str, params: tuple[object, ...]) -> set[str]:
    connection.execute("SET LOCAL enable_seqscan=off")
    plan = connection.execute(f"EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) {sql}", params).fetchone()[0]
    return index_names_from_plan(plan)


def query_plan_validation(port: int, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        connection.execute(
            "INSERT INTO plm.job_jobs"
            "(scope,project_id,owner_module,job_type,idempotency_key,state,priority,available_at) "
            "SELECT 'PROJECT',%s,'document','PARSE','hist-'||g,'SUCCEEDED',0,statement_timestamp() "
            "FROM generate_series(1,10000) g",
            (ids["p1"],),
        )
        connection.execute(
            "INSERT INTO plm.job_jobs"
            "(scope,project_id,owner_module,job_type,idempotency_key,state,priority,available_at) "
            "SELECT 'PROJECT',%s,'document','PARSE','queue-'||g,'QUEUED',g%%5,statement_timestamp()-interval '1 minute' "
            "FROM generate_series(1,100) g",
            (ids["p1"],),
        )
        connection.execute(
            "INSERT INTO plm.aud_events"
            "(target_project_id,actor_id,target_owner_module,target_object_type,target_object_id,action,occurred_at) "
            "SELECT %s,%s,'document','Document',%s,'READ',statement_timestamp()-(g||' seconds')::interval "
            "FROM generate_series(1,10000) g",
            (ids["p1"], ids["user"], ids["document"]),
        )
        connection.execute(
            "INSERT INTO plm.rag_document_chunks"
            "(scope,project_id,document_version_id,state,search_body) "
            "SELECT 'PROJECT',%s,%s,'AVAILABLE',CASE WHEN g%%10=0 THEN '合同 项目 实施 方案' ELSE '普通 文档 内容' END "
            "FROM generate_series(1,5000) g",
            (ids["p1"], ids["version"]),
        )
        chunk_ids = [
            row[0]
            for row in connection.execute(
                "SELECT chunk_id FROM plm.rag_document_chunks "
                "WHERE project_id=%s AND chunk_id<>%s ORDER BY chunk_id LIMIT 1000",
                (ids["p1"], ids["chunk"]),
            ).fetchall()
        ]
        vector_rows: list[tuple[object, ...]] = []
        for offset, chunk_id in enumerate(chunk_ids, start=1):
            values = [
                math.sin(offset * (dimension + 1)) + math.cos((offset + 3) * (dimension + 7))
                for dimension in range(32)
            ]
            norm = math.sqrt(sum(value * value for value in values))
            vector = "[" + ",".join(f"{value / norm:.8f}" for value in values) + "]"
            vector_rows.append((ids["p1"], ids["index"], chunk_id, vector))
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO plm.rag_embedding_records"
                "(scope,project_id,embedding_index_id,chunk_id,embedding_dimension,embedding,state) "
                "VALUES ('PROJECT',%s,%s,%s,32,%s::vector,'AVAILABLE')",
                vector_rows,
            )
        connection.execute("ANALYZE plm.job_jobs")
        connection.execute("ANALYZE plm.aud_events")
        connection.execute("ANALYZE plm.rag_document_chunks")
        connection.execute("ANALYZE plm.rag_embedding_records")

        observed: dict[str, list[str]] = {}
        observed["Q-JOB-01"] = sorted(explain_indexes(
            connection,
            "SELECT job_id FROM plm.job_jobs "
            "WHERE state IN ('QUEUED','RETRY_WAIT') AND available_at<=statement_timestamp() "
            "ORDER BY priority DESC,available_at,job_id LIMIT 10",
            (),
        ))
        observed["Q-AUD-01"] = sorted(explain_indexes(
            connection,
            "SELECT audit_event_id FROM plm.aud_events WHERE target_project_id=%s "
            "ORDER BY occurred_at DESC,audit_event_id DESC LIMIT 20",
            (ids["p1"],),
        ))
        observed["Q-RAG-01-FTS"] = sorted(explain_indexes(
            connection,
            "SELECT chunk_id FROM plm.rag_document_chunks "
            "WHERE scope='PROJECT' AND project_id=%s "
            "AND search_vector @@ to_tsquery('simple','合同 & 项目') LIMIT 20",
            (ids["p1"],),
        ))
        query_vector = vector_rows[0][3]
        connection.execute("SET LOCAL hnsw.ef_search=200")
        connection.execute("SET LOCAL hnsw.iterative_scan='strict_order'")
        observed["Q-RAG-01-HNSW"] = sorted(explain_indexes(
            connection,
            "SELECT embedding_record_id FROM plm.rag_embedding_records "
            "WHERE scope='PROJECT' AND project_id=%s AND embedding_index_id=%s "
            "AND state='AVAILABLE' AND embedding_dimension=32 "
            "ORDER BY embedding::vector(32) <=> %s::vector(32) LIMIT 5",
            (ids["p1"], ids["index"], query_vector),
        ))
        connection.execute("SET LOCAL enable_sort=off")
        observed["HNSW-PHYSICAL-PROBE"] = sorted(explain_indexes(
            connection,
            "SELECT embedding_record_id FROM plm.rag_embedding_records "
            "WHERE state='AVAILABLE' AND embedding_dimension=32 "
            "ORDER BY embedding::vector(32) <=> %s::vector(32) LIMIT 5",
            (query_vector,),
        ))
        connection.execute("SET LOCAL enable_sort=on")
        expected = {
            "Q-JOB-01": "ix_job_jobs__claim",
            "Q-AUD-01": "ix_aud_events__project_time",
            "Q-RAG-01-FTS": "ix_rag_chunks__search_gin",
            "HNSW-PHYSICAL-PROBE": "ix_rag_embed__v32_hnsw",
        }
        for query_id, index_name in expected.items():
            if index_name not in observed[query_id]:
                raise RuntimeError(f"{query_id} did not use {index_name}: {observed[query_id]}")
        authorized_vector_indexes = set(observed["Q-RAG-01-HNSW"])
        allowed_vector_routes = {
            "ix_rag_embed__v32_hnsw",
            "uq_rag_embeddings__index_chunk_available",
        }
        if not (authorized_vector_indexes & allowed_vector_routes):
            raise RuntimeError(
                "Authorized vector query used neither HNSW nor bounded exact-filter index: "
                f"{sorted(authorized_vector_indexes)}"
            )
        authorized_vector_route = (
            "HNSW" if "ix_rag_embed__v32_hnsw" in authorized_vector_indexes
            else "EXACT_FILTERED_FALLBACK"
        )
        connection.execute("SET LOCAL enable_indexscan=off")
        exact = {
            row[0]
            for row in connection.execute(
                "SELECT embedding_record_id FROM plm.rag_embedding_records "
                "WHERE state='AVAILABLE' AND embedding_dimension=32 "
                "ORDER BY embedding::vector(32) <=> %s::vector(32) LIMIT 5",
                (query_vector,),
            ).fetchall()
        }
        connection.execute("SET LOCAL enable_indexscan=on")
        connection.execute("SET LOCAL enable_sort=off")
        approximate = {
            row[0]
            for row in connection.execute(
                "SELECT embedding_record_id FROM plm.rag_embedding_records "
                "WHERE state='AVAILABLE' AND embedding_dimension=32 "
                "ORDER BY embedding::vector(32) <=> %s::vector(32) LIMIT 5",
                (query_vector,),
            ).fetchall()
        }
        connection.execute("SET LOCAL enable_sort=on")
        recall = len(exact & approximate) / 5
        if recall < 0.95:
            raise RuntimeError(f"Representative HNSW Top-5 recall is below 0.95: {recall}")
        connection.commit()
    return {
        "status": "PASS",
        "observed_indexes": observed,
        "authorized_vector_route": authorized_vector_route,
        "representative_hnsw_vector_count": len(vector_rows) + 1,
        "representative_hnsw_top5_recall": recall,
        "performance_claim": "NOT_MADE",
    }


def claim_one(port: int, worker_no: int) -> str | None:
    del worker_no
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        row = connection.execute(
            """
            WITH picked AS (
              SELECT job_id FROM plm.job_jobs
              WHERE state IN ('QUEUED','RETRY_WAIT')
                AND available_at<=statement_timestamp()
              ORDER BY priority DESC,available_at,job_id
              FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE plm.job_jobs j
            SET state='RUNNING',lock_version=lock_version+1,
                fencing_token=fencing_token+1,updated_at=statement_timestamp()
            FROM picked WHERE j.job_id=picked.job_id
            RETURNING j.job_id
            """
        ).fetchone()
        connection.commit()
        return str(row[0]) if row else None


def concurrency_validation(port: int) -> dict[str, object]:
    with ThreadPoolExecutor(max_workers=20) as executor:
        claimed = list(executor.map(lambda n: claim_one(port, n), range(20)))
    non_null = [item for item in claimed if item]
    if len(non_null) != 20 or len(set(non_null)) != 20:
        raise RuntimeError("20-worker SKIP LOCKED claim was not unique")
    return {"status": "PASS", "worker_count": 20, "unique_claim_count": len(set(non_null))}


def retention_validation(port: int, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        rows = connection.execute(
            """
            SELECT f.file_object_id FROM plm.doc_file_objects f
            WHERE f.retention_due_at<=statement_timestamp()
              AND f.state IN ('STAGED','FAILED','CLEANUP_PENDING')
              AND NOT EXISTS (
                SELECT 1 FROM plm.plt_retention_holds h
                WHERE h.state='ACTIVE' AND h.object_owner='document'
                  AND h.object_type='FileObject' AND h.object_id=f.file_object_id
                  AND h.scope=f.scope AND h.project_id IS NOT DISTINCT FROM f.project_id
              )
            ORDER BY f.file_object_id
            """
        ).fetchall()
    candidates = {row[0] for row in rows}
    if candidates != {ids["file_free"]}:
        raise RuntimeError(f"Retention/Hold candidate mismatch: {candidates}")
    return {"status": "PASS", "cleanup_candidate_count": 1, "active_hold_blocked_count": 1}


def sensitive_schema_validation(port: int) -> dict[str, object]:
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        rows = connection.execute(
            "SELECT lower(column_name) FROM information_schema.columns WHERE table_schema='plm'"
        ).fetchall()
    present = sorted(FORBIDDEN_COLUMNS & {row[0] for row in rows})
    if present:
        raise RuntimeError(f"Forbidden sensitive columns found: {present}")
    return {"status": "PASS", "forbidden_column_hits": 0}


def backup_restore_validation(port: int, pg_bin: Path, ids: dict[str, uuid.UUID]) -> dict[str, object]:
    recreate_database(port, RESTORE_DB)
    with tempfile.TemporaryDirectory(prefix="plm-sc04-") as temporary:
        dump_path = Path(temporary) / "sc04.dump"
        subprocess.run(
            [str(pg_bin / "pg_dump.exe"), "-h", "127.0.0.1", "-p", str(port), "-U", "poc_admin", "-Fc", "-f", str(dump_path), DATA_DB],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [str(pg_bin / "pg_restore.exe"), "-h", "127.0.0.1", "-p", str(port), "-U", "poc_admin", "-d", RESTORE_DB, str(dump_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        dump_size = dump_path.stat().st_size
    with psycopg.connect(admin_url(port, RESTORE_DB)) as connection:
        restored = connection.execute(
            "SELECT count(*) FROM plm.doc_documents WHERE document_id=%s",
            (ids["document"],),
        ).fetchone()[0]
        root_count = database_root_count(connection)
    if restored != 1 or root_count != 65 or dump_size <= 0:
        raise RuntimeError("Backup/restore verification failed")
    return {"status": "PASS", "restored_root_table_count": root_count, "restored_document_count": restored, "dump_bytes": dump_size}


def data_migration_validation(root: Path, port: int, pg_bin: Path) -> dict[str, object]:
    recreate_database(port, DATA_DB)
    config = alembic_config(root, port, DATA_DB)
    alembic.command.upgrade(config, "0001")
    ids = seed_core_data(port)
    alembic.command.upgrade(config, "head")
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        retained = connection.execute(
            "SELECT title FROM plm.doc_documents WHERE document_id=%s",
            (ids["document"],),
        ).fetchone()[0]
    result = {
        "status": "PASS",
        "retained_after_upgrade": retained == "Migration retained document",
        "negative_constraints": negative_constraint_validation(port, ids),
        "query_plans": query_plan_validation(port, ids),
        "concurrency": concurrency_validation(port),
        "retention_and_file_recovery": retention_validation(port, ids),
        "sensitive_schema": sensitive_schema_validation(port),
        "backup_restore": backup_restore_validation(port, pg_bin, ids),
    }
    alembic.command.downgrade(config, "0001")
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        retained_after_down = connection.execute(
            "SELECT title FROM plm.doc_documents WHERE document_id=%s",
            (ids["document"],),
        ).fetchone()[0]
        secondary_index = connection.execute(
            "SELECT to_regclass('plm.ix_job_jobs__claim')"
        ).fetchone()[0]
    alembic.command.downgrade(config, "base")
    with psycopg.connect(admin_url(port, DATA_DB)) as connection:
        roots_after_base = database_root_count(connection)
    if retained_after_down != "Migration retained document" or secondary_index is not None or roots_after_base != 0:
        raise RuntimeError("Data downgrade verification failed")
    result["retained_after_downgrade"] = True
    result["secondary_indexes_removed_on_down"] = True
    result["root_tables_after_base"] = roots_after_base
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=55434)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keep-databases", action="store_true")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result: dict[str, object] = {
        "schema_version": SCHEMA_CONTRACT_VERSION,
        "validation_only": VALIDATION_ONLY,
        "status": "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_version": os.sys.version.split()[0],
        "external_network_calls": 0,
    }
    try:
        result["manifest"] = manifest_validation(root)
        result["empty_migration"] = empty_migration_validation(root, arguments.port)
        result["data_migration"] = data_migration_validation(root, arguments.port, arguments.pg_bin.resolve())
    except Exception as error:
        result["status"] = "FAIL"
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        arguments.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if not arguments.keep_databases:
            for database in DATABASES:
                try:
                    drop_database(arguments.port, database)
                except Exception:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
