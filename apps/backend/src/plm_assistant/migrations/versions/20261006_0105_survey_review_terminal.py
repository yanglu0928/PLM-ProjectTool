"""Open only the Survey Review start and terminal Owner transitions.

Revision ID: 20261006_0105
Revises: 20261006_0104
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa


revision = "20261006_0105"
down_revision = "20261006_0104"
branch_labels = None
depends_on = None


_REVIEW_OWNER_GUARD = r"""
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
       OR NEW.name IS DISTINCT FROM OLD.name
       OR NEW.survey_state IS DISTINCT FROM OLD.survey_state
       OR NEW.survey_state<>'ACTIVE'
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1
       OR (OLD.current_approved_version_ref IS NOT NULL
           AND NEW.current_approved_version_ref IS NULL) THEN
      RAISE EXCEPTION 'Survey update is outside active Owner';
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


_REVIEW_START_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_survey_review_start()
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
  IF review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'SRV-02'
     OR review_row.subject_id IS DISTINCT FROM NEW.survey_id
     OR review_row.policy_code<>'SURVEY_ALL_V1'
     OR review_row.review_state<>'IN_REVIEW'
     OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_ref
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'PROJECT'
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.survey_version_id
     OR round_row.round_state<>'IN_REVIEW' THEN
    RAISE EXCEPTION 'Survey Review start binding is incomplete or mismatched';
  END IF;
  RETURN NULL;
END; $$;
"""


_TERMINAL_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_survey_review_terminal()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  survey_row plm.srv_surveys%ROWTYPE;
  approved_row plm.srv_survey_versions%ROWTYPE;
  review_row plm.rvw_reviews%ROWTYPE;
  round_row plm.rvw_review_rounds%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='srv_surveys' THEN
    survey_row := NEW;
  ELSE
    SELECT * INTO survey_row FROM plm.srv_surveys
     WHERE survey_id=NEW.survey_id AND project_id=NEW.project_id FOR SHARE;
  END IF;
  IF survey_row.survey_id IS NULL THEN
    RAISE EXCEPTION 'Survey Review definition is missing';
  END IF;
  IF survey_row.current_approved_version_ref IS NOT NULL THEN
    SELECT * INTO approved_row FROM plm.srv_survey_versions
     WHERE survey_version_id=survey_row.current_approved_version_ref
       AND survey_id=survey_row.survey_id
       AND project_id=survey_row.project_id FOR SHARE;
    IF approved_row.survey_version_id IS NULL
       OR approved_row.version_state<>'APPROVED' THEN
      RAISE EXCEPTION 'Survey approved pointer is invalid';
    END IF;
  END IF;
  IF TG_TABLE_NAME='srv_surveys' THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state IN ('DRAFT','IN_REVIEW') THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state='SUPERSEDED' THEN
    IF approved_row.survey_version_id IS NULL
       OR approved_row.survey_version_id=NEW.survey_version_id
       OR approved_row.version_no<=NEW.version_no THEN
      RAISE EXCEPTION 'Survey superseded version is invalid';
    END IF;
    RETURN NULL;
  END IF;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_ref FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_ref FOR SHARE;
  IF review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'SRV-02'
     OR review_row.subject_id IS DISTINCT FROM NEW.survey_id
     OR review_row.policy_code<>'SURVEY_ALL_V1'
     OR review_row.active_round_id IS NOT NULL
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'PROJECT'
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.survey_version_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'Survey terminal Review binding is invalid';
  END IF;
  IF NEW.version_state='APPROVED' THEN
    IF review_row.review_state<>'APPROVED'
       OR survey_row.current_approved_version_ref IS DISTINCT FROM NEW.survey_version_id THEN
      RAISE EXCEPTION 'Survey approval formalization is incomplete';
    END IF;
  ELSIF NEW.version_state='RETURNED' THEN
    IF review_row.review_state NOT IN ('RETURNED','WITHDRAWN')
       OR survey_row.current_approved_version_ref IS NOT DISTINCT FROM NEW.survey_version_id THEN
      RAISE EXCEPTION 'Survey nonapproval formalization is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Survey terminal version state is invalid';
  END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(_REVIEW_OWNER_GUARD))
    op.execute(sa.text(_REVIEW_START_INTEGRITY))
    op.execute(sa.text(_TERMINAL_INTEGRITY))
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_srv_versions__review_start
        AFTER UPDATE ON plm.srv_survey_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.validate_survey_review_start()
    """)
    for table in ("srv_surveys", "srv_survey_versions"):
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__review_terminal "
            f"AFTER UPDATE ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION plm.validate_survey_review_terminal()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Survey Review downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.srv_surveys, plm.srv_survey_versions, "
        "plm.rvw_reviews, plm.rvw_review_rounds IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.srv_surveys
             WHERE current_approved_version_ref IS NOT NULL
          ) OR EXISTS (
            SELECT 1 FROM plm.srv_survey_versions
             WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL
                OR review_round_ref IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'Survey Review history prevents downgrade';
          END IF;
        END $$;
    """)
    for table in reversed(("srv_surveys", "srv_survey_versions")):
        op.execute(sa.text(
            f"DROP TRIGGER trg_{table}__review_terminal ON plm.{table}"
        ))
    op.execute(
        "DROP TRIGGER trg_srv_versions__review_start ON plm.srv_survey_versions"
    )
    op.execute("DROP FUNCTION plm.validate_survey_review_terminal()")
    op.execute("DROP FUNCTION plm.validate_survey_review_start()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261006_0104_survey_version_owner"
    )
    op.execute(sa.text(previous._OWNER_GUARD))
