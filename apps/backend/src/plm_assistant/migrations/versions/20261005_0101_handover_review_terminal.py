"""Open only the Handover Review start and terminal Owner transitions.

Revision ID: 20261005_0101
Revises: 20261005_0100
"""

from __future__ import annotations

import importlib

from alembic import context, op
import sqlalchemy as sa


revision = "20261005_0101"
down_revision = "20261005_0100"
branch_labels = None
depends_on = None


_REVIEW_OWNER_GUARD = r"""
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
    ELSIF TG_TABLE_NAME='hnd_analysis_items'
       AND NEW.item_state<>'CANDIDATE' THEN
      RAISE EXCEPTION 'Handover AnalysisItem initial state is invalid';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME='hnd_analyses' THEN
    IF NEW.handover_analysis_id IS DISTINCT FROM OLD.handover_analysis_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.analysis_purpose IS DISTINCT FROM OLD.analysis_purpose
       OR NEW.source_set_ref IS DISTINCT FROM OLD.source_set_ref
       OR NEW.analysis_state IS DISTINCT FROM OLD.analysis_state
       OR NEW.analysis_state<>'ACTIVE'
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.updated_by IS NULL OR NEW.updated_at<OLD.updated_at
       OR NEW.lock_version<>OLD.lock_version+1
       OR (OLD.current_approved_version_ref IS NOT NULL
           AND NEW.current_approved_version_ref IS NULL) THEN
      RAISE EXCEPTION 'Handover Analysis update is outside active Owner';
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


_REVIEW_START_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_handover_review_start()
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
     OR review_row.subject_type<>'HND-02'
     OR review_row.subject_id IS DISTINCT FROM NEW.handover_analysis_id
     OR review_row.review_state<>'IN_REVIEW'
     OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_ref
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'PROJECT'
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM
        NEW.handover_analysis_version_id
     OR round_row.round_state<>'IN_REVIEW' THEN
    RAISE EXCEPTION 'Handover Review start binding is incomplete or mismatched';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_items i
        WHERE i.handover_analysis_version_id=
              NEW.handover_analysis_version_id
          AND (i.source_missing OR i.item_type='NEED_CONFIRM')
          AND NOT EXISTS (
              SELECT 1 FROM plm.hnd_action_items a
               WHERE a.project_id=NEW.project_id
                 AND a.source_kind='ANALYSIS_ITEM'
                 AND a.source_analysis_version_ref=
                     NEW.handover_analysis_version_id
                 AND a.source_item_id=i.analysis_item_id
                 AND a.action_state<>'CANCELLED')) THEN
    RAISE EXCEPTION 'Handover Review requires active Action coverage';
  END IF;
  IF EXISTS (
       SELECT 1 FROM plm.hnd_analysis_items i
        WHERE i.handover_analysis_version_id=
              NEW.handover_analysis_version_id
          AND i.item_state<>'CANDIDATE') THEN
    RAISE EXCEPTION 'Handover Review start requires candidate items';
  END IF;
  RETURN NULL;
END; $$;
"""


