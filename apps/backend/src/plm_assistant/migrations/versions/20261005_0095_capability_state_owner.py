"""Open only the frozen Capability metadata/archive/restrict owner paths.

Revision ID: 20261005_0095
Revises: 20261005_0094
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261005_0095"
down_revision = "20261005_0094"
branch_labels = None
depends_on = None


_STATE_OWNER_GUARD = r"""
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
       OR NEW.source_collection_ref IS DISTINCT FROM OLD.source_collection_ref
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL
       OR NEW.updated_at < OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1
       OR NOT (
         (OLD.baseline_state='ACTIVE' AND NEW.baseline_state='ACTIVE'
          AND NEW.current_approved_version_ref
              IS NOT DISTINCT FROM OLD.current_approved_version_ref)
         OR
         (NEW.baseline_state=OLD.baseline_state
          AND NEW.name=OLD.name
          AND NEW.description IS NOT DISTINCT FROM OLD.description
          AND OLD.baseline_state='ACTIVE')
         OR
         (OLD.baseline_state='ACTIVE' AND NEW.baseline_state='ARCHIVED'
          AND NEW.name=OLD.name
          AND NEW.description IS NOT DISTINCT FROM OLD.description
          AND NEW.current_approved_version_ref
              IS NOT DISTINCT FROM OLD.current_approved_version_ref)
       ) THEN
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
         OR
         (OLD.version_state IN ('DRAFT','APPROVED','RETURNED','SUPERSEDED')
          AND NEW.version_state='RESTRICTED'
          AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
          AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
       ) THEN
      RAISE EXCEPTION 'Capability BaselineVersion update is outside active Owner';
    END IF;
  ELSE
    RAISE EXCEPTION 'Capability version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


_STATE_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_capability_terminal()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  baseline_row plm.cap_baselines%ROWTYPE;
  version_row plm.cap_baseline_versions%ROWTYPE;
  approved_id uuid;
  approved_count integer;
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
  SELECT count(*),min(baseline_version_id::text)::uuid
    INTO approved_count,approved_id
    FROM plm.cap_baseline_versions
   WHERE baseline_id=baseline_row.baseline_id
     AND version_state='APPROVED';
  IF approved_count>1
     OR (approved_count=0 AND baseline_row.current_approved_version_ref IS NOT NULL)
     OR (approved_count=1 AND baseline_row.current_approved_version_ref
                              IS DISTINCT FROM approved_id) THEN
    RAISE EXCEPTION 'Capability approved pointer is invalid';
  END IF;
  IF baseline_row.current_approved_version_ref IS NOT NULL THEN
    SELECT * INTO version_row FROM plm.cap_baseline_versions
     WHERE baseline_version_id=baseline_row.current_approved_version_ref
       AND baseline_id=baseline_row.baseline_id FOR SHARE;
  END IF;
  IF TG_TABLE_NAME='cap_baselines' THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state IN ('DRAFT','IN_REVIEW','RESTRICTED') THEN
    IF NEW.version_state='RESTRICTED'
       AND baseline_row.current_approved_version_ref=NEW.baseline_version_id THEN
      RAISE EXCEPTION 'Restricted Capability remains formally approved';
    END IF;
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
    op.execute(_STATE_OWNER_GUARD)
    op.execute(_STATE_INTEGRITY)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Capability state-owner downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.cap_baselines, plm.cap_baseline_versions, "
        "plm.aud_events IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM plm.cap_baselines WHERE baseline_state='ARCHIVED')
             OR EXISTS (SELECT 1 FROM plm.cap_baseline_versions
                         WHERE version_state='RESTRICTED')
             OR EXISTS (SELECT 1 FROM plm.aud_events
                         WHERE target_owner_module='capability'
                           AND action IN ('CAP_BASELINE_PATCHED',
                                          'CAP_BASELINE_ARCHIVED',
                                          'CAP_VERSION_RESTRICTED')) THEN
            RAISE EXCEPTION 'Capability state-owner history prevents downgrade';
          END IF;
        END $$;
    """)
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261005_0094_capability_review_terminal"
    )
    op.execute(previous._TERMINAL_OWNER_GUARD)
    op.execute(previous._TERMINAL_INTEGRITY)
