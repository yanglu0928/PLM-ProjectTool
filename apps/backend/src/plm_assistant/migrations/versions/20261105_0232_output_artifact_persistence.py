"""Add closed OUT-02 OutputArtifact persistence foundations."""
from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261105_0232"
down_revision = "20261105_0231"
branch_labels = None
depends_on = None


_WRITE_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_output_artifact_owner_write()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'out_artifacts' THEN
    IF current_setting('plm.output_artifact_owner_write', true) = 'on' THEN
      IF TG_OP = 'INSERT' THEN
        RETURN NEW;
      END IF;
      IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.project_id, NEW.output_request_id, NEW.plugin_execution_id,
               NEW.document_id, NEW.document_version_id, NEW.file_object_id,
               NEW.document_category, NEW.scope, NEW.artifact_kind, NEW.media_type,
               NEW.artifact_sha256, NEW.size_bytes, NEW.created_at)
           IS NOT DISTINCT FROM
           ROW(OLD.project_id, OLD.output_request_id, OLD.plugin_execution_id,
               OLD.document_id, OLD.document_version_id, OLD.file_object_id,
               OLD.document_category, OLD.scope, OLD.artifact_kind, OLD.media_type,
               OLD.artifact_sha256, OLD.size_bytes, OLD.created_at)
        THEN
          RETURN NEW;
        END IF;
        RAISE EXCEPTION 'OutputArtifact content is immutable';
      END IF;
    END IF;
    RAISE EXCEPTION 'OutputArtifact persistence is owner controlled and append only';
  ELSIF TG_TABLE_NAME = 'out_artifact_validation_results' THEN
    IF current_setting('plm.output_artifact_owner_write', true) = 'on'
       AND TG_OP = 'INSERT'
    THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'OutputArtifact validation history is append only';
  END IF;
  RAISE EXCEPTION 'OutputArtifact persistence guard rejected an unknown relation';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_output_artifact_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'OutputArtifact history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    ts = postgresql.TIMESTAMP(timezone=True, precision=6)

    # Candidate keys exist only to support frozen cross-root composite references.
    op.create_unique_constraint(
        "uq_out_output_requests__id_project_type", "out_output_requests",
        ["output_request_id", "project_id", "output_type"], schema="plm")
    op.create_unique_constraint(
        "uq_plg_executions__id_request_project", "plg_executions",
        ["plugin_execution_id", "output_request_id", "project_id"], schema="plm")
    op.create_unique_constraint(
        "uq_doc_documents__artifact_category_scope", "doc_documents",
        ["document_id", "document_category", "scope", "project_id"], schema="plm")
    op.create_unique_constraint(
        "uq_doc_versions__artifact_content", "doc_document_versions",
        ["document_version_id", "document_id", "scope", "project_id",
         "file_object_id", "content_sha256", "size_bytes", "detected_mime"],
        schema="plm")
    op.create_unique_constraint(
        "uq_doc_file_objects__artifact_content", "doc_file_objects",
        ["file_object_id", "scope", "project_id", "sha256", "size_bytes",
         "detected_mime"], schema="plm")

    op.create_table(
        "out_artifacts",
        sa.Column("output_artifact_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("output_request_id", ident, nullable=False),
        sa.Column("plugin_execution_id", ident, nullable=False),
        sa.Column("document_id", ident, nullable=False),
        sa.Column("document_version_id", ident, nullable=False),
        sa.Column("file_object_id", ident, nullable=False),
        sa.Column("document_category", sa.Text(), nullable=False,
                  server_default=sa.text("'GENERATED_ARTIFACT'")),
        sa.Column("scope", sa.Text(), nullable=False,
                  server_default=sa.text("'PROJECT'")),
        sa.Column("artifact_kind", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("artifact_state", sa.Text(), nullable=False,
                  server_default=sa.text("'VALIDATING'")),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", ts, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("published_at", ts),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("output_artifact_id", "project_id",
                            name="uq_out_artifacts__id_project"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_out_artifacts__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["output_request_id", "project_id", "artifact_kind"],
            ["plm.out_output_requests.output_request_id",
             "plm.out_output_requests.project_id", "plm.out_output_requests.output_type"],
            name="fk_out_artifacts__request_kind_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["plugin_execution_id", "output_request_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id",
             "plm.plg_executions.output_request_id", "plm.plg_executions.project_id"],
            name="fk_out_artifacts__execution_request_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_id", "document_category", "scope", "project_id"],
            ["plm.doc_documents.document_id", "plm.doc_documents.document_category",
             "plm.doc_documents.scope", "plm.doc_documents.project_id"],
            name="fk_out_artifacts__generated_document_project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "document_id", "scope", "project_id",
             "file_object_id", "artifact_sha256", "size_bytes", "media_type"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id", "plm.doc_document_versions.scope",
             "plm.doc_document_versions.project_id", "plm.doc_document_versions.file_object_id",
             "plm.doc_document_versions.content_sha256", "plm.doc_document_versions.size_bytes",
             "plm.doc_document_versions.detected_mime"],
            name="fk_out_artifacts__document_version_content", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["file_object_id", "scope", "project_id", "artifact_sha256",
             "size_bytes", "media_type"],
            ["plm.doc_file_objects.file_object_id", "plm.doc_file_objects.scope",
             "plm.doc_file_objects.project_id", "plm.doc_file_objects.sha256",
             "plm.doc_file_objects.size_bytes", "plm.doc_file_objects.detected_mime"],
            name="fk_out_artifacts__file_content_project", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "scope='PROJECT' AND document_category='GENERATED_ARTIFACT'",
            name="ck_out_artifacts__project_generated_document"),
        sa.CheckConstraint(
            "artifact_kind IN ('DOCX','PPTX','PNG','JPEG')",
            name="ck_out_artifacts__kind"),
        sa.CheckConstraint(
            "(artifact_kind='DOCX' AND media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document') OR "
            "(artifact_kind='PPTX' AND media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation') OR "
            "(artifact_kind='PNG' AND media_type='image/png') OR "
            "(artifact_kind='JPEG' AND media_type='image/jpeg')",
            name="ck_out_artifacts__kind_media_type"),
        sa.CheckConstraint(
            "artifact_state IN ('VALIDATING','AVAILABLE','RESTRICTED','REVOKED')",
            name="ck_out_artifacts__state"),
        sa.CheckConstraint(
            "(artifact_state='VALIDATING' AND published_at IS NULL) OR "
            "(artifact_state='AVAILABLE' AND published_at IS NOT NULL) OR "
            "artifact_state IN ('RESTRICTED','REVOKED')",
            name="ck_out_artifacts__publish_time"),
        sa.CheckConstraint(
            "artifact_state <> 'AVAILABLE' OR "
            "(validation_summary->>'format_code'='PASSED' "
            "AND validation_summary->>'structure_code'='PASSED' "
            "AND validation_summary->>'hash_code'='PASSED' "
            "AND validation_summary->>'content_code'='PASSED')",
            name="ck_out_artifacts__available_validated",
        ),
        sa.CheckConstraint("octet_length(artifact_sha256)=32",
                           name="ck_out_artifacts__sha256"),
        sa.CheckConstraint("size_bytes BETWEEN 0 AND 134217728",
                           name="ck_out_artifacts__size"),
        sa.CheckConstraint(
            "jsonb_typeof(validation_summary)='object' "
            "AND validation_summary - ARRAY['format_code','structure_code','hash_code','content_code'] = '{}'::jsonb "
            "AND (NOT (validation_summary ? 'format_code') OR validation_summary->>'format_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'structure_code') OR validation_summary->>'structure_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'hash_code') OR validation_summary->>'hash_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'content_code') OR validation_summary->>'content_code' ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_out_artifacts__validation_summary_codes"),
        sa.CheckConstraint(
            "lock_version >= 0 AND isfinite(created_at) "
            "AND (published_at IS NULL OR isfinite(published_at))",
            name="ck_out_artifacts__time_lock"),
        schema="plm",
    )
    op.create_index(
        "ix_out_artifacts__project_state_created", "out_artifacts",
        ["project_id", "artifact_state", "created_at", "output_artifact_id"],
        schema="plm")
    op.create_table(
        "out_artifact_validation_results",
        sa.Column("validation_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("output_artifact_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("validation_code", sa.Text(), nullable=False),
        sa.Column("validation_state", sa.Text(), nullable=False),
        sa.Column("evidence_fingerprint", sa.LargeBinary()),
        sa.Column("checked_at", ts, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["output_artifact_id", "project_id"],
            ["plm.out_artifacts.output_artifact_id", "plm.out_artifacts.project_id"],
            name="fk_out_artifact_validation__artifact_project", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "validation_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="ck_out_artifact_validation__code"),
        sa.CheckConstraint(
            "validation_state IN ('PASSED','FAILED','WARNING')",
            name="ck_out_artifact_validation__state"),
        sa.CheckConstraint(
            "evidence_fingerprint IS NULL OR octet_length(evidence_fingerprint)=32",
            name="ck_out_artifact_validation__fingerprint"),
        sa.CheckConstraint("isfinite(checked_at)",
                           name="ck_out_artifact_validation__checked_at"),
        schema="plm",
    )
    op.create_index(
        "ix_out_artifact_validation__artifact_time",
        "out_artifact_validation_results",
        ["output_artifact_id", "project_id", "checked_at", "validation_result_id"],
        schema="plm")
    op.execute(_WRITE_GUARD)
    for table in ("out_artifacts", "out_artifact_validation_results"):
        op.execute(f"""
        CREATE TRIGGER trg_{table}__owner_write
        BEFORE INSERT OR UPDATE OR DELETE ON plm.{table}
        FOR EACH ROW EXECUTE FUNCTION plm.guard_output_artifact_owner_write()
        """)
        op.execute(f"""
        CREATE TRIGGER trg_{table}__no_truncate
        BEFORE TRUNCATE ON plm.{table}
        FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_output_artifact_truncate()
        """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline OutputArtifact downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.out_artifacts) "
        "OR EXISTS (SELECT 1 FROM plm.out_artifact_validation_results)"
    )).scalar_one():
        raise RuntimeError("OutputArtifact history blocks downgrade")
    for table in ("out_artifacts", "out_artifact_validation_results"):
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__owner_write ON plm.{table}")
    op.execute("DROP FUNCTION plm.reject_output_artifact_truncate()")
    op.execute("DROP FUNCTION plm.guard_output_artifact_owner_write()")
    op.drop_index("ix_out_artifact_validation__artifact_time",
                  table_name="out_artifact_validation_results", schema="plm")
    op.drop_table("out_artifact_validation_results", schema="plm")
    op.drop_index("ix_out_artifacts__project_state_created",
                  table_name="out_artifacts", schema="plm")
    op.drop_table("out_artifacts", schema="plm")
    for name, table in (
        ("uq_doc_file_objects__artifact_content", "doc_file_objects"),
        ("uq_doc_versions__artifact_content", "doc_document_versions"),
        ("uq_doc_documents__artifact_category_scope", "doc_documents"),
        ("uq_plg_executions__id_request_project", "plg_executions"),
        ("uq_out_output_requests__id_project_type", "out_output_requests"),
    ):
        op.drop_constraint(name, table, schema="plm", type_="unique")
