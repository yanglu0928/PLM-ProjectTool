"""Enable the Handover DRAFT Version owner transition.

Revision ID: 20261005_0097
Revises: 20261005_0096
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261005_0097"
down_revision = "20261005_0096"
branch_labels = None
depends_on = None


_OWNER_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_analysis_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Handover Analysis history cannot be deleted';
  END IF;
  IF TG_OP='UPDATE' THEN
    IF TG_TABLE_NAME='hnd_analyses'
       AND NEW.handover_analysis_id=OLD.handover_analysis_id
       AND NEW.project_id=OLD.project_id
       AND NEW.analysis_purpose=OLD.analysis_purpose
       AND NEW.source_set_ref=OLD.source_set_ref
       AND NEW.analysis_state=OLD.analysis_state
       AND NEW.analysis_state='ACTIVE'
       AND NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref
       AND NEW.current_approved_version_ref IS NULL
       AND NEW.created_by=OLD.created_by
       AND NEW.created_at=OLD.created_at
       AND NEW.updated_by IS NOT NULL
       AND NEW.updated_at>=OLD.updated_at
       AND NEW.lock_version=OLD.lock_version+1 THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Handover Analysis Owner transition is invalid';
  END IF;
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
END; $$;
"""

_CLOSED_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_handover_analysis_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Handover Analysis Owner is not installed';
  END IF;
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
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(_OWNER_GUARD))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade cannot prove absence of Handover Versions")
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.hnd_analysis_versions)"
    )).scalar_one():
        raise RuntimeError(
            "Handover Version history prevents downgrade; restore backup or migrate forward"
        )
    op.execute(sa.text(_CLOSED_GUARD))
