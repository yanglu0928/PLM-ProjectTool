"""DOC-02 immutable versions, provenance, and guarded Document pointers.

Revision ID: 20260925_0022
Revises: 20260925_0021
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0022"
down_revision = "20260925_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doc_document_versions",
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("version_no", sa.BigInteger(), nullable=False),
        sa.Column("file_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("detected_mime", sa.Text(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("availability_state", sa.Text(), nullable=False,
                  server_default=sa.text("'AVAILABLE'")),
        sa.Column("supersedes_version_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("integrity_checked_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("document_id", "version_no", name="uq_doc_versions__document_no"),
        sa.UniqueConstraint("document_version_id", "document_id",
                            name="uq_doc_versions__id_document"),
        sa.UniqueConstraint("file_object_id", name="uq_doc_versions__file"),
        sa.ForeignKeyConstraint(["document_id"], ["plm.doc_documents.document_id"],
                                name="fk_doc_versions__document", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                                name="fk_doc_versions__file", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_doc_versions__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["supersedes_version_ref", "document_id"],
                                ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"],
                                name="fk_doc_versions__supersedes", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_doc_versions__scope_project"),
        sa.CheckConstraint("version_no > 0", name="ck_doc_versions__number"),
        sa.CheckConstraint("octet_length(content_sha256)=32", name="ck_doc_versions__sha256"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_doc_versions__size"),
        sa.CheckConstraint("char_length(detected_mime) BETWEEN 1 AND 255",
                           name="ck_doc_versions__mime"),
        sa.CheckConstraint("jsonb_typeof(source_metadata)='object'",
                           name="ck_doc_versions__source"),
        sa.CheckConstraint("availability_state IN ('AVAILABLE','RESTRICTED','REVOKED')",
                           name="ck_doc_versions__state"),
        schema="plm",
    )
    op.create_index("ix_doc_versions__document_created", "doc_document_versions",
                    ["document_id", "created_at"], schema="plm")
    op.create_table(
        "doc_version_source_refs",
        sa.Column("source_ref_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_owner_module", sa.Text()),
        sa.Column("source_object_type", sa.Text()),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("document_version_id", "ordinal",
                            name="uq_doc_version_sources__version_ordinal"),
        sa.ForeignKeyConstraint(["document_version_id"],
                                ["plm.doc_document_versions.document_version_id"],
                                name="fk_doc_version_sources__version", ondelete="NO ACTION"),
        sa.CheckConstraint("ordinal >= 0", name="ck_doc_version_sources__ordinal"),
        sa.CheckConstraint("source_kind ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                           name="ck_doc_version_sources__kind"),
        sa.CheckConstraint("(source_owner_module IS NULL AND source_object_type IS NULL AND source_object_id IS NULL AND source_version_id IS NULL) OR (source_owner_module IS NOT NULL AND source_object_type IS NOT NULL AND source_object_id IS NOT NULL)",
                           name="ck_doc_version_sources__ref_shape"),
        sa.CheckConstraint("source_owner_module IS NULL OR source_owner_module ~ '^[a-z][a-z0-9_]{0,39}$'",
                           name="ck_doc_version_sources__owner"),
        sa.CheckConstraint("source_object_type IS NULL OR source_object_type ~ '^[A-Z]{2,3}-[0-9]{2}$'",
                           name="ck_doc_version_sources__object_type"),
        schema="plm",
    )
    op.drop_constraint("ck_doc_documents__pre_version_pointers", "doc_documents",
                       schema="plm", type_="check")
    op.create_foreign_key("fk_doc_documents__latest_version", "doc_documents",
                          "doc_document_versions", ["latest_version_ref", "document_id"],
                          ["document_version_id", "document_id"], source_schema="plm",
                          referent_schema="plm", ondelete="NO ACTION")
    op.create_foreign_key("fk_doc_documents__effective_version", "doc_documents",
                          "doc_document_versions", ["effective_version_ref", "document_id"],
                          ["document_version_id", "document_id"], source_schema="plm",
                          referent_schema="plm", ondelete="NO ACTION")
    op.execute("""
        CREATE FUNCTION plm.validate_document_version_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            d plm.doc_documents%ROWTYPE;
            f plm.doc_file_objects%ROWTYPE;
            previous_id uuid;
            previous_no bigint;
        BEGIN
            SELECT * INTO d FROM plm.doc_documents
             WHERE document_id=NEW.document_id FOR UPDATE;
            IF NOT FOUND OR d.scope IS DISTINCT FROM NEW.scope
               OR d.project_id IS DISTINCT FROM NEW.project_id
               OR d.document_state <> 'ACTIVE' THEN
                RAISE EXCEPTION 'document version scope or state invalid';
            END IF;
            IF NEW.scope='PROJECT' AND NOT EXISTS (
                SELECT 1 FROM plm.prj_projects WHERE project_id=NEW.project_id AND state='ACTIVE'
            ) THEN
                RAISE EXCEPTION 'project is not active';
            END IF;
            SELECT * INTO f FROM plm.doc_file_objects
             WHERE file_object_id=NEW.file_object_id FOR UPDATE;
            IF NOT FOUND OR f.scope IS DISTINCT FROM NEW.scope
               OR f.project_id IS DISTINCT FROM NEW.project_id
               OR f.storage_class <> 'PERSISTENT' OR f.file_state <> 'AVAILABLE'
               OR f.sha256 IS DISTINCT FROM NEW.content_sha256
               OR f.size_bytes IS DISTINCT FROM NEW.size_bytes
               OR f.detected_mime IS DISTINCT FROM NEW.detected_mime
               OR NEW.availability_state <> 'AVAILABLE' THEN
                RAISE EXCEPTION 'document version file snapshot invalid';
            END IF;
            SELECT document_version_id, version_no INTO previous_id, previous_no
              FROM plm.doc_document_versions WHERE document_id=NEW.document_id
             ORDER BY version_no DESC LIMIT 1;
            IF previous_id IS NULL THEN
                IF NEW.version_no <> 1 OR NEW.supersedes_version_ref IS NOT NULL
                   OR d.latest_version_ref IS NOT NULL THEN
                    RAISE EXCEPTION 'first document version sequence invalid';
                END IF;
            ELSIF NEW.version_no <> previous_no + 1
               OR NEW.supersedes_version_ref IS DISTINCT FROM previous_id
               OR d.latest_version_ref IS DISTINCT FROM previous_id THEN
                RAISE EXCEPTION 'document version sequence invalid';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_versions_insert_guard
        BEFORE INSERT ON plm.doc_document_versions
        FOR EACH ROW EXECUTE FUNCTION plm.validate_document_version_insert()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_document_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'document version is retained';
            END IF;
            IF ROW(NEW.document_version_id,NEW.document_id,NEW.scope,NEW.project_id,
                   NEW.version_no,NEW.file_object_id,NEW.content_sha256,NEW.size_bytes,
                   NEW.detected_mime,NEW.source_metadata,NEW.created_by,NEW.created_at,
                   NEW.supersedes_version_ref)
               IS DISTINCT FROM
               ROW(OLD.document_version_id,OLD.document_id,OLD.scope,OLD.project_id,
                   OLD.version_no,OLD.file_object_id,OLD.content_sha256,OLD.size_bytes,
                   OLD.detected_mime,OLD.source_metadata,OLD.created_by,OLD.created_at,
                   OLD.supersedes_version_ref) THEN
                RAISE EXCEPTION 'document version content is immutable';
            END IF;
            IF NEW.availability_state IS DISTINCT FROM OLD.availability_state THEN
                IF NOT ((OLD.availability_state='AVAILABLE' AND NEW.availability_state IN ('RESTRICTED','REVOKED'))
                        OR (OLD.availability_state='RESTRICTED' AND NEW.availability_state='REVOKED')) THEN
                    RAISE EXCEPTION 'document version state transition invalid';
                END IF;
                IF EXISTS (SELECT 1 FROM plm.doc_documents
                            WHERE effective_version_ref=OLD.document_version_id) THEN
                    RAISE EXCEPTION 'effective version must be cleared first';
                END IF;
            END IF;
            IF NEW.integrity_checked_at IS NOT NULL AND OLD.integrity_checked_at IS NOT NULL
               AND NEW.integrity_checked_at < OLD.integrity_checked_at THEN
                RAISE EXCEPTION 'integrity check time cannot regress';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_versions_immutable
        BEFORE UPDATE OR DELETE ON plm.doc_document_versions
        FOR EACH ROW EXECUTE FUNCTION plm.guard_document_version_mutation()
    """)
    op.execute("""
        CREATE FUNCTION plm.validate_document_pointers()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            latest_no bigint;
            effective_state text;
        BEGIN
            IF NEW.effective_version_ref IS NOT NULL AND NEW.latest_version_ref IS NULL THEN
                RAISE EXCEPTION 'effective document version needs latest';
            END IF;
            IF NEW.latest_version_ref IS NULL AND OLD.latest_version_ref IS NOT NULL THEN
                RAISE EXCEPTION 'latest document version cannot be cleared';
            END IF;
            IF NEW.latest_version_ref IS NOT NULL THEN
                SELECT version_no INTO latest_no FROM plm.doc_document_versions
                 WHERE document_version_id=NEW.latest_version_ref
                   AND document_id=NEW.document_id AND scope=NEW.scope
                   AND project_id IS NOT DISTINCT FROM NEW.project_id;
                IF latest_no IS NULL OR latest_no <> (
                    SELECT max(version_no) FROM plm.doc_document_versions
                     WHERE document_id=NEW.document_id
                ) THEN
                    RAISE EXCEPTION 'latest document version pointer invalid';
                END IF;
            END IF;
            IF NEW.effective_version_ref IS NOT NULL THEN
                SELECT availability_state INTO effective_state
                  FROM plm.doc_document_versions
                 WHERE document_version_id=NEW.effective_version_ref
                   AND document_id=NEW.document_id AND scope=NEW.scope
                   AND project_id IS NOT DISTINCT FROM NEW.project_id;
                IF effective_state IS DISTINCT FROM 'AVAILABLE' THEN
                    RAISE EXCEPTION 'effective document version unavailable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_documents_version_pointers
        BEFORE UPDATE ON plm.doc_documents
        FOR EACH ROW EXECUTE FUNCTION plm.validate_document_pointers()
    """)
    op.execute("""
        CREATE FUNCTION plm.reject_document_version_source_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'document version source is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_version_sources_immutable
        BEFORE UPDATE OR DELETE ON plm.doc_version_source_refs
        FOR EACH ROW EXECUTE FUNCTION plm.reject_document_version_source_mutation()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_published_file_metadata()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.file_state IN ('AVAILABLE','RESTRICTED')
               OR EXISTS (SELECT 1 FROM plm.doc_document_versions
                           WHERE file_object_id=OLD.file_object_id) THEN
                IF ROW(NEW.file_object_id,NEW.scope,NEW.project_id,NEW.storage_class,
                       NEW.storage_locator,NEW.original_name_metadata,NEW.sha256,
                       NEW.size_bytes,NEW.detected_mime,NEW.created_by,NEW.created_at)
                   IS DISTINCT FROM
                   ROW(OLD.file_object_id,OLD.scope,OLD.project_id,OLD.storage_class,
                       OLD.storage_locator,OLD.original_name_metadata,OLD.sha256,
                       OLD.size_bytes,OLD.detected_mime,OLD.created_by,OLD.created_at) THEN
                    RAISE EXCEPTION 'published file metadata is immutable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_file_objects_published_immutable
        BEFORE UPDATE ON plm.doc_file_objects
        FOR EACH ROW EXECUTE FUNCTION plm.guard_published_file_metadata()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for DocumentVersion")
    bind = op.get_bind()
    if (bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_document_versions)"))
            or bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_version_source_refs)"))
            or bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_documents WHERE latest_version_ref IS NOT NULL OR effective_version_ref IS NOT NULL)"))):
        raise RuntimeError("DocumentVersion history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_file_objects_published_immutable ON plm.doc_file_objects")
    op.execute("DROP FUNCTION plm.guard_published_file_metadata()")
    op.execute("DROP TRIGGER trg_doc_version_sources_immutable ON plm.doc_version_source_refs")
    op.execute("DROP FUNCTION plm.reject_document_version_source_mutation()")
    op.execute("DROP TRIGGER trg_doc_documents_version_pointers ON plm.doc_documents")
    op.execute("DROP FUNCTION plm.validate_document_pointers()")
    op.execute("DROP TRIGGER trg_doc_versions_immutable ON plm.doc_document_versions")
    op.execute("DROP FUNCTION plm.guard_document_version_mutation()")
    op.execute("DROP TRIGGER trg_doc_versions_insert_guard ON plm.doc_document_versions")
    op.execute("DROP FUNCTION plm.validate_document_version_insert()")
    op.drop_constraint("fk_doc_documents__effective_version", "doc_documents",
                       schema="plm", type_="foreignkey")
    op.drop_constraint("fk_doc_documents__latest_version", "doc_documents",
                       schema="plm", type_="foreignkey")
    op.create_check_constraint("ck_doc_documents__pre_version_pointers", "doc_documents",
                               "latest_version_ref IS NULL AND effective_version_ref IS NULL",
                               schema="plm")
    op.drop_table("doc_version_source_refs", schema="plm")
    op.drop_index("ix_doc_versions__document_created", table_name="doc_document_versions",
                  schema="plm")
    op.drop_table("doc_document_versions", schema="plm")
