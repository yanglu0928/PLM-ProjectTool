"""Add immutable business-quality and Index activation evidence.

Revision ID: 20261004_0087
Revises: 20261004_0086
"""

from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "20261004_0087"
down_revision = "20261004_0086"
branch_labels = None
depends_on = None


_INDEX_ACTIVATION = r"""
    IF OLD.index_state='READY' AND NEW.index_state='ACTIVE' THEN
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_index_id,NEW.scope,NEW.project_id,
                  NEW.index_purpose,NEW.embedding_model_ref,
                  NEW.embedding_dimension,NEW.chunk_profile,
                  NEW.chunk_profile_version,NEW.source_chunk_count,
                  NEW.source_snapshot_fingerprint,NEW.index_version,
                  NEW.created_by,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_index_id,OLD.scope,OLD.project_id,
                  OLD.index_purpose,OLD.embedding_model_ref,
                  OLD.embedding_dimension,OLD.chunk_profile,
                  OLD.chunk_profile_version,OLD.source_chunk_count,
                  OLD.source_snapshot_fingerprint,OLD.index_version,
                  OLD.created_by,OLD.created_at,OLD.created_xid)
           OR model_kind IS DISTINCT FROM 'EMBEDDING'
           OR model_dimension IS DISTINCT FROM NEW.embedding_dimension
           OR model_state IS DISTINCT FROM 'AVAILABLE'
           OR build_row.build_state<>'SUCCEEDED'
           OR NOT EXISTS (
                SELECT 1 FROM plm.rag_embedding_index_validations validation
                 WHERE validation.embedding_index_id=NEW.embedding_index_id
                   AND validation.embedding_build_id=build_row.embedding_build_id
                   AND validation.validation_state='PASSED')
           OR NOT EXISTS (
                SELECT 1 FROM plm.rag_embedding_index_quality_results quality
                 WHERE quality.embedding_index_id=NEW.embedding_index_id
                   AND quality.quality_state='PASSED') THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex ACTIVE proof is invalid';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.index_state='ACTIVE' AND NEW.index_state='RETIRED' THEN
        IF NEW.lock_version<>OLD.lock_version+1
           OR ROW(NEW.embedding_index_id,NEW.scope,NEW.project_id,
                  NEW.index_purpose,NEW.embedding_model_ref,
                  NEW.embedding_dimension,NEW.chunk_profile,
                  NEW.chunk_profile_version,NEW.source_chunk_count,
                  NEW.source_snapshot_fingerprint,NEW.index_version,
                  NEW.created_by,NEW.created_at,NEW.created_xid)
              IS DISTINCT FROM
              ROW(OLD.embedding_index_id,OLD.scope,OLD.project_id,
                  OLD.index_purpose,OLD.embedding_model_ref,
                  OLD.embedding_dimension,OLD.chunk_profile,
                  OLD.chunk_profile_version,OLD.source_chunk_count,
                  OLD.source_snapshot_fingerprint,OLD.index_version,
                  OLD.created_by,OLD.created_at,OLD.created_xid) THEN
            RAISE EXCEPTION 'RAG EmbeddingIndex retirement is invalid';
        END IF;
        RETURN NEW;
    END IF;

"""


