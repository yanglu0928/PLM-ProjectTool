"""Permit a single, timestamp-only revocation without rewriting confirmation history.

Revision ID: 20261008_0142
Revises: 20261008_0141
"""

from __future__ import annotations

from alembic import op


revision = "20261008_0142"
down_revision = "20261008_0141"
branch_labels = None
depends_on = None

_REVOKE_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_deidentification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.revoked_at IS NOT NULL THEN
      RAISE EXCEPTION 'Reference confirmation cannot be born revoked';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.revoked_at IS NULL AND NEW.revoked_at IS NOT NULL
     AND NEW.revoked_at >= OLD.confirmed_at
     AND ROW(NEW.confirmation_id, NEW.source_fingerprint, NEW.source_project_class,
             NEW.deidentification_class, NEW.applicability, NEW.attestation_statement,
             NEW.confirmed_by, NEW.confirmed_at, NEW.expires_at, NEW.trace_id)
         IS NOT DISTINCT FROM
         ROW(OLD.confirmation_id, OLD.source_fingerprint, OLD.source_project_class,
             OLD.deidentification_class, OLD.applicability, OLD.attestation_statement,
             OLD.confirmed_by, OLD.confirmed_at, OLD.expires_at, OLD.trace_id) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Reference deidentification history is immutable';
END; $$;
"""

_INSERT_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_deidentification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Reference deidentification history is immutable';
END; $$;
"""


def upgrade() -> None:
    op.execute(_REVOKE_OWNER)


def downgrade() -> None:
    # Existing revocation timestamps remain readable and effective after downgrade.
    op.execute(_INSERT_OWNER)
