"""Open only the Capability DRAFT to IN_REVIEW Subject binding.

Revision ID: 20261005_0093
Revises: 20261005_0092
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa


revision = "20261005_0093"
down_revision = "20261005_0092"
branch_labels = None
depends_on = None


_REVIEW_START_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_capability_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Capability history is immutable';
  END IF;
  IF TG_TABLE_NAME='cap_baselines' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.baseline_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 THEN
        RAISE EXCEPTION 'CapabilityBaseline initial state is invalid';
      END IF;
    ELSIF NEW.baseline_id IS DISTINCT FROM OLD.baseline_id
       OR NEW.baseline_code IS DISTINCT FROM OLD.baseline_code
       OR NEW.name IS DISTINCT FROM OLD.name
       OR NEW.description IS DISTINCT FROM OLD.description
       OR NEW.baseline_state IS DISTINCT FROM OLD.baseline_state
       OR NEW.source_collection_ref IS DISTINCT FROM OLD.source_collection_ref
       OR NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL
       OR NEW.updated_at < OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1 THEN
      RAISE EXCEPTION 'CapabilityBaseline update is outside active Owner';
    END IF;
  ELSIF TG_TABLE_NAME='cap_baseline_versions' THEN
    IF TG_OP='INSERT' THEN
      IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
         OR NEW.review_round_ref IS NOT NULL THEN
        RAISE EXCEPTION 'Capability BaselineVersion initial state is invalid';
      END IF;
    ELSIF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
          IS DISTINCT FROM
          (to_jsonb(OLD)-ARRAY['version_state','review_ref','review_round_ref'])
       OR OLD.version_state<>'DRAFT' OR NEW.version_state<>'IN_REVIEW'
       OR OLD.review_ref IS NOT NULL OR OLD.review_round_ref IS NOT NULL
       OR NEW.review_ref IS NULL OR NEW.review_round_ref IS NULL THEN
      RAISE EXCEPTION 'Capability BaselineVersion update is outside Review start Owner';
    END IF;
  ELSE
    RAISE EXCEPTION 'Capability version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


_REVIEW_BINDING = r"""
CREATE OR REPLACE FUNCTION plm.validate_capability_review_start()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  review_row plm.rvw_reviews%ROWTYPE;
  round_row plm.rvw_review_rounds%ROWTYPE;
BEGIN
  IF NEW.version_state<>'IN_REVIEW' THEN
    RETURN NULL;
  END IF;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_ref FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_ref FOR SHARE;
  IF review_row.review_id IS NULL OR review_row.scope<>'GLOBAL'
     OR review_row.project_id IS NOT NULL OR review_row.subject_type<>'CAP-01'
     OR review_row.subject_id IS DISTINCT FROM NEW.baseline_id
     OR review_row.review_state<>'IN_REVIEW'
     OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_ref
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'GLOBAL' OR round_row.project_id IS NOT NULL
     OR round_row.subject_version_id IS DISTINCT FROM NEW.baseline_version_id
     OR round_row.round_state<>'IN_REVIEW' THEN
    RAISE EXCEPTION 'Capability Review binding is incomplete or mismatched';
  END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    op.execute(_REVIEW_START_GUARD)
    op.create_index(
        "uq_cap_versions__baseline_in_review", "cap_baseline_versions",
        ["baseline_id"], unique=True, schema="plm",
        postgresql_where=sa.text("version_state='IN_REVIEW'"),
    )
    op.execute(_REVIEW_BINDING)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_cap_versions__review_start
        AFTER UPDATE ON plm.cap_baseline_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.validate_capability_review_start()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Capability Review start downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.cap_baselines, plm.cap_baseline_versions, "
        "plm.rvw_reviews, plm.rvw_review_rounds IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.cap_baseline_versions
             WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL
                OR review_round_ref IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'Capability Review history prevents downgrade';
          END IF;
        END $$;
    """)
    op.execute(
        "DROP TRIGGER trg_cap_versions__review_start "
        "ON plm.cap_baseline_versions"
    )
    op.execute("DROP FUNCTION plm.validate_capability_review_start()")
    op.drop_index(
        "uq_cap_versions__baseline_in_review",
        table_name="cap_baseline_versions", schema="plm",
    )
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261005_0092_capability_version_owner"
    )
    op.execute(previous._VERSION_OWNER_GUARD)