_EVIDENCE_GUARDS = r"""
CREATE FUNCTION plm.guard_rag_embedding_index_quality_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    validation_row plm.rag_embedding_index_validations%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Index quality history is retained';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO validation_row FROM plm.rag_embedding_index_validations
     WHERE embedding_index_validation_id=NEW.technical_validation_ref
     FOR KEY SHARE;
    IF index_row.embedding_index_id IS NULL
       OR index_row.index_state<>'READY'
       OR validation_row.embedding_index_validation_id IS NULL
       OR validation_row.embedding_index_id<>index_row.embedding_index_id
       OR validation_row.validation_state<>'PASSED'
       OR ROW(NEW.scope,NEW.project_id,NEW.index_purpose,
              NEW.embedding_model_ref,NEW.source_snapshot_fingerprint)
          IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id,index_row.index_purpose,
              index_row.embedding_model_ref,index_row.source_snapshot_fingerprint)
       OR NEW.created_xid<>txid_current()
       OR NEW.dataset_sealed_at>=NEW.completed_at THEN
        RAISE EXCEPTION 'RAG Index quality evidence binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_index_quality_result_guard
BEFORE INSERT OR UPDATE OR DELETE
ON plm.rag_embedding_index_quality_results
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_index_quality_result();

CREATE FUNCTION plm.guard_rag_embedding_index_activation_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    index_row plm.rag_embedding_indexes%ROWTYPE;
    retired_row plm.rag_embedding_indexes%ROWTYPE;
    quality_row plm.rag_embedding_index_quality_results%ROWTYPE;
    audit_row plm.aud_events%ROWTYPE;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'RAG Index activation history is retained';
    END IF;
    SELECT * INTO index_row FROM plm.rag_embedding_indexes
     WHERE embedding_index_id=NEW.embedding_index_id FOR KEY SHARE;
    SELECT * INTO quality_row FROM plm.rag_embedding_index_quality_results
     WHERE quality_result_id=NEW.quality_result_ref FOR KEY SHARE;
    SELECT * INTO audit_row FROM plm.aud_events
     WHERE audit_event_id=NEW.audit_event_id FOR KEY SHARE;
    IF NEW.retired_index_ref IS NOT NULL THEN
        SELECT * INTO retired_row FROM plm.rag_embedding_indexes
         WHERE embedding_index_id=NEW.retired_index_ref FOR KEY SHARE;
    END IF;
    IF index_row.embedding_index_id IS NULL
       OR index_row.index_state<>'ACTIVE'
       OR index_row.lock_version<>NEW.lock_version
       OR NEW.lock_version<>NEW.expected_lock_version+1
       OR NEW.expected_lock_version<>2
       OR quality_row.quality_result_id IS NULL
       OR quality_row.embedding_index_id<>index_row.embedding_index_id
       OR quality_row.quality_state<>'PASSED'
       OR ROW(NEW.scope,NEW.project_id,NEW.index_purpose)
          IS DISTINCT FROM
          ROW(index_row.scope,index_row.project_id,index_row.index_purpose)
       OR (NEW.retired_index_ref IS NULL AND
           (NEW.retired_before_lock_version IS NOT NULL OR
            NEW.retired_after_lock_version IS NOT NULL))
       OR (NEW.retired_index_ref IS NOT NULL AND
           (retired_row.embedding_index_id IS NULL
            OR retired_row.index_state<>'RETIRED'
            OR retired_row.lock_version<>NEW.retired_after_lock_version
            OR NEW.retired_after_lock_version<>
               NEW.retired_before_lock_version+1
            OR ROW(retired_row.scope,retired_row.project_id,
                   retired_row.index_purpose) IS DISTINCT FROM
               ROW(NEW.scope,NEW.project_id,NEW.index_purpose)))
       OR audit_row.audit_event_id IS NULL
       OR audit_row.trace_id<>NEW.trace_id
       OR audit_row.actor_type<>'USER'
       OR audit_row.actor_id<>NEW.activated_by
       OR audit_row.action<>'RAG_INDEX_ACTIVATED'
       OR audit_row.outcome<>'SUCCESS'
       OR audit_row.target_owner_module<>'rag'
       OR audit_row.target_object_type<>'RAG-03'
       OR audit_row.target_object_id<>NEW.embedding_index_id
       OR audit_row.target_version_id<>NEW.quality_result_ref
       OR audit_row.before_state<>'READY'
       OR audit_row.after_state<>'ACTIVE'
       OR audit_row.event_scope<>(
          CASE WHEN NEW.scope='GLOBAL' THEN 'DEPLOYMENT' ELSE 'PROJECT' END)
       OR audit_row.target_project_id IS DISTINCT FROM NEW.project_id
       OR NEW.created_xid<>txid_current()
       OR NEW.activated_at IS DISTINCT FROM audit_row.occurred_at THEN
        RAISE EXCEPTION 'RAG Index activation result binding is invalid';
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_rag_embedding_index_activation_result_guard
BEFORE INSERT OR UPDATE OR DELETE
ON plm.rag_embedding_index_activation_results
FOR EACH ROW EXECUTE FUNCTION plm.guard_rag_embedding_index_activation_result();

CREATE FUNCTION plm.guard_rag_embedding_index_quality_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RAG Index quality and activation history cannot be truncated';
END; $$;

CREATE TRIGGER trg_rag_embedding_index_quality_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_index_quality_results
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_index_quality_truncate();

CREATE TRIGGER trg_rag_embedding_index_activation_no_truncate
BEFORE TRUNCATE ON plm.rag_embedding_index_activation_results
FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_rag_embedding_index_quality_truncate();
"""


