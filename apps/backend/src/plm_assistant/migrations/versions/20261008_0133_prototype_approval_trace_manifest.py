"""Add immutable Prototype approval Trace manifest and exact edge closure.

Revision ID: 20261008_0133
Revises: 20261008_0132
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261008_0133"
down_revision = "20261008_0132"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_prototype_approval_trace_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Prototype approval Trace history is immutable';
  END IF;
  IF TG_TABLE_NAME='prt_version_approval_trace_manifests' THEN
    RETURN NEW;
  ELSIF TG_TABLE_NAME='prt_version_approval_trace_sources' THEN
    IF NOT EXISTS (
      SELECT 1 FROM plm.trc_links l
       WHERE l.trace_link_id=NEW.trace_link_id
         AND l.scope='PROJECT' AND l.project_id=NEW.project_id
         AND l.source_owner_module=NEW.source_owner_module
         AND l.source_object_type=NEW.source_object_type
         AND l.source_object_id=NEW.source_object_id
         AND l.source_version_id=NEW.source_version_id
         AND l.source_project_id IS NOT DISTINCT FROM NEW.source_project_id
         AND l.target_owner_module='prototype' AND l.target_object_type='PRT-03'
         AND l.target_object_id=NEW.prototype_id
         AND l.target_version_id=NEW.prototype_version_id
         AND l.target_project_id=NEW.project_id
         AND l.relation_type=NEW.relation_type
         AND l.link_state='ACTIVE'
    ) THEN
      RAISE EXCEPTION 'Prototype approval Trace source does not match active TraceLink';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Unknown Prototype approval Trace table';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_prototype_approval_trace_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE manifest_row plm.prt_version_approval_trace_manifests%ROWTYPE;
DECLARE source_count integer; min_ordinal integer; max_ordinal integer;
BEGIN
  SELECT * INTO manifest_row
    FROM plm.prt_version_approval_trace_manifests
   WHERE approval_trace_manifest_id=NEW.approval_trace_manifest_id;
  IF NOT FOUND THEN RETURN NULL; END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM plm.prt_prototype_versions v
      JOIN plm.prt_prototypes p
        ON p.prototype_id=v.prototype_id AND p.project_id=v.project_id
      JOIN plm.prt_version_review_state_results rs
        ON rs.review_state_result_id=manifest_row.review_state_result_id
      JOIN plm.rvw_reviews r ON r.review_id=manifest_row.review_id
      JOIN plm.rvw_review_rounds rr
        ON rr.review_round_id=manifest_row.review_round_id
      JOIN plm.prt_template_versions tv
        ON tv.prototype_template_version_id=manifest_row.template_version_id
       AND tv.prototype_template_id=manifest_row.template_id
     WHERE v.prototype_version_id=manifest_row.prototype_version_id
       AND v.prototype_id=manifest_row.prototype_id
       AND v.project_id=manifest_row.project_id
       AND v.version_state='APPROVED'
       AND v.template_ref=manifest_row.template_id
       AND v.template_version_ref=manifest_row.template_version_id
       AND v.review_ref=manifest_row.review_id
       AND v.review_round_ref=manifest_row.review_round_id
       AND v.content_fingerprint=manifest_row.content_fingerprint
       AND v.declared_artifact_count=manifest_row.declared_artifact_count
       AND v.declared_requirement_count=manifest_row.declared_requirement_count
       AND p.prototype_state='ACTIVE'
       AND p.current_approved_version_ref=v.prototype_version_id
       AND rs.prototype_version_id=v.prototype_version_id
       AND rs.prototype_id=v.prototype_id AND rs.project_id=v.project_id
       AND rs.review_id=manifest_row.review_id
       AND rs.review_round_id=manifest_row.review_round_id
       AND rs.event_type='APPROVED'
       AND rs.current_approved_version_ref=v.prototype_version_id
       AND rs.actor_id=manifest_row.approved_by
       AND r.scope='PROJECT' AND r.project_id=manifest_row.project_id
       AND r.subject_type='PRT-03' AND r.subject_id=manifest_row.prototype_id
       AND r.review_state='APPROVED'
       AND rr.review_id=r.review_id AND rr.scope='PROJECT'
       AND rr.project_id=manifest_row.project_id
       AND rr.subject_version_id=manifest_row.prototype_version_id
       AND rr.round_state='APPROVED'
       AND tv.version_state='PUBLISHED'
       AND (tv.scope='GLOBAL' OR
            (tv.scope='PROJECT' AND tv.project_id=manifest_row.project_id))
  ) THEN
    RAISE EXCEPTION 'Prototype approval Trace manifest does not match approval facts';
  END IF;

  SELECT count(*), min(ordinal), max(ordinal)
    INTO source_count, min_ordinal, max_ordinal
    FROM plm.prt_version_approval_trace_sources
   WHERE approval_trace_manifest_id=manifest_row.approval_trace_manifest_id;
  IF source_count<>manifest_row.declared_trace_link_count
     OR min_ordinal<>1 OR max_ordinal<>source_count THEN
    RAISE EXCEPTION 'Prototype approval Trace manifest source set is incomplete';
  END IF;

  IF (SELECT count(*) FROM plm.prt_version_approval_trace_sources s
       WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
         AND s.source_kind='TEMPLATE_VERSION')<>1
     OR NOT EXISTS (
       SELECT 1 FROM plm.prt_version_approval_trace_sources s
       JOIN plm.prt_template_versions tv
         ON tv.prototype_template_version_id=s.source_version_id
        AND tv.prototype_template_id=s.source_object_id
        AND tv.project_id IS NOT DISTINCT FROM s.source_project_id
        WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
          AND s.source_kind='TEMPLATE_VERSION'
          AND s.source_object_id=manifest_row.template_id
          AND s.source_version_id=manifest_row.template_version_id
     ) THEN
    RAISE EXCEPTION 'Prototype approval Trace template source is incomplete';
  END IF;

  IF EXISTS (
      SELECT 1 FROM plm.prt_version_artifact_refs a
       WHERE a.prototype_version_id=manifest_row.prototype_version_id
         AND a.artifact_kind<>'DOCUMENT_VERSION'
     ) OR
     (SELECT count(*) FROM plm.prt_version_approval_trace_sources s
       WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
         AND s.source_kind='DOCUMENT_VERSION')<>manifest_row.declared_artifact_count
     OR EXISTS (
       SELECT 1 FROM plm.prt_version_artifact_refs a
        WHERE a.prototype_version_id=manifest_row.prototype_version_id
          AND NOT EXISTS (
            SELECT 1 FROM plm.prt_version_approval_trace_sources s
            JOIN plm.doc_document_versions dv
              ON dv.document_version_id=s.source_version_id
             AND dv.document_id=s.source_object_id
             AND dv.project_id IS NOT DISTINCT FROM s.source_project_id
             WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
               AND s.source_kind='DOCUMENT_VERSION'
               AND s.source_version_id=a.target_id
               AND (dv.scope='GLOBAL' OR
                    (dv.scope='PROJECT' AND dv.project_id=manifest_row.project_id))
          )
     ) OR EXISTS (
       SELECT 1 FROM plm.prt_version_approval_trace_sources s
        WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
          AND s.source_kind='DOCUMENT_VERSION'
          AND NOT EXISTS (
            SELECT 1 FROM plm.prt_version_artifact_refs a
             WHERE a.prototype_version_id=manifest_row.prototype_version_id
               AND a.artifact_kind='DOCUMENT_VERSION'
               AND a.target_id=s.source_version_id
          )
     ) THEN
    RAISE EXCEPTION 'Prototype approval Trace document source set is not exact';
  END IF;

  IF (SELECT count(*) FROM plm.prt_version_approval_trace_sources s
       WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
         AND s.source_kind='REQUIREMENT_VERSION')<>
       manifest_row.declared_requirement_count
     OR EXISTS (
       SELECT 1 FROM plm.prt_version_requirement_refs q
        WHERE q.prototype_version_id=manifest_row.prototype_version_id
          AND NOT EXISTS (
            SELECT 1 FROM plm.prt_version_approval_trace_sources s
             WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
               AND s.source_kind='REQUIREMENT_VERSION'
               AND s.source_object_id=q.requirement_id
               AND s.source_version_id=q.requirement_version_id
               AND s.source_project_id=manifest_row.project_id
          )
     ) OR EXISTS (
       SELECT 1 FROM plm.prt_version_approval_trace_sources s
        WHERE s.approval_trace_manifest_id=manifest_row.approval_trace_manifest_id
          AND s.source_kind='REQUIREMENT_VERSION'
          AND NOT EXISTS (
            SELECT 1 FROM plm.prt_version_requirement_refs q
             WHERE q.prototype_version_id=manifest_row.prototype_version_id
               AND q.requirement_id=s.source_object_id
               AND q.requirement_version_id=s.source_version_id
               AND q.project_id=s.source_project_id
          )
     ) THEN
    RAISE EXCEPTION 'Prototype approval Trace requirement source set is not exact';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_prototype_approval_trace_manifest()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.event_type='APPROVED' AND NOT EXISTS (
    SELECT 1 FROM plm.prt_version_approval_trace_manifests m
     WHERE m.review_state_result_id=NEW.review_state_result_id
       AND m.prototype_version_id=NEW.prototype_version_id
       AND m.prototype_id=NEW.prototype_id AND m.project_id=NEW.project_id
       AND m.review_id=NEW.review_id AND m.review_round_id=NEW.review_round_id
       AND m.approved_by=NEW.actor_id
  ) THEN
    RAISE EXCEPTION 'Prototype approval has no Trace manifest';
  ELSIF NEW.event_type<>'APPROVED' AND EXISTS (
    SELECT 1 FROM plm.prt_version_approval_trace_manifests m
     WHERE m.review_state_result_id=NEW.review_state_result_id
  ) THEN
    RAISE EXCEPTION 'Prototype nonapproval cannot own a Trace manifest';
  END IF;
  RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_prototype_approval_trace_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'Prototype approval Trace history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "prt_version_approval_trace_manifests",
        sa.Column("approval_trace_manifest_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("review_state_result_id", ident, nullable=False),
        sa.Column("review_id", ident, nullable=False),
        sa.Column("review_round_id", ident, nullable=False),
        sa.Column("template_id", ident, nullable=False),
        sa.Column("template_version_id", ident, nullable=False),
        sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("declared_artifact_count", sa.Integer(), nullable=False),
        sa.Column("declared_requirement_count", sa.Integer(), nullable=False),
        sa.Column("declared_trace_link_count", sa.Integer(), nullable=False),
        sa.Column("approved_by", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "approval_trace_manifest_id", "prototype_version_id", "prototype_id",
            "project_id", name="uq_prt_approval_manifests__identity_version"),
        sa.UniqueConstraint("prototype_version_id",
                            name="uq_prt_approval_manifests__version"),
        sa.UniqueConstraint("review_state_result_id",
                            name="uq_prt_approval_manifests__review_result"),
        sa.ForeignKeyConstraint(
            ["prototype_version_id", "prototype_id", "project_id"],
            ["plm.prt_prototype_versions.prototype_version_id",
             "plm.prt_prototype_versions.prototype_id",
             "plm.prt_prototype_versions.project_id"],
            name="fk_prt_approval_manifests__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["review_state_result_id"],
            ["plm.prt_version_review_state_results.review_state_result_id"],
            name="fk_prt_approval_manifests__review_result", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_prt_approval_manifests__review",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_round_id"],
                                ["plm.rvw_review_rounds.review_round_id"],
                                name="fk_prt_approval_manifests__round",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["template_version_id", "template_id"],
            ["plm.prt_template_versions.prototype_template_version_id",
             "plm.prt_template_versions.prototype_template_id"],
            name="fk_prt_approval_manifests__template_version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["approved_by"], ["plm.auth_users.user_id"],
                                name="fk_prt_approval_manifests__approver",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("octet_length(content_fingerprint)=32",
                           name="ck_prt_approval_manifests__fingerprint"),
        sa.CheckConstraint(
            "declared_artifact_count BETWEEN 1 AND 100 AND "
            "declared_requirement_count BETWEEN 1 AND 200 AND "
            "declared_trace_link_count="
            "declared_artifact_count+declared_requirement_count+1",
            name="ck_prt_approval_manifests__counts"),
        schema="plm")
    op.create_index("ix_prt_approval_manifests__review_round",
                    "prt_version_approval_trace_manifests",
                    ["review_id", "review_round_id"], schema="plm")

    op.create_table(
        "prt_version_approval_trace_sources",
        sa.Column("approval_trace_source_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("approval_trace_manifest_id", ident, nullable=False),
        sa.Column("prototype_version_id", ident, nullable=False),
        sa.Column("prototype_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_owner_module", sa.Text(), nullable=False),
        sa.Column("source_object_type", sa.Text(), nullable=False),
        sa.Column("source_object_id", ident, nullable=False),
        sa.Column("source_version_id", ident, nullable=False),
        sa.Column("source_project_id", ident),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("trace_link_id", ident, nullable=False),
        sa.UniqueConstraint("approval_trace_manifest_id", "ordinal",
                            name="uq_prt_approval_sources__manifest_ordinal"),
        sa.UniqueConstraint("approval_trace_manifest_id", "source_kind",
                            "source_version_id",
                            name="uq_prt_approval_sources__manifest_source"),
        sa.UniqueConstraint("trace_link_id",
                            name="uq_prt_approval_sources__trace_link"),
        sa.ForeignKeyConstraint(
            ["approval_trace_manifest_id", "prototype_version_id", "prototype_id",
             "project_id"],
            ["plm.prt_version_approval_trace_manifests.approval_trace_manifest_id",
             "plm.prt_version_approval_trace_manifests.prototype_version_id",
             "plm.prt_version_approval_trace_manifests.prototype_id",
             "plm.prt_version_approval_trace_manifests.project_id"],
            name="fk_prt_approval_sources__manifest", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["trace_link_id"], ["plm.trc_links.trace_link_id"],
                                name="fk_prt_approval_sources__trace_link",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal>0", name="ck_prt_approval_sources__ordinal"),
        sa.CheckConstraint(
            "(source_kind='TEMPLATE_VERSION' AND source_owner_module='prototype' "
            "AND source_object_type='PRT-04' AND relation_type='DERIVED_FROM') OR "
            "(source_kind='DOCUMENT_VERSION' AND source_owner_module='document' "
            "AND source_object_type='DOC-02' AND relation_type='DERIVED_FROM') OR "
            "(source_kind='REQUIREMENT_VERSION' AND source_owner_module='requirement' "
            "AND source_object_type='REQ-03' AND relation_type='IMPLEMENTS')",
            name="ck_prt_approval_sources__shape"),
        schema="plm")
    op.create_index("ix_prt_approval_sources__source",
                    "prt_version_approval_trace_sources",
                    ["source_owner_module", "source_object_type", "source_version_id",
                     "prototype_version_id"], schema="plm")

    op.execute(sa.text(_GUARDS))
    for table in (
        "prt_version_approval_trace_manifests",
        "prt_version_approval_trace_sources",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}__immutable BEFORE INSERT OR UPDATE OR DELETE "
            f"ON plm.{table} FOR EACH ROW "
            "EXECUTE FUNCTION plm.guard_prototype_approval_trace_history()")
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT "
            "EXECUTE FUNCTION plm.reject_prototype_approval_trace_truncate()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_approval_manifests__closure "
        "AFTER INSERT ON plm.prt_version_approval_trace_manifests "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_prototype_approval_trace_closure()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_prt_review_results__approval_trace_closure "
        "AFTER INSERT ON plm.prt_version_review_state_results "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.enforce_prototype_approval_trace_manifest()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Prototype approval Trace downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.prt_version_approval_trace_manifests, "
        "plm.prt_version_approval_trace_sources IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.prt_version_approval_trace_manifests) "
        "OR EXISTS (SELECT 1 FROM plm.prt_version_approval_trace_sources)"
    )).scalar_one():
        raise RuntimeError("Prototype approval Trace history prevents downgrade")
    op.execute(
        "DROP TRIGGER trg_prt_review_results__approval_trace_closure "
        "ON plm.prt_version_review_state_results")
    op.execute(
        "DROP TRIGGER trg_prt_approval_manifests__closure "
        "ON plm.prt_version_approval_trace_manifests")
    for table in (
        "prt_version_approval_trace_sources",
        "prt_version_approval_trace_manifests",
    ):
        op.execute(f"DROP TRIGGER trg_{table}__immutable ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.drop_index("ix_prt_approval_sources__source",
                  table_name="prt_version_approval_trace_sources", schema="plm")
    op.drop_table("prt_version_approval_trace_sources", schema="plm")
    op.drop_index("ix_prt_approval_manifests__review_round",
                  table_name="prt_version_approval_trace_manifests", schema="plm")
    op.drop_table("prt_version_approval_trace_manifests", schema="plm")
    for function in (
        "assert_prototype_approval_trace_closure",
        "enforce_prototype_approval_trace_manifest",
        "guard_prototype_approval_trace_history",
        "reject_prototype_approval_trace_truncate",
    ):
        op.execute(f"DROP FUNCTION plm.{function}()")