_TERMINAL_INTEGRITY = r"""
CREATE OR REPLACE FUNCTION plm.validate_handover_review_terminal()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  analysis_row plm.hnd_analyses%ROWTYPE;
  version_row plm.hnd_analysis_versions%ROWTYPE;
  approved_row plm.hnd_analysis_versions%ROWTYPE;
  review_row plm.rvw_reviews%ROWTYPE;
  round_row plm.rvw_review_rounds%ROWTYPE;
BEGIN
  IF TG_TABLE_NAME='hnd_analyses' THEN
    analysis_row := NEW;
  ELSIF TG_TABLE_NAME='hnd_analysis_versions' THEN
    SELECT * INTO analysis_row FROM plm.hnd_analyses
     WHERE handover_analysis_id=NEW.handover_analysis_id
       AND project_id=NEW.project_id FOR SHARE;
  ELSE
    SELECT * INTO version_row FROM plm.hnd_analysis_versions
     WHERE handover_analysis_version_id=NEW.handover_analysis_version_id
       AND handover_analysis_id=NEW.handover_analysis_id
       AND project_id=NEW.project_id FOR SHARE;
    SELECT * INTO analysis_row FROM plm.hnd_analyses
     WHERE handover_analysis_id=NEW.handover_analysis_id
       AND project_id=NEW.project_id FOR SHARE;
  END IF;
  IF analysis_row.handover_analysis_id IS NULL THEN
    RAISE EXCEPTION 'Handover Review analysis is missing';
  END IF;
  IF analysis_row.current_approved_version_ref IS NOT NULL THEN
    SELECT * INTO approved_row FROM plm.hnd_analysis_versions
     WHERE handover_analysis_version_id=
           analysis_row.current_approved_version_ref
       AND handover_analysis_id=analysis_row.handover_analysis_id
       AND project_id=analysis_row.project_id FOR SHARE;
    IF approved_row.handover_analysis_version_id IS NULL
       OR approved_row.version_state<>'APPROVED' THEN
      RAISE EXCEPTION 'Handover approved pointer is invalid';
    END IF;
  END IF;
  IF TG_TABLE_NAME='hnd_analyses' THEN
    RETURN NULL;
  END IF;
  IF TG_TABLE_NAME='hnd_analysis_items' THEN
    IF NEW.item_state='CONFIRMED'
       AND version_row.version_state<>'APPROVED' THEN
      RAISE EXCEPTION 'Handover confirmed item requires approved version';
    END IF;
    RETURN NULL;
  END IF;
  IF NEW.version_state IN ('DRAFT','IN_REVIEW') THEN
    RETURN NULL;
  END IF;
  IF NEW.version_state='SUPERSEDED' THEN
    IF approved_row.handover_analysis_version_id IS NULL
       OR approved_row.handover_analysis_version_id=
          NEW.handover_analysis_version_id
       OR approved_row.version_no<=NEW.version_no THEN
      RAISE EXCEPTION 'Handover superseded version is invalid';
    END IF;
    RETURN NULL;
  END IF;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_ref FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_ref FOR SHARE;
  IF review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'HND-02'
     OR review_row.subject_id IS DISTINCT FROM NEW.handover_analysis_id
     OR review_row.active_round_id IS NOT NULL
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_ref
     OR round_row.scope<>'PROJECT'
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM
        NEW.handover_analysis_version_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'Handover terminal Review binding is invalid';
  END IF;
  IF NEW.version_state='APPROVED' THEN
    IF review_row.review_state<>'APPROVED'
       OR analysis_row.current_approved_version_ref IS DISTINCT FROM
          NEW.handover_analysis_version_id
       OR EXISTS (
          SELECT 1 FROM plm.hnd_analysis_items i
           WHERE i.handover_analysis_version_id=
                 NEW.handover_analysis_version_id
             AND i.item_state<>'CONFIRMED')
       OR EXISTS (
          SELECT 1 FROM plm.hnd_analysis_items i
           WHERE i.handover_analysis_version_id=
                 NEW.handover_analysis_version_id
             AND (i.source_missing OR i.item_type='NEED_CONFIRM')
             AND NOT EXISTS (
                 SELECT 1 FROM plm.hnd_action_items a
                  WHERE a.project_id=NEW.project_id
                    AND a.source_kind='ANALYSIS_ITEM'
                    AND a.source_analysis_version_ref=
                        NEW.handover_analysis_version_id
                    AND a.source_item_id=i.analysis_item_id
                    AND a.action_state<>'CANCELLED')) THEN
      RAISE EXCEPTION 'Handover approval formalization is incomplete';
    END IF;
  ELSIF NEW.version_state='RETURNED' THEN
    IF review_row.review_state NOT IN ('RETURNED','WITHDRAWN')
       OR analysis_row.current_approved_version_ref IS NOT DISTINCT FROM
          NEW.handover_analysis_version_id
       OR EXISTS (
          SELECT 1 FROM plm.hnd_analysis_items i
           WHERE i.handover_analysis_version_id=
                 NEW.handover_analysis_version_id
             AND i.item_state<>'CANDIDATE') THEN
      RAISE EXCEPTION 'Handover nonapproval formalization is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Handover terminal version state is invalid';
  END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    op.execute(_REVIEW_OWNER_GUARD)
    op.execute(_REVIEW_START_INTEGRITY)
    op.execute(_TERMINAL_INTEGRITY)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_hnd_versions__review_start
        AFTER UPDATE ON plm.hnd_analysis_versions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.validate_handover_review_start()
    """)
    for table in (
        "hnd_analyses", "hnd_analysis_versions", "hnd_analysis_items",
    ):
        op.execute(sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_{table}__review_terminal "
            f"AFTER UPDATE ON plm.{table} "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
            "EXECUTE FUNCTION plm.validate_handover_review_terminal()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Handover Review downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.hnd_analyses, plm.hnd_analysis_versions, "
        "plm.hnd_analysis_items, plm.rvw_reviews, plm.rvw_review_rounds, "
        "plm.hnd_action_items IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.hnd_analyses
             WHERE current_approved_version_ref IS NOT NULL
          ) OR EXISTS (
            SELECT 1 FROM plm.hnd_analysis_versions
             WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL
                OR review_round_ref IS NOT NULL
          ) OR EXISTS (
            SELECT 1 FROM plm.hnd_analysis_items
             WHERE item_state<>'CANDIDATE'
          ) THEN
            RAISE EXCEPTION 'Handover Review history prevents downgrade';
          END IF;
        END $$;
    """)
    for table in reversed((
        "hnd_analyses", "hnd_analysis_versions", "hnd_analysis_items",
    )):
        op.execute(sa.text(
            f"DROP TRIGGER trg_{table}__review_terminal ON plm.{table}"
        ))
    op.execute(
        "DROP TRIGGER trg_hnd_versions__review_start "
        "ON plm.hnd_analysis_versions"
    )
    op.execute("DROP FUNCTION plm.validate_handover_review_terminal()")
    op.execute("DROP FUNCTION plm.validate_handover_review_start()")
    previous = importlib.import_module(
        "plm_assistant.migrations.versions.20261005_0097_handover_version_owner"
    )
    op.execute(previous._OWNER_GUARD)
