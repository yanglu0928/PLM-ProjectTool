"""Enable the Survey DRAFT Version owner transition.

Revision ID: 20261006_0104
Revises: 20261006_0103
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261006_0104"
down_revision = "20261006_0103"
branch_labels = None
depends_on = None


_OWNER_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_definition_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Survey definition history cannot be deleted';
  END IF;
  IF TG_OP='UPDATE' THEN
    IF TG_TABLE_NAME='srv_surveys'
       AND NEW.survey_id=OLD.survey_id AND NEW.project_id=OLD.project_id
       AND NEW.name=OLD.name AND NEW.survey_state=OLD.survey_state
       AND NEW.survey_state='ACTIVE'
       AND NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
       AND NEW.created_by=OLD.created_by AND NEW.created_at=OLD.created_at
       AND NEW.updated_by IS NOT NULL AND NEW.updated_at>=OLD.updated_at
       AND NEW.lock_version=OLD.lock_version+1 THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Survey Owner transition is invalid';
  END IF;
  IF TG_TABLE_NAME='srv_surveys' THEN
    IF NEW.survey_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
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
END; $$;
"""

_CLOSED_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_survey_definition_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Survey definition Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='srv_surveys' THEN
    IF NEW.survey_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN RAISE EXCEPTION 'Survey initial state is invalid'; END IF;
  ELSIF TG_TABLE_NAME='srv_survey_versions' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'SurveyVersion initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(_OWNER_GUARD))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade cannot prove absence of Survey Versions")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.srv_survey_versions)"
    )).scalar_one():
        raise RuntimeError("Survey Version history prevents downgrade")
    op.execute(sa.text(_CLOSED_GUARD))
