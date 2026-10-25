"""CR-EVD-002: retain fixed ParseRecord identity without rewriting old evidence."""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20261001_0052"
down_revision = "20260930_0051"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("evd_evidence_records", sa.Column("source_parse_record_id", UUID(as_uuid=True)), schema="plm")
    op.create_foreign_key("fk_evd_evidence__source_parse", "evd_evidence_records", "doc_parse_records",
                          ["source_parse_record_id"], ["parse_record_id"], source_schema="plm",
                          referent_schema="plm", ondelete="NO ACTION")
    op.execute("""
    CREATE FUNCTION plm.guard_evidence_parse_source() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.locator_type='DOCUMENT' THEN
          IF NEW.source_parse_record_id IS NOT NULL THEN
            RAISE EXCEPTION 'Document Evidence has no ParseRecord source';
          END IF;
        ELSE
          IF NEW.source_parse_record_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM plm.doc_parse_records p
            WHERE p.parse_record_id=NEW.source_parse_record_id
              AND p.document_version_id=NEW.document_version_id
              AND p.scope=NEW.scope AND p.project_id IS NOT DISTINCT FROM NEW.project_id
              AND p.parse_state='SUCCEEDED'
          ) THEN RAISE EXCEPTION 'Evidence ParseRecord source invalid'; END IF;
          IF NEW.locator_type='STRUCTURED_NODE' AND
             (NEW.locator_payload->>'parse_record_id') IS DISTINCT FROM NEW.source_parse_record_id::text THEN
            RAISE EXCEPTION 'Structured Evidence ParseRecord mismatch';
          END IF;
        END IF;
      ELSIF TG_OP='UPDATE' AND NEW.source_parse_record_id IS DISTINCT FROM OLD.source_parse_record_id THEN
        RAISE EXCEPTION 'Evidence ParseRecord source is immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_evd_evidence_parse_source
      BEFORE INSERT OR UPDATE ON plm.evd_evidence_records
      FOR EACH ROW EXECUTE FUNCTION plm.guard_evidence_parse_source();
    """)


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("offline Evidence provenance downgrade is disabled")
    op.execute("""
    LOCK TABLE plm.evd_evidence_records IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM plm.evd_evidence_records WHERE source_parse_record_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot discard fixed Evidence ParseRecord history';
      END IF;
    END $$;
    DROP TRIGGER trg_evd_evidence_parse_source ON plm.evd_evidence_records;
    DROP FUNCTION plm.guard_evidence_parse_source();
    """)
    op.drop_constraint("fk_evd_evidence__source_parse", "evd_evidence_records", schema="plm", type_="foreignkey")
    op.drop_column("evd_evidence_records", "source_parse_record_id", schema="plm")
