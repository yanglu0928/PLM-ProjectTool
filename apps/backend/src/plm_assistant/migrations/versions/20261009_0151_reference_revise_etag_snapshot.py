"""Persist the actual root lock version in immutable Reference revise results.

Revision ID: 20261009_0151
Revises: 20261009_0150
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0151"
down_revision = "20261009_0150"
branch_labels = None
depends_on = None


_RESULT_WITH_LOCK = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_revise_result_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND EXISTS (
    SELECT 1 FROM plm.sol_reference_versions v
      JOIN plm.sol_reference_solutions r
        ON r.reference_solution_id=v.reference_solution_id AND r.scope=v.scope
     WHERE v.reference_version_id=NEW.reference_version_id
       AND v.reference_solution_id=NEW.reference_solution_id
       AND v.scope=NEW.scope AND v.version_no=NEW.version_no
       AND v.supersedes_version_ref=NEW.supersedes_version_ref
       AND v.content_fingerprint=NEW.content_fingerprint
       AND v.source_fingerprint=NEW.source_fingerprint
       AND v.created_at=NEW.created_at
       AND r.current_version_ref=NEW.reference_version_id
       AND r.lock_version=NEW.result_lock_version
  ) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Reference revision result mismatch or immutable';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_solution_reference_revise_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions r
      JOIN plm.sol_reference_revise_results x
        ON x.reference_version_id=NEW.reference_version_id
       AND x.reference_solution_id=NEW.reference_solution_id AND x.scope=NEW.scope
     WHERE r.reference_solution_id=NEW.reference_solution_id AND r.scope=NEW.scope
       AND r.project_id IS NOT DISTINCT FROM NEW.project_id
       AND r.current_version_ref=NEW.reference_version_id
       AND r.lock_version=x.result_lock_version
       AND x.version_no=NEW.version_no
       AND x.supersedes_version_ref=NEW.supersedes_version_ref
       AND x.content_fingerprint=NEW.content_fingerprint
       AND x.source_fingerprint=NEW.source_fingerprint
       AND x.created_at=NEW.created_at
  ) OR (SELECT count(*) FROM plm.sol_reference_document_refs d
         WHERE d.reference_version_id=NEW.reference_version_id)
       <>NEW.declared_document_count
     OR (SELECT count(*) FROM plm.sol_reference_evidence_refs e
         WHERE e.reference_version_id=NEW.reference_version_id)
       <>NEW.declared_evidence_count
  THEN RAISE EXCEPTION 'Reference revision transaction is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""

_RESULT_PREVIOUS = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_revise_result_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND EXISTS (
    SELECT 1 FROM plm.sol_reference_versions v
      JOIN plm.sol_reference_solutions r
        ON r.reference_solution_id=v.reference_solution_id AND r.scope=v.scope
     WHERE v.reference_version_id=NEW.reference_version_id
       AND v.reference_solution_id=NEW.reference_solution_id
       AND v.scope=NEW.scope AND v.version_no=NEW.version_no
       AND v.supersedes_version_ref=NEW.supersedes_version_ref
       AND v.content_fingerprint=NEW.content_fingerprint
       AND v.source_fingerprint=NEW.source_fingerprint
       AND v.created_at=NEW.created_at
       AND r.current_version_ref=NEW.reference_version_id
  ) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Reference revision result mismatch or immutable';
END; $$;

CREATE OR REPLACE FUNCTION plm.assert_solution_reference_revise_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions r
      JOIN plm.sol_reference_revise_results x
        ON x.reference_version_id=NEW.reference_version_id
       AND x.reference_solution_id=NEW.reference_solution_id AND x.scope=NEW.scope
     WHERE r.reference_solution_id=NEW.reference_solution_id AND r.scope=NEW.scope
       AND r.project_id IS NOT DISTINCT FROM NEW.project_id
       AND r.current_version_ref=NEW.reference_version_id
       AND x.version_no=NEW.version_no
       AND x.supersedes_version_ref=NEW.supersedes_version_ref
       AND x.content_fingerprint=NEW.content_fingerprint
       AND x.source_fingerprint=NEW.source_fingerprint
       AND x.created_at=NEW.created_at
  ) OR (SELECT count(*) FROM plm.sol_reference_document_refs d
         WHERE d.reference_version_id=NEW.reference_version_id)
       <>NEW.declared_document_count
     OR (SELECT count(*) FROM plm.sol_reference_evidence_refs e
         WHERE e.reference_version_id=NEW.reference_version_id)
       <>NEW.declared_evidence_count
  THEN RAISE EXCEPTION 'Reference revision transaction is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    # Before Eligibility has an Owner, every 0150 revision increments the root
    # exactly once. Refuse unknown/manual history instead of inventing an ETag.
    op.execute(sa.text("""
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions r
      JOIN plm.sol_reference_versions v
        ON v.reference_version_id=r.current_version_ref
     WHERE r.lock_version<>v.version_no-1
  ) THEN RAISE EXCEPTION 'Reference lock history requires audited forward repair';
  END IF;
END $$;
"""))
    op.add_column("sol_reference_revise_results",
                  sa.Column("result_lock_version", sa.BigInteger(), nullable=True),
                  schema="plm")
    # Narrow migration-only backfill; a failed PostgreSQL migration rolls this
    # trigger state back with the surrounding DDL transaction.
    op.execute("ALTER TABLE plm.sol_reference_revise_results "
               "DISABLE TRIGGER trg_sol_reference_revise_results__owner")
    op.execute(sa.text(
        "UPDATE plm.sol_reference_revise_results "
        "SET result_lock_version=version_no-1"
    ))
    op.execute("ALTER TABLE plm.sol_reference_revise_results "
               "ENABLE TRIGGER trg_sol_reference_revise_results__owner")
    op.alter_column("sol_reference_revise_results", "result_lock_version",
                    nullable=False, schema="plm")
    op.create_check_constraint(
        "ck_sol_reference_revise_results__lock", "sol_reference_revise_results",
        "result_lock_version>=1", schema="plm")
    op.execute(_RESULT_WITH_LOCK)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference result lock downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_reference_revise_results)"
    )).scalar_one():
        raise RuntimeError("Reference result lock history prevents downgrade")
    op.execute(_RESULT_PREVIOUS)
    op.drop_constraint("ck_sol_reference_revise_results__lock",
                       "sol_reference_revise_results", schema="plm", type_="check")
    op.drop_column("sol_reference_revise_results", "result_lock_version", schema="plm")
