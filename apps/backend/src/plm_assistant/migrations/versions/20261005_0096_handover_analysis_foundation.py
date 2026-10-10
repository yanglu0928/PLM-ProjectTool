"""Add PROJECT Handover analysis identity/version foundation.

Revision ID: 20261005_0096
Revises: 20261005_0095
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261005_0096"
down_revision = "20261005_0095"
branch_labels = None
depends_on = None


_SOURCE_REF = r"source_set_ref ~ '^sha256:[0-9a-f]{64}$'"
_TABLES = (
    "hnd_analyses", "hnd_analysis_versions",
    "hnd_analysis_source_document_refs", "hnd_analysis_ai_task_refs",
    "hnd_analysis_items", "hnd_item_evidence_refs",
    "hnd_item_capability_refs", "hnd_item_options",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_analysis_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Handover Analysis Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='hnd_analyses' THEN
    IF NEW.analysis_state<>'ACTIVE'
       OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'HandoverAnalysis initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_analysis_versions' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'HandoverAnalysisVersion initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_analysis_items' THEN
    IF NEW.item_state<>'CANDIDATE' THEN
      RAISE EXCEPTION 'Handover AnalysisItem initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_handover_analysis_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_version uuid;
  version_row plm.hnd_analysis_versions%ROWTYPE;
  actual_source_ref text;
BEGIN
  target_version := NEW.handover_analysis_version_id;
  SELECT * INTO version_row FROM plm.hnd_analysis_versions
   WHERE handover_analysis_version_id=target_version;
  IF version_row.handover_analysis_version_id IS NULL THEN
    RAISE EXCEPTION 'Handover AnalysisVersion is missing';
  END IF;
  IF version_row.declared_source_count<>(
       SELECT count(*) FROM plm.hnd_analysis_source_document_refs
        WHERE handover_analysis_version_id=target_version)
     OR version_row.declared_item_count<>(
       SELECT count(*) FROM plm.hnd_analysis_items
        WHERE handover_analysis_version_id=target_version)
     OR version_row.declared_evidence_count<>(
       SELECT count(*) FROM plm.hnd_item_evidence_refs
        WHERE handover_analysis_version_id=target_version)
     OR version_row.declared_capability_ref_count<>(
       SELECT count(*) FROM plm.hnd_item_capability_refs
        WHERE handover_analysis_version_id=target_version)
     OR version_row.declared_ai_task_count<>(
       SELECT count(*) FROM plm.hnd_analysis_ai_task_refs
        WHERE handover_analysis_version_id=target_version) THEN
    RAISE EXCEPTION 'Handover AnalysisVersion declared counts are incomplete';
  END IF;
  SELECT 'sha256:' || encode(sha256(convert_to(
           'handover-source-set.v1' || chr(10) ||
           string_agg(source.document_version_id::text, chr(10)
                      ORDER BY source.document_version_id::text), 'UTF8')), 'hex')
    INTO actual_source_ref
    FROM (SELECT DISTINCT document_version_id
            FROM plm.hnd_analysis_source_document_refs
           WHERE handover_analysis_version_id=target_version) source;
  IF actual_source_ref IS DISTINCT FROM version_row.source_set_ref THEN
    RAISE EXCEPTION 'Handover source set fingerprint is invalid';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_source_document_refs r
       JOIN plm.doc_document_versions v
         ON v.document_version_id=r.document_version_id
        AND v.document_id=r.document_id
       JOIN plm.doc_documents d ON d.document_id=r.document_id
        WHERE r.handover_analysis_version_id=target_version
          AND (r.project_id<>version_row.project_id OR v.scope<>'PROJECT'
               OR v.project_id<>version_row.project_id
               OR v.availability_state<>'AVAILABLE'
               OR d.scope<>'PROJECT' OR d.project_id<>version_row.project_id
               OR d.document_state<>'ACTIVE')) THEN
    RAISE EXCEPTION 'Handover document source is not current project evidence';
  END IF;
  IF NOT EXISTS (
       SELECT 1 FROM plm.cap_baseline_versions v
       JOIN plm.cap_baselines b ON b.baseline_id=v.baseline_id
        WHERE v.baseline_version_id=version_row.capability_baseline_version_ref
          AND v.baseline_id=version_row.capability_baseline_id
          AND v.version_state='APPROVED' AND b.baseline_state='ACTIVE'
          AND b.current_approved_version_ref=v.baseline_version_id) THEN
    RAISE EXCEPTION 'Handover requires an approved Capability baseline version';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_items i
        WHERE i.handover_analysis_version_id=target_version
          AND NOT i.source_missing
          AND NOT EXISTS (
                SELECT 1 FROM plm.hnd_item_evidence_refs e
                 WHERE e.analysis_item_row_id=i.analysis_item_row_id)) THEN
    RAISE EXCEPTION 'Handover AnalysisItem requires evidence or missing-source declaration';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_items i
        WHERE i.handover_analysis_version_id=target_version
          AND i.item_type='NEED_CONFIRM'
          AND (i.confirmation_question IS NULL
               OR char_length(btrim(i.confirmation_question))=0
               OR i.recommendation IS NULL
               OR NOT (i.required_input_spec ? 'fields')
               OR jsonb_typeof(i.required_input_spec->'fields')<>'array'
               OR jsonb_array_length(i.required_input_spec->'fields')=0
               OR (SELECT count(*) FROM plm.hnd_item_options o
                    WHERE o.analysis_item_row_id=i.analysis_item_row_id)<2)) THEN
    RAISE EXCEPTION 'Handover NEED_CONFIRM prompt is incomplete';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_item_evidence_refs r
       JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id
        WHERE r.handover_analysis_version_id=target_version
          AND (e.scope<>'PROJECT' OR e.project_id<>version_row.project_id
               OR e.eligibility_state<>'ELIGIBLE')) THEN
    RAISE EXCEPTION 'Handover evidence is not eligible for the project';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_item_capability_refs r
       JOIN plm.cap_items i
         ON i.baseline_version_id=r.baseline_version_id
        AND i.capability_item_id=r.capability_item_id
        WHERE r.handover_analysis_version_id=target_version
          AND (r.baseline_version_id<>version_row.capability_baseline_version_ref
               OR i.item_state<>'AVAILABLE')) THEN
    RAISE EXCEPTION 'Handover capability item is outside the fixed approved baseline';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_ai_task_refs r
       JOIN plm.ai_tasks t ON t.ai_task_id=r.ai_task_id
        WHERE r.handover_analysis_version_id=target_version
          AND (t.scope<>'PROJECT' OR t.project_id<>version_row.project_id
               OR t.task_type<>'GAP_ANALYSIS' OR t.task_state<>'SUCCEEDED')) THEN
    RAISE EXCEPTION 'Handover AI task provenance is invalid';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_handover_analysis_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Handover analysis history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "hnd_analyses",
        sa.Column("handover_analysis_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("analysis_purpose", sa.Text(), nullable=False),
        sa.Column("source_set_ref", sa.Text(), nullable=False),
        sa.Column("analysis_state", sa.Text(), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("handover_analysis_id", "project_id",
                            name="uq_hnd_analyses__id_project"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_hnd_analyses__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_hnd_analyses__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_hnd_analyses__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("char_length(analysis_purpose) BETWEEN 1 AND 255 AND analysis_purpose=btrim(analysis_purpose)", name="ck_hnd_analyses__purpose"),
        sa.CheckConstraint(_SOURCE_REF, name="ck_hnd_analyses__source_ref"),
        sa.CheckConstraint("analysis_state IN ('ACTIVE','ARCHIVED','RESTRICTED')", name="ck_hnd_analyses__state"),
        sa.CheckConstraint("lock_version>=0", name="ck_hnd_analyses__lock"),
        schema="plm",
    )
    op.create_index("ix_hnd_analyses__project_state", "hnd_analyses",
                    ["project_id", "analysis_state", "handover_analysis_id"], schema="plm")
    op.create_table(
        "hnd_analysis_versions",
        sa.Column("handover_analysis_version_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("handover_analysis_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("source_set_ref", sa.Text(), nullable=False),
        sa.Column("capability_baseline_id", ident, nullable=False),
        sa.Column("capability_baseline_version_ref", ident, nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_source_count", sa.Integer(), nullable=False),
        sa.Column("declared_item_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_count", sa.Integer(), nullable=False),
        sa.Column("declared_capability_ref_count", sa.Integer(), nullable=False),
        sa.Column("declared_ai_task_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("handover_analysis_version_id", "handover_analysis_id",
                            "project_id", name="uq_hnd_versions__id_analysis_project"),
        sa.UniqueConstraint("handover_analysis_id", "version_no",
                            name="uq_hnd_versions__analysis_no"),
        sa.ForeignKeyConstraint(["handover_analysis_id", "project_id"],
                                ["plm.hnd_analyses.handover_analysis_id", "plm.hnd_analyses.project_id"],
                                name="fk_hnd_versions__analysis", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "handover_analysis_id", "project_id"],
                                ["plm.hnd_analysis_versions.handover_analysis_version_id", "plm.hnd_analysis_versions.handover_analysis_id", "plm.hnd_analysis_versions.project_id"],
                                name="fk_hnd_versions__supersedes", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["capability_baseline_version_ref", "capability_baseline_id"],
                                ["plm.cap_baseline_versions.baseline_version_id", "plm.cap_baseline_versions.baseline_id"],
                                name="fk_hnd_versions__capability_version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"], name="fk_hnd_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"], name="fk_hnd_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_hnd_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_hnd_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')", name="ck_hnd_versions__state"),
        sa.CheckConstraint(_SOURCE_REF, name="ck_hnd_versions__source_ref"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_hnd_versions__fingerprint"),
        sa.CheckConstraint("declared_source_count>0 AND declared_item_count>0 AND declared_evidence_count>=0 AND declared_capability_ref_count>=0 AND declared_ai_task_count>=0", name="ck_hnd_versions__counts"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR (review_ref IS NOT NULL AND review_round_ref IS NOT NULL)", name="ck_hnd_versions__review_shape"),
        schema="plm",
    )
    op.create_index("ix_hnd_versions__analysis_created", "hnd_analysis_versions",
                    ["handover_analysis_id", "created_at"], schema="plm")
    op.create_index(
        "uq_hnd_versions__analysis_in_review", "hnd_analysis_versions",
        ["handover_analysis_id"], unique=True, schema="plm",
        postgresql_where=sa.text("version_state='IN_REVIEW'"),
    )
    op.create_index(
        "uq_hnd_versions__analysis_approved", "hnd_analysis_versions",
        ["handover_analysis_id"], unique=True, schema="plm",
        postgresql_where=sa.text("version_state='APPROVED'"),
    )
    op.create_foreign_key(
        "fk_hnd_analyses__approved_version", "hnd_analyses", "hnd_analysis_versions",
        ["current_approved_version_ref", "handover_analysis_id", "project_id"],
        ["handover_analysis_version_id", "handover_analysis_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
    )
    _create_owned_tables(ident)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__owner BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW EXECUTE FUNCTION "
            "plm.guard_handover_analysis_foundation()"
        ))
        op.execute(sa.text(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE "
            f"ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION "
            "plm.reject_handover_analysis_truncate()"
        ))
    for table in _TABLES[1:]:
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__complete AFTER INSERT ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "
            "plm.validate_handover_analysis_foundation()"
        ))


def _create_owned_tables(ident) -> None:
    version_fk = (["handover_analysis_version_id", "handover_analysis_id", "project_id"],
                  ["plm.hnd_analysis_versions.handover_analysis_version_id",
                   "plm.hnd_analysis_versions.handover_analysis_id",
                   "plm.hnd_analysis_versions.project_id"])
    op.create_table(
        "hnd_analysis_source_document_refs",
        sa.Column("source_document_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("handover_analysis_version_id", ident, nullable=False), sa.Column("handover_analysis_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False), sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("handover_analysis_version_id", "document_version_id", name="uq_hnd_source_docs__version_document"),
        sa.UniqueConstraint("handover_analysis_version_id", "ordinal", name="uq_hnd_source_docs__version_ordinal"),
        sa.ForeignKeyConstraint(*version_fk, name="fk_hnd_source_docs__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["document_version_id", "document_id"], ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"], name="fk_hnd_source_docs__document_version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_source_docs__ordinal"), schema="plm")
    op.create_index("ix_hnd_source_docs__document_version", "hnd_analysis_source_document_refs", ["document_version_id"], schema="plm")
    op.create_table(
        "hnd_analysis_ai_task_refs",
        sa.Column("ai_task_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("handover_analysis_version_id", ident, nullable=False), sa.Column("handover_analysis_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False), sa.Column("ai_task_id", ident, nullable=False),
        sa.Column("task_scope", sa.Text(), nullable=False, server_default=sa.text("'PROJECT'")), sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("handover_analysis_version_id", "ai_task_id", name="uq_hnd_ai_refs__version_task"),
        sa.UniqueConstraint("handover_analysis_version_id", "ordinal", name="uq_hnd_ai_refs__version_ordinal"),
        sa.ForeignKeyConstraint(*version_fk, name="fk_hnd_ai_refs__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["ai_task_id", "task_scope", "project_id"], ["plm.ai_tasks.ai_task_id", "plm.ai_tasks.scope", "plm.ai_tasks.project_id"], name="fk_hnd_ai_refs__task", ondelete="NO ACTION"),
        sa.CheckConstraint("task_scope='PROJECT'", name="ck_hnd_ai_refs__scope"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_ai_refs__ordinal"), schema="plm")
    op.create_table(
        "hnd_analysis_items",
        sa.Column("analysis_item_row_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("handover_analysis_version_id", ident, nullable=False), sa.Column("handover_analysis_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False), sa.Column("analysis_item_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False), sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False), sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text()),
        sa.Column("confirmation_question", sa.Text()),
        sa.Column("required_input_spec", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_missing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("item_state", sa.Text(), nullable=False, server_default=sa.text("'CANDIDATE'")),
        sa.UniqueConstraint("analysis_item_row_id", "handover_analysis_version_id", "handover_analysis_id", "project_id", name="uq_hnd_items__row_version_analysis_project"),
        sa.UniqueConstraint("handover_analysis_version_id", "analysis_item_id", name="uq_hnd_items__version_stable"),
        sa.UniqueConstraint("handover_analysis_version_id", "ordinal", name="uq_hnd_items__version_ordinal"),
        sa.ForeignKeyConstraint(*version_fk, name="fk_hnd_items__version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_items__ordinal"),
        sa.CheckConstraint("item_type IN ('GAP','MISSING','CONFLICT','RISK','SCOPE','NEED_CONFIRM')", name="ck_hnd_items__type"),
        sa.CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL') AND priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_hnd_items__classification"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title) AND char_length(statement) BETWEEN 1 AND 4000 AND statement=btrim(statement) AND char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)", name="ck_hnd_items__texts"),
        sa.CheckConstraint("recommendation IS NULL OR (char_length(recommendation) BETWEEN 1 AND 2000 AND recommendation=btrim(recommendation))", name="ck_hnd_items__recommendation"),
        sa.CheckConstraint("item_state IN ('CANDIDATE','CONFIRMED','RESOLVED','ACCEPTED_RISK','REJECTED','SUPERSEDED')", name="ck_hnd_items__state"),
        sa.CheckConstraint("jsonb_typeof(required_input_spec)='object'", name="ck_hnd_items__input_spec"), schema="plm")
    op.create_index("ix_hnd_items__version_ordinal", "hnd_analysis_items", ["handover_analysis_version_id", "ordinal"], schema="plm")
    item_fk = (["analysis_item_row_id", "handover_analysis_version_id", "handover_analysis_id", "project_id"],
               ["plm.hnd_analysis_items.analysis_item_row_id", "plm.hnd_analysis_items.handover_analysis_version_id", "plm.hnd_analysis_items.handover_analysis_id", "plm.hnd_analysis_items.project_id"])
    op.create_table(
        "hnd_item_evidence_refs",
        sa.Column("item_evidence_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("analysis_item_row_id", ident, nullable=False), sa.Column("handover_analysis_version_id", ident, nullable=False),
        sa.Column("handover_analysis_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_item_row_id", "evidence_id", name="uq_hnd_item_evidence__item_evidence"),
        sa.UniqueConstraint("analysis_item_row_id", "ordinal", name="uq_hnd_item_evidence__item_ordinal"),
        sa.ForeignKeyConstraint(*item_fk, name="fk_hnd_item_evidence__item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"], name="fk_hnd_item_evidence__evidence", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_item_evidence__ordinal"), schema="plm")
    op.create_index("ix_hnd_item_evidence__evidence", "hnd_item_evidence_refs", ["evidence_id"], schema="plm")
    op.create_table(
        "hnd_item_capability_refs",
        sa.Column("item_capability_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("analysis_item_row_id", ident, nullable=False), sa.Column("handover_analysis_version_id", ident, nullable=False),
        sa.Column("handover_analysis_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        sa.Column("baseline_version_id", ident, nullable=False), sa.Column("capability_item_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_item_row_id", "baseline_version_id", "capability_item_id", name="uq_hnd_item_capability__item_capability"),
        sa.UniqueConstraint("analysis_item_row_id", "ordinal", name="uq_hnd_item_capability__item_ordinal"),
        sa.ForeignKeyConstraint(*item_fk, name="fk_hnd_item_capability__item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["baseline_version_id", "capability_item_id"], ["plm.cap_items.baseline_version_id", "plm.cap_items.capability_item_id"], name="fk_hnd_item_capability__capability", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_item_capability__ordinal"), schema="plm")
    op.create_table(
        "hnd_item_options",
        sa.Column("item_option_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("analysis_item_row_id", ident, nullable=False), sa.Column("handover_analysis_version_id", ident, nullable=False),
        sa.Column("handover_analysis_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        sa.Column("option_code", sa.Text(), nullable=False), sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_item_row_id", "option_code", name="uq_hnd_item_options__item_code"),
        sa.UniqueConstraint("analysis_item_row_id", "ordinal", name="uq_hnd_item_options__item_ordinal"),
        sa.ForeignKeyConstraint(*item_fk, name="fk_hnd_item_options__item", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_hnd_item_options__ordinal"),
        sa.CheckConstraint("option_code ~ '^[A-Z][A-Z0-9_-]{0,31}$'", name="ck_hnd_item_options__code"),
        sa.CheckConstraint("char_length(label) BETWEEN 1 AND 255 AND label=btrim(label)", name="ck_hnd_item_options__label"), schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover analysis foundation downgrade is disabled")
    op.execute("LOCK TABLE " + ", ".join("plm." + table for table in _TABLES)
               + " IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.hnd_analyses)
             OR EXISTS (SELECT 1 FROM plm.hnd_analysis_versions)
             OR EXISTS (SELECT 1 FROM plm.hnd_analysis_source_document_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_analysis_ai_task_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_analysis_items)
             OR EXISTS (SELECT 1 FROM plm.hnd_item_evidence_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_item_capability_refs)
             OR EXISTS (SELECT 1 FROM plm.hnd_item_options) THEN
            RAISE EXCEPTION 'Handover analysis history prevents downgrade';
          END IF;
        END $$;
    """)
    op.drop_constraint("fk_hnd_analyses__approved_version", "hnd_analyses",
                       schema="plm", type_="foreignkey")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_handover_analysis_foundation()")
    op.execute("DROP FUNCTION plm.guard_handover_analysis_foundation()")
    op.execute("DROP FUNCTION plm.reject_handover_analysis_truncate()")
