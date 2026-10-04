"""Windows 11/PostgreSQL 18 proof for Schema0087 quality evidence."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ready_fixture = load(
    ROOT / "validation/rag-03-a05-p03-index-ready-owner/verify.py",
    "rag_quality_ready_fixture",
)
worker_fixture = ready_fixture.worker_fixture
send_fixture = ready_fixture.send_fixture
begin_fixture = ready_fixture.begin_fixture


def verify_empty_migration() -> None:
    database = "rag03a05p04p02empty_" + uuid.uuid4().hex[:8]
    with ready_fixture.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            config = create_migration_config(URL.create(
                "postgresql+psycopg", username=ready_fixture.USER,
                host=ready_fixture.HOST, port=ready_fixture.PORT,
                database=database,
            ))
            command.upgrade(config, "head")
            command.check(config)
            with ready_fixture.connect(database) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.rag_embedding_index_quality_results"
                ).fetchone()[0] == 0
                assert db.execute(
                    "SELECT count(*) FROM plm.rag_embedding_index_activation_results"
                ).fetchone()[0] == 0
            command.downgrade(config, "20261004_0086")
            command.upgrade(config, "head")
            command.check(config)
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))


def _quality_insert(db, index_id, *, dataset_ref: str, dataset_hash: bytes,
                    classification: int, citation: int, state: str,
                    error_code: str | None):
    return db.execute("""
        INSERT INTO plm.rag_embedding_index_quality_results(
          embedding_index_id,technical_validation_ref,scope,project_id,
          index_purpose,embedding_model_ref,source_snapshot_fingerprint,
          dataset_ref,dataset_fingerprint,isolation_attestation_fingerprint,
          evaluation_artifact_fingerprint,evaluation_policy_ref,
          dataset_case_count,classification_correct_count,
          exact_citation_correct_count,minimum_classification_basis_points,
          classification_basis_points,minimum_exact_citation_basis_points,
          exact_citation_basis_points,project_isolation_pass,
          out_of_scope_citation_count,failure_closure_pass,quality_state,
          error_code,evaluated_by,dataset_sealed_at)
        SELECT index_row.embedding_index_id,
          validation.embedding_index_validation_id,index_row.scope,
          index_row.project_id,index_row.index_purpose,
          index_row.embedding_model_ref,index_row.source_snapshot_fingerprint,
          %s,%s,sha256('synthetic isolation'::bytea),
          sha256('synthetic artifact'::bytea),'rag-business-quality-v1',
          50,%s,%s,9000,%s*10000/50,9800,%s*10000/50,true,0,true,%s,%s,
          index_row.created_by,statement_timestamp()-interval '1 day'
        FROM plm.rag_embedding_indexes index_row
        JOIN plm.rag_embedding_index_validations validation
          ON validation.embedding_index_id=index_row.embedding_index_id
        WHERE index_row.embedding_index_id=%s
        RETURNING quality_result_id
    """, (dataset_ref, dataset_hash, classification, citation,
            classification, citation, state, error_code,
            index_id)).fetchone()[0]


def execute(context, envelope, sender, adapter) -> None:
    ready_fixture.execute_success(context, envelope, sender, adapter)
    index_id = context["planned"].embedding_index_id
    database = context["database"]
    with begin_fixture.connect(database) as db:
        failed = _quality_insert(
            db, index_id, dataset_ref="quality.synthetic.failed.v1",
            dataset_hash=b"f" * 32, classification=24, citation=37,
            state="FAILED", error_code="RAG_BUSINESS_QUALITY_THRESHOLD_FAILED",
        )
        ready_fixture.reject_db(db, lambda: db.execute(
            "UPDATE plm.rag_embedding_indexes SET index_state='ACTIVE',"
            "lock_version=3 WHERE embedding_index_id=%s", (index_id,),
        ), "ACTIVE proof is invalid")
        passed = _quality_insert(
            db, index_id, dataset_ref="quality.synthetic.contract.v1",
            dataset_hash=b"p" * 32, classification=45, citation=49,
            state="PASSED", error_code=None,
        )
        ready_fixture.reject_db(db, lambda: db.execute(
            "UPDATE plm.rag_embedding_index_quality_results SET "
            "classification_correct_count=50 WHERE quality_result_id=%s",
            (passed,),
        ), "quality history is retained")
        ready_fixture.reject_db(db, lambda: db.execute(
            "UPDATE plm.rag_embedding_indexes SET index_state='ACTIVE',"
            "lock_version=3 WHERE embedding_index_id=%s", (index_id,),
        ), "activation transaction is incomplete")
        with db.transaction():
            identity = db.execute(
                "SELECT scope,project_id,index_purpose,created_by "
                "FROM plm.rag_embedding_indexes WHERE embedding_index_id=%s",
                (index_id,),
            ).fetchone()
            trace = uuid.uuid4()
            event_scope = "DEPLOYMENT" if identity[0] == "GLOBAL" else "PROJECT"
            audit = db.execute(
                "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                "actor_type,actor_id,action,outcome,target_owner_module,"
                "target_object_type,target_object_id,target_version_id,before_state,"
                "after_state) VALUES (%s,%s,%s,'USER',%s,'RAG_INDEX_ACTIVATED',"
                "'SUCCESS','rag','RAG-03',%s,%s,'READY','ACTIVE') "
                "RETURNING audit_event_id,occurred_at",
                (trace, event_scope, identity[1], identity[3], index_id, passed),
            ).fetchone()
            db.execute(
                "UPDATE plm.rag_embedding_indexes SET index_state='ACTIVE',"
                "lock_version=3 WHERE embedding_index_id=%s", (index_id,),
            )
            result = db.execute(
                "INSERT INTO plm.rag_embedding_index_activation_results("
                "embedding_index_id,quality_result_ref,scope,project_id,"
                "index_purpose,activated_by,audit_event_id,trace_id,"
                "expected_lock_version,lock_version,activated_at) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,2,3,%s) "
                "RETURNING activation_result_id",
                (index_id, passed, identity[0], identity[1], identity[2],
                 identity[3], audit[0], trace, audit[1]),
            ).fetchone()[0]
        assert db.execute(
            "SELECT index_state,lock_version FROM plm.rag_embedding_indexes "
            "WHERE embedding_index_id=%s", (index_id,),
        ).fetchone() == ("ACTIVE", 3)
        assert db.execute(
            "SELECT quality_result_ref,retired_index_ref FROM "
            "plm.rag_embedding_index_activation_results "
            "WHERE activation_result_id=%s", (result,),
        ).fetchone() == (passed, None)
        assert db.execute(
            "SELECT count(*) FROM plm.rag_embedding_index_quality_results "
            "WHERE embedding_index_id=%s", (index_id,),
        ).fetchone()[0] == 2
        columns = {row[0] for row in db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='plm' AND "
            "table_name='rag_embedding_index_quality_results'"
        )}
        assert not columns.intersection(
            {"query_body", "golden_answer", "customer_body", "document_body"}
        )
        ready_fixture.reject_db(db, lambda: db.execute(
            "DELETE FROM plm.rag_embedding_index_quality_results "
            "WHERE quality_result_id=%s", (failed,),
        ), "quality history is retained")
    try:
        command.downgrade(context["config"], "20261004_0086")
    except Exception as error:
        assert "quality history prevents downgrade" in str(error), error
    else:
        raise AssertionError("populated quality history accepted downgrade")
    print(
        "RAG_03_A05_P04_P02_QUALITY_SCHEMA_PASS: immutable failed/passed "
        "quality metadata, fixed 90/98 thresholds, direct ACTIVE rejection, "
        "deferred activation result, ACTIVE uniqueness foundation, no bodies"
    )


def main() -> None:
    verify_empty_migration()
    send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
