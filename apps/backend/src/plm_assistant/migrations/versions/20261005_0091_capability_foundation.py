"""Add GLOBAL Capability baseline/version/item foundation.

Revision ID: 20261005_0091
Revises: 20261004_0090
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261005_0091"
down_revision = "20261004_0090"
branch_labels = None
depends_on = None


_SOURCE_REF = r"source_collection_ref ~ '^sha256:[0-9a-f]{64}$'"
_TABLES = (
    "cap_baselines", "cap_baseline_versions", "cap_items",
    "cap_item_document_refs", "cap_item_evidence_refs",
)

_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_capability_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Capability Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='cap_baselines' THEN
    IF NEW.baseline_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'CapabilityBaseline initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='cap_baseline_versions' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'Capability BaselineVersion initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.validate_capability_version_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_version uuid;
  version_row plm.cap_baseline_versions%ROWTYPE;
  actual_source_ref text;
  baseline_source_ref text;
BEGIN
  target_version := CASE WHEN TG_TABLE_NAME='cap_baseline_versions'
                         THEN NEW.baseline_version_id
                         ELSE NEW.baseline_version_id END;
  SELECT * INTO version_row FROM plm.cap_baseline_versions
   WHERE baseline_version_id=target_version;
  IF version_row.baseline_version_id IS NULL THEN
    RAISE EXCEPTION 'Capability BaselineVersion is missing';
  END IF;
  SELECT source_collection_ref INTO baseline_source_ref
    FROM plm.cap_baselines WHERE baseline_id=version_row.baseline_id;
  IF version_row.declared_item_count<>(
       SELECT count(*) FROM plm.cap_items
        WHERE baseline_version_id=target_version)
     OR version_row.declared_document_ref_count<>(
       SELECT count(*) FROM plm.cap_item_document_refs
        WHERE baseline_version_id=target_version)
     OR version_row.declared_evidence_ref_count<>(
       SELECT count(*) FROM plm.cap_item_evidence_refs
        WHERE baseline_version_id=target_version) THEN
    RAISE EXCEPTION 'Capability BaselineVersion declared counts are incomplete';
  END IF;
  SELECT 'sha256:' || encode(sha256(convert_to(
           'capability-source-set.v1' || chr(10) ||
           string_agg(source.document_version_id::text, chr(10)
                      ORDER BY source.document_version_id::text), 'UTF8')), 'hex')
    INTO actual_source_ref
    FROM (SELECT DISTINCT document_version_id
            FROM plm.cap_item_document_refs
           WHERE baseline_version_id=target_version) source;
  IF actual_source_ref IS DISTINCT FROM version_row.source_collection_ref
     OR baseline_source_ref IS DISTINCT FROM version_row.source_collection_ref THEN
    RAISE EXCEPTION 'Capability source collection fingerprint is invalid';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.cap_items i
        WHERE i.baseline_version_id=target_version
          AND (NOT EXISTS (
                 SELECT 1 FROM plm.cap_item_document_refs d
                  WHERE d.capability_item_row_id=i.capability_item_row_id)
               OR NOT EXISTS (
                 SELECT 1 FROM plm.cap_item_evidence_refs e
                  WHERE e.capability_item_row_id=i.capability_item_row_id))) THEN
    RAISE EXCEPTION 'CapabilityItem requires document and evidence';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.cap_item_document_refs r
       JOIN plm.doc_document_versions v
         ON v.document_version_id=r.document_version_id
        AND v.document_id=r.document_id
       JOIN plm.doc_documents d ON d.document_id=r.document_id
        WHERE r.baseline_version_id=target_version
          AND (v.scope<>'GLOBAL' OR v.project_id IS NOT NULL
               OR v.availability_state<>'AVAILABLE'
               OR d.scope<>'GLOBAL' OR d.project_id IS NOT NULL
               OR d.document_category<>'STANDARD_CAPABILITY'
               OR d.document_state<>'ACTIVE')) THEN
    RAISE EXCEPTION 'Capability document source is not an available GLOBAL standard';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.cap_item_evidence_refs r
       JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id
        WHERE r.baseline_version_id=target_version
          AND (e.scope<>'GLOBAL' OR e.project_id IS NOT NULL
               OR e.eligibility_state<>'ELIGIBLE'
               OR NOT EXISTS (
                    SELECT 1 FROM plm.cap_item_document_refs d
                     WHERE d.capability_item_row_id=r.capability_item_row_id
                       AND d.document_id=e.document_id
                       AND d.document_version_id=e.document_version_id))) THEN
    RAISE EXCEPTION 'Capability evidence is not eligible or source-bound';
  END IF;
  RETURN NULL;
END; $$;

CREATE TRIGGER trg_cap_baselines__owner_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.cap_baselines
FOR EACH ROW EXECUTE FUNCTION plm.guard_capability_foundation();
CREATE TRIGGER trg_cap_versions__owner_guard
BEFORE INSERT OR UPDATE OR DELETE ON plm.cap_baseline_versions
FOR EACH ROW EXECUTE FUNCTION plm.guard_capability_foundation();
CREATE TRIGGER trg_cap_items__owner_guard
BEFORE UPDATE OR DELETE ON plm.cap_items
FOR EACH ROW EXECUTE FUNCTION plm.guard_capability_foundation();
CREATE TRIGGER trg_cap_item_docs__owner_guard
BEFORE UPDATE OR DELETE ON plm.cap_item_document_refs
FOR EACH ROW EXECUTE FUNCTION plm.guard_capability_foundation();
CREATE TRIGGER trg_cap_item_evidence__owner_guard
BEFORE UPDATE OR DELETE ON plm.cap_item_evidence_refs
FOR EACH ROW EXECUTE FUNCTION plm.guard_capability_foundation();

CREATE CONSTRAINT TRIGGER trg_cap_versions__complete
AFTER INSERT ON plm.cap_baseline_versions DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_capability_version_foundation();
CREATE CONSTRAINT TRIGGER trg_cap_items__complete
AFTER INSERT ON plm.cap_items DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_capability_version_foundation();
CREATE CONSTRAINT TRIGGER trg_cap_item_docs__complete
AFTER INSERT ON plm.cap_item_document_refs DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_capability_version_foundation();
CREATE CONSTRAINT TRIGGER trg_cap_item_evidence__complete
AFTER INSERT ON plm.cap_item_evidence_refs DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION plm.validate_capability_version_foundation();

CREATE OR REPLACE FUNCTION plm.reject_capability_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Capability history cannot be truncated';
END; $$;
CREATE TRIGGER trg_cap_baselines__no_truncate BEFORE TRUNCATE ON plm.cap_baselines
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_capability_truncate();
CREATE TRIGGER trg_cap_versions__no_truncate BEFORE TRUNCATE ON plm.cap_baseline_versions
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_capability_truncate();
CREATE TRIGGER trg_cap_items__no_truncate BEFORE TRUNCATE ON plm.cap_items
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_capability_truncate();
CREATE TRIGGER trg_cap_item_docs__no_truncate BEFORE TRUNCATE ON plm.cap_item_document_refs
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_capability_truncate();
CREATE TRIGGER trg_cap_item_evidence__no_truncate BEFORE TRUNCATE ON plm.cap_item_evidence_refs
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_capability_truncate();
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        "cap_baselines",
        sa.Column("baseline_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("baseline_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("baseline_state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("source_collection_ref", sa.Text(), nullable=False),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", ident),
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("baseline_code", name="uq_cap_baselines__code"),
        sa.UniqueConstraint("baseline_id", "source_collection_ref", name="uq_cap_baselines__id_source"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_cap_baselines__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"], name="fk_cap_baselines__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("baseline_code ~ '^[A-Z][A-Z0-9_.-]{0,63}$'", name="ck_cap_baselines__code"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)", name="ck_cap_baselines__name"),
        sa.CheckConstraint("description IS NULL OR (char_length(description) BETWEEN 1 AND 2000 AND description=btrim(description))", name="ck_cap_baselines__description"),
        sa.CheckConstraint("baseline_state IN ('ACTIVE','ARCHIVED','RESTRICTED')", name="ck_cap_baselines__state"),
        sa.CheckConstraint(_SOURCE_REF, name="ck_cap_baselines__source_ref"),
        sa.CheckConstraint("lock_version>=0", name="ck_cap_baselines__lock"),
        schema="plm",
    )
    op.create_index("ix_cap_baselines__state_code", "cap_baselines", ["baseline_state", "baseline_code"], schema="plm")
    op.create_table(
        "cap_baseline_versions",
        sa.Column("baseline_version_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("baseline_id", ident, nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_state", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("source_collection_ref", sa.Text(), nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_item_count", sa.Integer(), nullable=False),
        sa.Column("declared_document_ref_count", sa.Integer(), nullable=False),
        sa.Column("declared_evidence_ref_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_version_ref", ident),
        sa.Column("review_ref", ident),
        sa.Column("review_round_ref", ident),
        sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", timestamp, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("baseline_version_id", "baseline_id", name="uq_cap_versions__id_baseline"),
        sa.UniqueConstraint("baseline_id", "version_no", name="uq_cap_versions__baseline_no"),
        sa.ForeignKeyConstraint(["baseline_id"], ["plm.cap_baselines.baseline_id"], name="fk_cap_versions__baseline", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "baseline_id"], ["plm.cap_baseline_versions.baseline_version_id", "plm.cap_baseline_versions.baseline_id"], name="fk_cap_versions__supersedes", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"], name="fk_cap_versions__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"], name="fk_cap_versions__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_cap_versions__creator", ondelete="NO ACTION"),
        sa.CheckConstraint("version_no>0", name="ck_cap_versions__number"),
        sa.CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')", name="ck_cap_versions__state"),
        sa.CheckConstraint(_SOURCE_REF, name="ck_cap_versions__source_ref"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_cap_versions__fingerprint"),
        sa.CheckConstraint("declared_item_count>0 AND declared_document_ref_count>0 AND declared_evidence_ref_count>=declared_item_count", name="ck_cap_versions__counts"),
        sa.CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR (review_ref IS NOT NULL AND review_round_ref IS NOT NULL)", name="ck_cap_versions__review_shape"),
        schema="plm",
    )
    op.create_index("ix_cap_versions__baseline_created", "cap_baseline_versions", ["baseline_id", "created_at"], schema="plm")
    op.create_foreign_key("fk_cap_baselines__approved_version", "cap_baselines", "cap_baseline_versions", ["current_approved_version_ref", "baseline_id"], ["baseline_version_id", "baseline_id"], source_schema="plm", referent_schema="plm", ondelete="NO ACTION")
    op.create_table(
        "cap_items",
        sa.Column("capability_item_row_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("baseline_version_id", ident, nullable=False),
        sa.Column("baseline_id", ident, nullable=False),
        sa.Column("capability_item_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("capability_code", sa.Text(), nullable=False),
        sa.Column("domain_name", sa.Text(), nullable=False),
        sa.Column("module_name", sa.Text(), nullable=False),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("boundary_text", sa.Text(), nullable=False),
        sa.Column("prerequisites", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("interface_refs", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("item_state", sa.Text(), nullable=False),
        sa.UniqueConstraint("capability_item_row_id", "baseline_version_id", "baseline_id", name="uq_cap_items__row_version_baseline"),
        sa.UniqueConstraint("baseline_version_id", "capability_item_id", name="uq_cap_items__version_stable"),
        sa.UniqueConstraint("baseline_version_id", "capability_code", name="uq_cap_items__version_code"),
        sa.UniqueConstraint("baseline_version_id", "ordinal", name="uq_cap_items__version_ordinal"),
        sa.ForeignKeyConstraint(["baseline_version_id", "baseline_id"], ["plm.cap_baseline_versions.baseline_version_id", "plm.cap_baseline_versions.baseline_id"], name="fk_cap_items__version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_cap_items__ordinal"),
        sa.CheckConstraint("capability_code ~ '^[A-Z][A-Z0-9_.-]{0,63}$'", name="ck_cap_items__code"),
        sa.CheckConstraint("char_length(domain_name) BETWEEN 1 AND 255 AND domain_name=btrim(domain_name) AND char_length(module_name) BETWEEN 1 AND 255 AND module_name=btrim(module_name) AND char_length(feature_name) BETWEEN 1 AND 255 AND feature_name=btrim(feature_name)", name="ck_cap_items__classification"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)", name="ck_cap_items__name"),
        sa.CheckConstraint("char_length(description) BETWEEN 1 AND 2000 AND description=btrim(description) AND char_length(boundary_text) BETWEEN 1 AND 2000 AND boundary_text=btrim(boundary_text)", name="ck_cap_items__texts"),
        sa.CheckConstraint("cardinality(prerequisites)<=100 AND cardinality(interface_refs)<=100 AND array_position(prerequisites,NULL) IS NULL AND array_position(interface_refs,NULL) IS NULL", name="ck_cap_items__arrays"),
        sa.CheckConstraint("item_state IN ('AVAILABLE','DEPRECATED','WITHDRAWN')", name="ck_cap_items__state"),
        schema="plm",
    )
    op.create_index("ix_cap_items__version_ordinal", "cap_items", ["baseline_version_id", "ordinal"], schema="plm")
    op.create_table(
        "cap_item_document_refs",
        sa.Column("capability_item_document_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("capability_item_row_id", ident, nullable=False),
        sa.Column("baseline_version_id", ident, nullable=False),
        sa.Column("baseline_id", ident, nullable=False),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("capability_item_row_id", "document_version_id", name="uq_cap_item_docs__item_version"),
        sa.UniqueConstraint("capability_item_row_id", "ordinal", name="uq_cap_item_docs__item_ordinal"),
        sa.ForeignKeyConstraint(["capability_item_row_id", "baseline_version_id", "baseline_id"], ["plm.cap_items.capability_item_row_id", "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"], name="fk_cap_item_docs__item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["document_version_id", "document_id"], ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"], name="fk_cap_item_docs__document_version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_cap_item_docs__ordinal"),
        schema="plm",
    )
    op.create_index("ix_cap_item_docs__document_version", "cap_item_document_refs", ["document_version_id"], schema="plm")
    op.create_table(
        "cap_item_evidence_refs",
        sa.Column("capability_item_evidence_ref_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("capability_item_row_id", ident, nullable=False),
        sa.Column("baseline_version_id", ident, nullable=False),
        sa.Column("baseline_id", ident, nullable=False),
        sa.Column("evidence_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("capability_item_row_id", "evidence_id", name="uq_cap_item_evidence__item_evidence"),
        sa.UniqueConstraint("capability_item_row_id", "ordinal", name="uq_cap_item_evidence__item_ordinal"),
        sa.ForeignKeyConstraint(["capability_item_row_id", "baseline_version_id", "baseline_id"], ["plm.cap_items.capability_item_row_id", "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"], name="fk_cap_item_evidence__item", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"], name="fk_cap_item_evidence__evidence", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>=0", name="ck_cap_item_evidence__ordinal"),
        schema="plm",
    )
    op.create_index("ix_cap_item_evidence__evidence", "cap_item_evidence_refs", ["evidence_id"], schema="plm")
    op.execute(_GUARDS)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Capability foundation downgrade is disabled")
    op.execute(
        "LOCK TABLE " + ", ".join("plm." + table for table in _TABLES)
        + " IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.cap_baselines)
             OR EXISTS (SELECT 1 FROM plm.cap_baseline_versions)
             OR EXISTS (SELECT 1 FROM plm.cap_items)
             OR EXISTS (SELECT 1 FROM plm.cap_item_document_refs)
             OR EXISTS (SELECT 1 FROM plm.cap_item_evidence_refs) THEN
            RAISE EXCEPTION 'Capability history prevents downgrade';
          END IF;
        END $$;
    """)
    op.drop_constraint("fk_cap_baselines__approved_version", "cap_baselines", schema="plm", type_="foreignkey")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_capability_version_foundation()")
    op.execute("DROP FUNCTION plm.guard_capability_foundation()")
    op.execute("DROP FUNCTION plm.reject_capability_truncate()")
