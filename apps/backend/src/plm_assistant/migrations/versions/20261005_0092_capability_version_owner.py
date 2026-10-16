"""Open only the Baseline lock bump required by Draft Version creation.

Revision ID: 20261005_0092
Revises: 20261005_0091
"""

from __future__ import annotations

from alembic import context, op


revision = "20261005_0092"
down_revision = "20261005_0091"
branch_labels = None
depends_on = None


_VERSION_OWNER_GUARD = r"""
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
      RAISE EXCEPTION 'CapabilityBaseline update is outside Draft Version Owner';
    END IF;
  ELSIF TG_TABLE_NAME='cap_baseline_versions' THEN
    IF TG_OP<>'INSERT' THEN
      RAISE EXCEPTION 'Capability BaselineVersion is immutable';
    END IF;
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'Capability BaselineVersion initial state is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Capability version content is immutable';
  END IF;
  RETURN NEW;
END; $$;
"""


_FOUNDATION_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_capability_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' OR TG_OP='UPDATE' THEN
    RAISE EXCEPTION 'Capability Owner is not installed';
  END IF;
  IF TG_TABLE_NAME='cap_baselines' THEN
    IF NEW.baseline_state<>'ACTIVE' OR NEW.current_approved_version_ref IS NOT NULL
       OR NEW.lock_version<>0 THEN
      RAISE EXCEPTION 'CapabilityBaseline initial state is invalid';
    END IF;
  ELSIF TG_TABLE_NAME='cap_baseline_versions' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'Capability BaselineVersion initial state is invalid';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    op.execute(_VERSION_OWNER_GUARD)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Capability Version Owner downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.cap_baselines, plm.cap_baseline_versions "
        "IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM plm.cap_baselines
             WHERE lock_version<>0 OR updated_by IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'Capability history prevents downgrade';
          END IF;
        END $$;
    """)
    op.execute(_FOUNDATION_GUARD)
