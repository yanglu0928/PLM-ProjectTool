"""CR-AUD-002 internal Audit file ownership; ordinary documents stay isolated."""
from alembic import context, op
import sqlalchemy as sa

revision = "20260926_0040"
down_revision = "20260926_0039"
branch_labels = None
depends_on = None

SCOPE = "(scope IN ('GLOBAL','DEPLOYMENT') AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)"
USAGE = """(usage_kind='DOCUMENT' AND owner_object_id IS NULL AND scope IN ('GLOBAL','PROJECT'))
 OR (usage_kind='AUDIT_EXPORT' AND owner_object_id IS NOT NULL
 AND owner_object_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND scope IN ('DEPLOYMENT','PROJECT') AND storage_class='PERSISTENT'
 AND sha256 IS NOT NULL AND size_bytes IS NOT NULL AND size_bytes BETWEEN 0 AND 134217728
 AND detected_mime IS NOT NULL AND detected_mime='application/x-ndjson'
 AND isfinite(created_at)
 AND (available_at IS NULL OR (isfinite(available_at) AND file_state IN ('AVAILABLE','RESTRICTED'))))"""


def upgrade():
    op.add_column("doc_file_objects", sa.Column("usage_kind", sa.Text(), nullable=False,
                  server_default=sa.text("'DOCUMENT'")), schema="plm")
    op.add_column("doc_file_objects", sa.Column("owner_object_id", sa.UUID()), schema="plm")
    op.drop_constraint("ck_doc_file_objects__scope_project", "doc_file_objects", schema="plm", type_="check")
    op.create_check_constraint("ck_doc_file_objects__scope_project", "doc_file_objects", SCOPE, schema="plm")
    op.create_check_constraint("ck_doc_file_objects__usage", "doc_file_objects", USAGE, schema="plm")
    op.execute("""
    CREATE FUNCTION plm.guard_internal_audit_file() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='TRUNCATE' THEN
        IF EXISTS(SELECT 1 FROM plm.doc_file_objects WHERE usage_kind='AUDIT_EXPORT') THEN
          RAISE EXCEPTION 'Audit file history cannot be truncated';
        END IF;
        RETURN NULL;
      ELSIF TG_OP='DELETE' THEN
        IF OLD.usage_kind='AUDIT_EXPORT' THEN RAISE EXCEPTION 'Audit file history cannot be deleted'; END IF;
        RETURN OLD;
      ELSIF TG_OP='INSERT' THEN
        IF NEW.usage_kind='AUDIT_EXPORT' AND (NEW.file_state<>'STAGED' OR NEW.available_at IS NOT NULL OR NEW.lock_version<>0) THEN
          RAISE EXCEPTION 'Audit file initial state invalid';
        END IF;
      ELSE
        IF (NEW.usage_kind,NEW.owner_object_id) IS DISTINCT FROM (OLD.usage_kind,OLD.owner_object_id) THEN
          RAISE EXCEPTION 'File usage identity is immutable';
        END IF;
        IF OLD.usage_kind='AUDIT_EXPORT' THEN
          IF (NEW.file_object_id,NEW.scope,NEW.project_id,NEW.storage_class,NEW.storage_locator,
              NEW.sha256,NEW.size_bytes,NEW.detected_mime,NEW.original_name_metadata,NEW.created_by,NEW.created_at)
             IS DISTINCT FROM
             (OLD.file_object_id,OLD.scope,OLD.project_id,OLD.storage_class,OLD.storage_locator,
              OLD.sha256,OLD.size_bytes,OLD.detected_mime,OLD.original_name_metadata,OLD.created_by,OLD.created_at)
             OR (OLD.available_at IS NOT NULL AND NEW.available_at IS DISTINCT FROM OLD.available_at) THEN
            RAISE EXCEPTION 'Audit file content identity is immutable';
          END IF;
          IF NEW.file_state IS DISTINCT FROM OLD.file_state THEN
            IF NOT ((OLD.file_state='STAGED' AND NEW.file_state IN ('AVAILABLE','FAILED'))
                 OR (OLD.file_state='AVAILABLE' AND NEW.file_state='RESTRICTED')
                 OR (OLD.file_state='FAILED' AND NEW.file_state='CLEANUP_PENDING')
                 OR (OLD.file_state='CLEANUP_PENDING' AND NEW.file_state='REMOVED'))
                 OR NEW.lock_version<>OLD.lock_version+1 THEN
              RAISE EXCEPTION 'Audit file transition invalid';
            END IF;
          ELSIF NEW.lock_version IS DISTINCT FROM OLD.lock_version THEN
            RAISE EXCEPTION 'Audit file version without transition';
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER trg_doc_files_internal_audit BEFORE INSERT OR UPDATE OR DELETE ON plm.doc_file_objects
      FOR EACH ROW EXECUTE FUNCTION plm.guard_internal_audit_file();
    CREATE TRIGGER trg_doc_files_internal_audit_truncate BEFORE TRUNCATE ON plm.doc_file_objects
      FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_internal_audit_file();

    CREATE FUNCTION plm.require_document_file_usage() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE f plm.doc_file_objects%ROWTYPE;
    BEGIN
      IF NEW.file_object_id IS NOT NULL THEN
        SELECT * INTO f FROM plm.doc_file_objects WHERE file_object_id=NEW.file_object_id FOR SHARE;
        IF NOT FOUND OR f.usage_kind<>'DOCUMENT' OR f.owner_object_id IS NOT NULL THEN
          RAISE EXCEPTION 'Document cannot bind internal Audit file';
        END IF;
      END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER trg_doc_versions_file_usage BEFORE INSERT OR UPDATE ON plm.doc_document_versions
      FOR EACH ROW EXECUTE FUNCTION plm.require_document_file_usage();
    CREATE TRIGGER trg_doc_uploads_file_usage BEFORE INSERT OR UPDATE ON plm.doc_upload_intents
      FOR EACH ROW EXECUTE FUNCTION plm.require_document_file_usage();
    """)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("offline Audit file ownership downgrade disabled")
    op.execute("LOCK TABLE plm.doc_documents, plm.doc_upload_intents, plm.doc_document_versions, plm.doc_file_objects IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.doc_file_objects WHERE usage_kind<>'DOCUMENT' OR owner_object_id IS NOT NULL OR scope='DEPLOYMENT')")):
        raise RuntimeError("Audit file history exists; downgrade refused")
    op.execute("""
      DROP TRIGGER trg_doc_versions_file_usage ON plm.doc_document_versions;
      DROP TRIGGER trg_doc_uploads_file_usage ON plm.doc_upload_intents;
      DROP FUNCTION plm.require_document_file_usage();
      DROP TRIGGER trg_doc_files_internal_audit ON plm.doc_file_objects;
      DROP TRIGGER trg_doc_files_internal_audit_truncate ON plm.doc_file_objects;
      DROP FUNCTION plm.guard_internal_audit_file();
    """)
    op.drop_constraint("ck_doc_file_objects__usage", "doc_file_objects", schema="plm", type_="check")
    op.drop_constraint("ck_doc_file_objects__scope_project", "doc_file_objects", schema="plm", type_="check")
    op.create_check_constraint("ck_doc_file_objects__scope_project", "doc_file_objects",
        "(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)", schema="plm")
    op.drop_column("doc_file_objects", "owner_object_id", schema="plm")
    op.drop_column("doc_file_objects", "usage_kind", schema="plm")
