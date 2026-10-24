"""Open Survey metadata and archive Owner transitions.

Revision ID: 20261006_0106
Revises: 20261006_0105
"""

from __future__ import annotations

import importlib

from alembic import context, op


revision = "20261006_0106"
down_revision = "20261006_0105"
branch_labels = None
depends_on = None


_STATE_OWNER_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_definition_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Survey definition history cannot be deleted';
  END IF;
  IF TG_OP='INSERT' THEN
    IF TG_TABLE_NAME='srv_surveys' THEN
      IF NEW.survey_state<>'ACTIVE'
         OR NEW.current_approved_version_ref IS NOT NULL
         OR NEW.lock_version<>0 THEN
        RAISE EXCEPTION 'Survey initial state is invalid';
      END IF;
    ELSIF TG_TABLE_NAME='srv_survey_versions' THEN
      IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
         OR NEW.review_round_ref IS NOT NULL THEN
        RAISE EXCEPTION 'SurveyVersion initial state is invalid';
      END IF;
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME='srv_surveys' THEN
    IF NEW.survey_id IS DISTINCT FROM OLD.survey_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1 THEN
      RAISE EXCEPTION 'Survey update is outside active Owner';
    END IF;
    IF OLD.survey_state='ACTIVE' AND NEW.survey_state='ACTIVE' THEN
      IF NEW.name IS DISTINCT FROM OLD.name THEN
        IF NEW.current_approved_version_ref IS DISTINCT FROM
             OLD.current_approved_version_ref
           OR EXISTS (
              SELECT 1 FROM plm.srv_survey_versions v
               WHERE v.survey_id=OLD.survey_id
                 AND v.project_id=OLD.project_id
                 AND v.version_state='IN_REVIEW') THEN
          RAISE EXCEPTION 'Survey metadata is under Review';
        END IF;
      ELSIF OLD.current_approved_version_ref IS NOT NULL
            AND NEW.current_approved_version_ref IS NULL THEN
        RAISE EXCEPTION 'Survey approved pointer cannot be cleared';
      END IF;
    ELSIF OLD.survey_state='ACTIVE' AND NEW.survey_state='ARCHIVED' THEN
      IF NEW.name IS DISTINCT FROM OLD.name
         OR NEW.current_approved_version_ref IS DISTINCT FROM
            OLD.current_approved_version_ref
         OR EXISTS (
            SELECT 1 FROM plm.srv_survey_versions v
             WHERE v.survey_id=OLD.survey_id
               AND v.project_id=OLD.project_id
               AND v.version_state='IN_REVIEW') THEN
        RAISE EXCEPTION 'Survey cannot be archived';
      END IF;
    ELSE
      RAISE EXCEPTION 'Survey state transition is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='srv_survey_versions' THEN
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
          AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
          AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref
          AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
         OR
         (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
          AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
          AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref
          AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
       ) THEN
      RAISE EXCEPTION 'SurveyVersion update is outside Review Owner';
    END IF;
  ELSE
    RAISE EXCEPTION 'Survey version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.execute(_STATE_OWNER_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey state-owner downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.srv_surveys, plm.srv_survey_versions, "
        "plm.aud_events IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.srv_surveys WHERE survey_state='ARCHIVED'
          ) OR EXISTS (
            SELECT 1 FROM plm.aud_events
             WHERE target_owner_module='survey'
               AND action IN ('SURVEY_PATCHED','SURVEY_ARCHIVED')
          ) THEN
            RAISE EXCEPTION 'Survey state-owner history prevents downgrade';
          END IF;
        END $$;
    """)
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261006_0105_survey_review_terminal"
    )
    op.execute(previous._REVIEW_OWNER_GUARD)
