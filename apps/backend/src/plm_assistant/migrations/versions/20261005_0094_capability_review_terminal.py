"""Atomically formalize terminal Capability Review outcomes.

Revision ID: 20261005_0094
Revises: 20261005_0093
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa


revision = "20261005_0094"
down_revision = "20261005_0093"
branch_labels = None
depends_on = None


_TERMINAL_OWNER_GUARD = r"""
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
       OR NOT (
         (OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
          AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
          AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
         OR
         (OLD.version_state='IN_REVIEW'
          AND NEW.version_state IN ('APPROVED','RETURNED')
          AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
         OR
         (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
          AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
       ) THEN
      RAISE EXCEPTION 'Capability BaselineVersion update is outside Review Owner';
    END IF;
  ELSE
    RAISE EXCEPTION 'Capability version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


_TERMINAL_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_capability_terminal()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  baseline_row plm.cap_baselines%ROWTYPE;
  version_row plm.cap_baseline_versions%ROWTYPE;
  review_row plm.rvw_reviews%ROWTYPE;
  round_row plm.rvw_review_rounds%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='cap_baselines' THEN
    baseline_row := NEW;
  ELSE
    SELECT * INTO baseline_row FROM plm.cap_baselines
     WHERE baseline_id=NEW.baseline_id FOR SHARE;
  END IF;
  IF baseline_row.baseline_id IS NULL THEN
    RAISE EXCEPTION 'Capability terminal baseline is missing';
  END IF;
  IF baseline_row.current_approved_version_ref IS NOT NULL THEN
    SELECT * INTO version_row FROM plm.cap_baseline_versions
     WHERE baseline_version_id=baseline_row.current_approved_version_ref
       AND baseline_id=baseline_row.baseline_id FOR SHARE;
    IF version_row.baseline_version_id IS NULL
       OR version_row.version_state<>'APPROVED' THEN
      RAISE EXCEPTION 'Capability approved pointer is invalid';
    END IF;
  END IF;
  IF TG_TABLE_NAME='cap_baselines' THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state IN ('DRAFT','IN_REVIEW') THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state='SUPERSEDED' THEN
    IF baseline_row.current_approved_version_ref IS NULL
       OR baseline_row.current_approved_version_ref=NEW.baseline_version_id
       OR version_row.version_no<=NEW.version_no THEN
      RAISE EXCEPTION 'Capability superseded version is invalid';
    END IF;
    RETURN NULL;
  END IF;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_ref FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_ref FOR SHARE;
  IF review_row.review_id IS NULL OR review_row.scope<>'GLOBAL'
     OR review_row.project_id IS NOT NULL OR review_row.subject_type<>'CAP-01'
     OR review_row.subject_id<>NEW.baseline_id
     OR review_row.active_round_id IS NOT NULL
     OR round_row.review_round_id IS NULL
     OR round_row.review_id<>NEW.review_ref
     OR round_row.subject_version_id<>NEW.baseline_version_id
     OR round_row.scope<>'GLOBAL' OR round_row.project_id IS NOT NULL
     OR review_row.review_state<>round_row.round_state THEN
    RAISE EXCEPTION 'Capability terminal Review binding is invalid';
  END IF;
  IF NEW.version_state='APPROVED' THEN
    IF review_row.review_state<>'APPROVED'
       OR baseline_row.current_approved_version_ref<>NEW.baseline_version_id THEN
      RAISE EXCEPTION 'Capability approval formalization is incomplete';
    END IF;
  ELSIF NEW.version_state='RETURNED' THEN
    IF review_row.review_state NOT IN ('RETURNED','WITHDRAWN')
       OR baseline_row.current_approved_version_ref=NEW.baseline_version_id THEN
      RAISE EXCEPTION 'Capability nonapproval formalization is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Capability terminal state is invalid';
  END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    op.execute(_TERMINAL_OWNER_GUARD)
    op.create_index(
        "uq_cap_versions__baseline_approved", "cap_baseline_versions",
        ["baseline_id"], unique=True, schema="plm",
        postgresql_where=sa.text("version_state='APPROVED'"),
    )
    op.execute(_TERMINAL_INTEGRITY)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_cap_baselines__terminal
        AFTER UPDATE ON plm.cap_baselines
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.validate_capability_terminal()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_cap_versions__terminal
        AFTER UPDATE ON plm.cap_baseline_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.validate_capability_terminal()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Capability terminal downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.cap_baselines, plm.cap_baseline_versions, "
        "plm.rvw_reviews, plm.rvw_review_rounds IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.cap_baselines
             WHERE current_approved_version_ref IS NOT NULL
          ) OR EXISTS (
            SELECT 1 FROM plm.cap_baseline_versions
             WHERE version_state IN ('APPROVED','RETURNED','SUPERSEDED')
          ) THEN
            RAISE EXCEPTION 'Capability terminal history prevents downgrade';
          END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER trg_cap_versions__terminal ON plm.cap_baseline_versions")
    op.execute("DROP TRIGGER trg_cap_baselines__terminal ON plm.cap_baselines")
    op.execute("DROP FUNCTION plm.validate_capability_terminal()")
    op.drop_index(
        "uq_cap_versions__baseline_approved",
        table_name="cap_baseline_versions", schema="plm",
    )
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261005_0093_capability_review_start"
    )
    op.execute(previous._REVIEW_START_GUARD)