_ACTIVATION_VALIDATOR = r"""
CREATE FUNCTION plm.validate_rag_embedding_index_activation_transaction()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    result_row plm.rag_embedding_index_activation_results%ROWTYPE;
    quality_row plm.rag_embedding_index_quality_results%ROWTYPE;
    model_state text;
BEGIN
    IF OLD.index_state='READY' AND NEW.index_state='ACTIVE' THEN
        SELECT * INTO result_row
          FROM plm.rag_embedding_index_activation_results
         WHERE embedding_index_id=NEW.embedding_index_id;
        SELECT * INTO quality_row
          FROM plm.rag_embedding_index_quality_results
         WHERE quality_result_id=result_row.quality_result_ref;
        SELECT model.model_state INTO model_state FROM plm.ai_models model
         WHERE model.ai_model_id=NEW.embedding_model_ref;
        IF result_row.activation_result_id IS NULL
           OR result_row.lock_version<>NEW.lock_version
           OR quality_row.quality_result_id IS NULL
           OR quality_row.quality_state<>'PASSED'
           OR quality_row.classification_basis_points<9000
           OR quality_row.exact_citation_basis_points<9800
           OR NOT quality_row.project_isolation_pass
           OR quality_row.out_of_scope_citation_count<>0
           OR NOT quality_row.failure_closure_pass
           OR EXISTS (
                SELECT 1 FROM plm.rag_embedding_index_quality_results newer
                 WHERE newer.embedding_index_id=NEW.embedding_index_id
                   AND (newer.completed_at,newer.quality_result_id)>
                       (quality_row.completed_at,quality_row.quality_result_id))
           OR model_state IS DISTINCT FROM 'AVAILABLE'
           OR EXISTS (
                SELECT 1 FROM plm.rag_index_source_chunks source
                JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
                 WHERE source.embedding_index_id=NEW.embedding_index_id
                   AND (chunk.chunk_state<>'ACTIVE'
                     OR chunk.text_fingerprint<>source.chunk_text_fingerprint
                     OR ROW(chunk.scope,chunk.project_id) IS DISTINCT FROM
                        ROW(NEW.scope,NEW.project_id)))
           OR EXISTS (
                SELECT 1 FROM plm.rag_embedding_builds build
                JOIN plm.rag_embedding_build_batches batch
                  ON batch.embedding_build_id=build.embedding_build_id
                JOIN plm.ai_egress_authorizations authz
                  ON authz.authorization_id=batch.egress_authorization_ref
                 WHERE build.embedding_index_id=NEW.embedding_index_id
                   AND (authz.authorization_state<>'AUTHORIZED'
                     OR authz.valid_until<=result_row.activated_at
                     OR authz.ai_model_id<>NEW.embedding_model_ref
                     OR ROW(authz.scope,authz.project_id) IS DISTINCT FROM
                        ROW(NEW.scope,NEW.project_id)))
           OR (SELECT count(*) FROM plm.rag_embedding_indexes active
                WHERE active.scope=NEW.scope
                  AND active.project_id IS NOT DISTINCT FROM NEW.project_id
                  AND active.index_purpose=NEW.index_purpose
                  AND active.index_state='ACTIVE')<>1 THEN
            RAISE EXCEPTION 'RAG Index activation transaction is incomplete';
        END IF;
        RETURN NULL;
    END IF;
    IF OLD.index_state='ACTIVE' AND NEW.index_state='RETIRED' THEN
        SELECT * INTO result_row
          FROM plm.rag_embedding_index_activation_results
         WHERE retired_index_ref=NEW.embedding_index_id;
        IF result_row.activation_result_id IS NULL
           OR result_row.retired_before_lock_version<>OLD.lock_version
           OR result_row.retired_after_lock_version<>NEW.lock_version THEN
            RAISE EXCEPTION 'RAG Index retirement transaction is incomplete';
        END IF;
    END IF;
    RETURN NULL;
END; $$;

CREATE CONSTRAINT TRIGGER trg_rag_embedding_index_activation_complete
AFTER UPDATE ON plm.rag_embedding_indexes
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION
plm.validate_rag_embedding_index_activation_transaction();
"""


