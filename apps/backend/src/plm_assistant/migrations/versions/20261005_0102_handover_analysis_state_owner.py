"""Open Handover Analysis metadata and archive Owner transitions.

Revision ID: 20261005_0102
Revises: 20261005_0101
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261005_0102"
down_revision = "20261005_0101"
branch_labels = None
depends_on = None


_STATE_OWNER_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_analysis_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Handover Analysis history cannot be deleted';
  END IF;
  IF TG_OP='INSERT' THEN
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
  END IF;
  IF TG_TABLE_NAME='hnd_analyses' THEN
    IF NEW.handover_analysis_id IS DISTINCT FROM OLD.handover_analysis_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.source_set_ref IS DISTINCT FROM OLD.source_set_ref
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1 THEN
      RAISE EXCEPTION 'Handover Analysis update is outside active Owner';
    END IF;
    IF OLD.analysis_state='ACTIVE' AND NEW.analysis_state='ACTIVE' THEN
      IF NEW.analysis_purpose IS DISTINCT FROM OLD.analysis_purpose THEN
        IF NEW.current_approved_version_ref IS DISTINCT FROM
             OLD.current_approved_version_ref
           OR EXISTS (
              SELECT 1 FROM plm.hnd_analysis_versions v
               WHERE v.handover_analysis_id=OLD.handover_analysis_id
                 AND v.project_id=OLD.project_id
                 AND v.version_state='IN_REVIEW') THEN
          RAISE EXCEPTION 'Handover Analysis metadata is under Review';
        END IF;
      ELSIF OLD.current_approved_version_ref IS NOT NULL
            AND NEW.current_approved_version_ref IS NULL THEN
        RAISE EXCEPTION 'Handover approved pointer cannot be cleared';
      END IF;
    ELSIF OLD.analysis_state='ACTIVE' AND NEW.analysis_state='ARCHIVED' THEN
      IF NEW.analysis_purpose IS DISTINCT FROM OLD.analysis_purpose
         OR NEW.current_approved_version_ref IS DISTINCT FROM
            OLD.current_approved_version_ref
         OR EXISTS (
            SELECT 1 FROM plm.hnd_analysis_versions v
             WHERE v.handover_analysis_id=OLD.handover_analysis_id
               AND v.project_id=OLD.project_id
               AND v.version_state='IN_REVIEW') THEN
        RAISE EXCEPTION 'Handover Analysis cannot be archived';
      END IF;
    ELSE
      RAISE EXCEPTION 'Handover Analysis state transition is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_analysis_versions' THEN
    IF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
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
      RAISE EXCEPTION 'Handover AnalysisVersion update is outside Review Owner';
    END IF;
  ELSIF TG_TABLE_NAME='hnd_analysis_items' THEN
    IF (to_jsonb(NEW)-'item_state') IS DISTINCT FROM
       (to_jsonb(OLD)-'item_state')
       OR OLD.item_state<>'CANDIDATE' OR NEW.item_state<>'CONFIRMED' THEN
      RAISE EXCEPTION 'Handover AnalysisItem update is outside Review Owner';
    END IF;
  ELSE
    RAISE EXCEPTION 'Handover Analysis version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.execute(_STATE_OWNER_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover Analysis state-owner downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.hnd_analyses, plm.hnd_analysis_versions, "
        "plm.aud_events IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.hnd_analyses WHERE analysis_state='ARCHIVED'
          ) OR EXISTS (
            SELECT 1 FROM plm.aud_events
             WHERE target_owner_module='handover'
               AND action IN ('HND_ANALYSIS_PATCHED','HND_ANALYSIS_ARCHIVED')
          ) THEN
            RAISE EXCEPTION 'Handover Analysis state-owner history prevents downgrade';
          END IF;
        END $$;
    """)
    previous = importlib.import_module(
        "plm_assistant.migrations.versions."
        "20261005_0101_handover_review_terminal"
    )
    op.execute(previous._REVIEW_OWNER_GUARD)
