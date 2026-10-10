"""Open atomic Reference revision while preserving immutable history.

Revision ID: 20261009_0150
Revises: 20261009_0149
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0150"
down_revision = "20261009_0149"
branch_labels = None
depends_on = None


_OPEN = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_no integer;
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF TG_TABLE_NAME = 'sol_reference_versions' THEN
      IF NEW.version_no = 1 THEN
        IF NEW.supersedes_version_ref IS NOT NULL THEN
          RAISE EXCEPTION 'initial Reference version cannot supersede'; END IF;
      ELSE
        SELECT version_no INTO prior_no FROM plm.sol_reference_versions
         WHERE reference_version_id=NEW.supersedes_version_ref
           AND reference_solution_id=NEW.reference_solution_id AND scope=NEW.scope;
        IF prior_no IS NULL OR NEW.version_no<>prior_no+1 THEN
          RAISE EXCEPTION 'Reference revision predecessor mismatch'; END IF;
      END IF;
    END IF;
    RETURN NEW;
  ELSIF TG_TABLE_NAME='sol_reference_solutions' AND TG_OP='UPDATE' THEN
    IF to_jsonb(NEW)-'current_version_ref'-'lock_version'
       <> to_jsonb(OLD)-'current_version_ref'-'lock_version'
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.current_version_ref IS NULL
       OR NEW.current_version_ref IS NOT DISTINCT FROM OLD.current_version_ref
       OR NOT EXISTS (
         SELECT 1 FROM plm.sol_reference_versions v
          JOIN plm.sol_reference_versions p
            ON p.reference_version_id=OLD.current_version_ref
           AND p.reference_solution_id=OLD.reference_solution_id
           AND p.scope=OLD.scope
          WHERE v.reference_version_id=NEW.current_version_ref
            AND v.reference_solution_id=OLD.reference_solution_id
            AND v.scope=OLD.scope AND v.project_id IS NOT DISTINCT FROM OLD.project_id
            AND v.supersedes_version_ref=p.reference_version_id
            AND v.version_no=p.version_no+1
       ) THEN RAISE EXCEPTION 'Reference revision pointer mismatch'; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;

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

CREATE FUNCTION plm.assert_solution_reference_revise_closure()
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

_CLOSED = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' THEN
    IF TG_TABLE_NAME='sol_reference_versions' THEN
      IF NEW.version_no>1 THEN
        RAISE EXCEPTION 'ReferenceSolution revise Owner is not installed'; END IF;
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_revise_result_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReferenceSolution revise result Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    # 0149 can contain legacy v2 rows inserted before that revision. Their
    # original 201 response cannot be reconstructed, so refuse silent repair.
    op.execute(sa.text(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM plm.sol_reference_versions "
        "WHERE version_no>1) OR EXISTS "
        "(SELECT 1 FROM plm.sol_reference_revise_results) THEN "
        "RAISE EXCEPTION 'legacy Reference revisions require audited forward repair'; "
        "END IF; END $$"
    ))
    op.execute(_OPEN)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_reference_versions__revise_closure "
        "AFTER INSERT ON plm.sol_reference_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW WHEN (NEW.version_no > 1) "
        "EXECUTE FUNCTION plm.assert_solution_reference_revise_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference revision Owner downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_reference_versions WHERE version_no>1) "
        "OR EXISTS (SELECT 1 FROM plm.sol_reference_revise_results)"
    )).scalar_one():
        raise RuntimeError("Reference revision history prevents Owner downgrade")
    op.execute("DROP TRIGGER trg_sol_reference_versions__revise_closure "
               "ON plm.sol_reference_versions")
    op.execute("DROP FUNCTION plm.assert_solution_reference_revise_closure()")
    op.execute(_CLOSED)