def _index_guard() -> str:
    previous = importlib.import_module(
        "plm_assistant.migrations.versions."
        "20261004_0086_rag_embedding_index_ready"
    )
    source = previous._index_guard()
    marker = "    IF OLD.index_state<>'PLANNED' OR NEW.index_state<>'BUILDING'"
    if source.count(marker) != 1:
        raise RuntimeError("Schema0086 Index guard shape changed")
    return source.replace(marker, _INDEX_ACTIVATION + marker)


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "rag_embedding_index_quality_results",
        sa.Column("quality_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("technical_validation_ref", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("index_purpose", sa.Text(), nullable=False),
        sa.Column("embedding_model_ref", ident, nullable=False),
        sa.Column("source_snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("dataset_ref", sa.Text(), nullable=False),
        sa.Column("dataset_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("isolation_attestation_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("evaluation_artifact_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("evaluation_policy_ref", sa.Text(), nullable=False),
        sa.Column("dataset_case_count", sa.Integer(), nullable=False),
        sa.Column("classification_correct_count", sa.Integer(), nullable=False),
        sa.Column("exact_citation_correct_count", sa.Integer(), nullable=False),
        sa.Column("minimum_classification_basis_points", sa.Integer(), nullable=False,
                  server_default=sa.text("9000")),
        sa.Column("classification_basis_points", sa.Integer(), nullable=False),
        sa.Column("minimum_exact_citation_basis_points", sa.Integer(), nullable=False,
                  server_default=sa.text("9800")),
        sa.Column("exact_citation_basis_points", sa.Integer(), nullable=False),
        sa.Column("project_isolation_pass", sa.Boolean(), nullable=False),
        sa.Column("out_of_scope_citation_count", sa.Integer(), nullable=False),
        sa.Column("failure_closure_pass", sa.Boolean(), nullable=False),
        sa.Column("quality_state", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("evaluated_by", ident, nullable=False),
        sa.Column("dataset_sealed_at", timestamp, nullable=False),
        sa.Column("completed_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["embedding_index_id"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_quality__index", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["technical_validation_ref"],
            ["plm.rag_embedding_index_validations.embedding_index_validation_id"],
            name="fk_rag_index_quality__technical_validation", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_quality__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["embedding_model_ref"], ["plm.ai_models.ai_model_id"],
            name="fk_rag_index_quality__model", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["evaluated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_quality__evaluator", ondelete="NO ACTION"),
        sa.UniqueConstraint(
            "embedding_index_id", "dataset_fingerprint", "evaluation_policy_ref",
            name="uq_rag_index_quality__index_dataset_policy"),
        sa.UniqueConstraint("dataset_fingerprint",
                            name="uq_rag_index_quality__dataset"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_quality__scope_project"),
        sa.CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "dataset_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,255}$' AND "
            "evaluation_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_rag_index_quality__refs"),
        sa.CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 AND "
            "octet_length(dataset_fingerprint)=32 AND "
            "octet_length(isolation_attestation_fingerprint)=32 AND "
            "octet_length(evaluation_artifact_fingerprint)=32",
            name="ck_rag_index_quality__fingerprints"),
        sa.CheckConstraint(
            "dataset_case_count BETWEEN 50 AND 10000 AND "
            "classification_correct_count BETWEEN 0 AND dataset_case_count AND "
            "exact_citation_correct_count BETWEEN 0 AND dataset_case_count AND "
            "minimum_classification_basis_points=9000 AND "
            "minimum_exact_citation_basis_points=9800 AND "
            "classification_basis_points="
            "(classification_correct_count::bigint*10000/dataset_case_count) AND "
            "exact_citation_basis_points="
            "(exact_citation_correct_count::bigint*10000/dataset_case_count) AND "
            "out_of_scope_citation_count BETWEEN 0 AND dataset_case_count",
            name="ck_rag_index_quality__metrics"),
        sa.CheckConstraint(
            "(quality_state='PASSED' AND error_code IS NULL AND "
            "classification_basis_points>=minimum_classification_basis_points AND "
            "exact_citation_basis_points>=minimum_exact_citation_basis_points AND "
            "project_isolation_pass AND out_of_scope_citation_count=0 AND "
            "failure_closure_pass) OR (quality_state='FAILED' AND "
            "error_code ~ '^RAG_[A-Z0-9_]{1,59}$')",
            name="ck_rag_index_quality__result"),
        sa.CheckConstraint(
            "created_xid>0 AND isfinite(dataset_sealed_at) AND "
            "isfinite(completed_at) AND dataset_sealed_at<completed_at",
            name="ck_rag_index_quality__time"),
        schema="plm",
    )
    op.create_index(
        "ix_rag_index_quality__index_time",
        "rag_embedding_index_quality_results",
        ["embedding_index_id", sa.text("completed_at DESC"),
         sa.text("quality_result_id DESC")], schema="plm",
    )
    op.create_table(
        "rag_embedding_index_activation_results",
        sa.Column("activation_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("embedding_index_id", ident, nullable=False),
        sa.Column("quality_result_ref", ident, nullable=False),
        sa.Column("retired_index_ref", ident),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("index_purpose", sa.Text(), nullable=False),
        sa.Column("activated_by", ident, nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("expected_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("retired_before_lock_version", sa.BigInteger()),
        sa.Column("retired_after_lock_version", sa.BigInteger()),
        sa.Column("activated_at", timestamp, nullable=False),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["embedding_index_id"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_activation__index", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["quality_result_ref"],
            ["plm.rag_embedding_index_quality_results.quality_result_id"],
            name="fk_rag_index_activation__quality", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["retired_index_ref"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_activation__retired", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_activation__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_activation__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_rag_index_activation__audit", ondelete="NO ACTION"),
        sa.UniqueConstraint("embedding_index_id",
                            name="uq_rag_index_activation__index"),
        sa.UniqueConstraint("quality_result_ref",
                            name="uq_rag_index_activation__quality"),
        sa.UniqueConstraint("retired_index_ref",
                            name="uq_rag_index_activation__retired"),
        sa.UniqueConstraint("audit_event_id",
                            name="uq_rag_index_activation__audit"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_activation__scope_project"),
        sa.CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "embedding_index_id<>coalesce(retired_index_ref,"
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_rag_index_activation__refs"),
        sa.CheckConstraint(
            "expected_lock_version=2 AND lock_version=3 AND "
            "((retired_index_ref IS NULL AND "
            "retired_before_lock_version IS NULL AND retired_after_lock_version IS NULL) "
            "OR (retired_index_ref IS NOT NULL AND "
            "retired_before_lock_version>=3 AND "
            "retired_after_lock_version=retired_before_lock_version+1))",
            name="ck_rag_index_activation__versions"),
        sa.CheckConstraint("created_xid>0 AND isfinite(activated_at)",
                           name="ck_rag_index_activation__time"),
        schema="plm",
    )
    op.execute(_EVIDENCE_GUARDS)
    op.execute(_index_guard())
    op.execute(_ACTIVATION_VALIDATOR)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline RAG Index quality downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.rag_embedding_index_activation_results, "
        "plm.rag_embedding_index_quality_results, "
        "plm.rag_embedding_indexes IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM plm.rag_embedding_index_quality_results)
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_index_activation_results)
               OR EXISTS (SELECT 1 FROM plm.rag_embedding_indexes
                            WHERE index_state IN ('ACTIVE','RETIRED')) THEN
                RAISE EXCEPTION 'RAG Index quality history prevents downgrade';
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_rag_embedding_index_activation_complete "
               "ON plm.rag_embedding_indexes")
    op.execute("DROP FUNCTION plm.validate_rag_embedding_index_activation_transaction()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions."
        "20261004_0086_rag_embedding_index_ready"
    )
    op.execute(previous._index_guard())
    op.execute("DROP TRIGGER trg_rag_embedding_index_activation_no_truncate "
               "ON plm.rag_embedding_index_activation_results")
    op.execute("DROP TRIGGER trg_rag_embedding_index_quality_no_truncate "
               "ON plm.rag_embedding_index_quality_results")
    op.execute("DROP TRIGGER trg_rag_embedding_index_activation_result_guard "
               "ON plm.rag_embedding_index_activation_results")
    op.execute("DROP TRIGGER trg_rag_embedding_index_quality_result_guard "
               "ON plm.rag_embedding_index_quality_results")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index_quality_truncate()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index_activation_result()")
    op.execute("DROP FUNCTION plm.guard_rag_embedding_index_quality_result()")
    op.drop_table("rag_embedding_index_activation_results", schema="plm")
    op.drop_index("ix_rag_index_quality__index_time",
                  table_name="rag_embedding_index_quality_results", schema="plm")
    op.drop_table("rag_embedding_index_quality_results", schema="plm")
