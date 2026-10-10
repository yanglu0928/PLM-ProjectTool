"""Open only event-backed Reference eligibility changes and revision invalidation.

Revision ID: 20261009_0153
Revises: 20261009_0152
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261009_0153"
down_revision = "20261009_0152"
branch_labels = None
depends_on = None

_ROOT_WITH_ELIGIBILITY = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_no integer;
BEGIN
  IF TG_OP='INSERT' THEN
    IF TG_TABLE_NAME='sol_reference_versions' THEN
      IF NEW.version_no=1 THEN
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
    IF NEW.lock_version<>OLD.lock_version+1 THEN
      RAISE EXCEPTION 'Reference root lock mismatch'; END IF;
    IF NEW.current_version_ref IS NOT DISTINCT FROM OLD.current_version_ref THEN
      IF to_jsonb(NEW)-'eligibility_state'-'eligibility_reason'-'lock_version'
         <>to_jsonb(OLD)-'eligibility_state'-'eligibility_reason'-'lock_version'
         OR NEW.eligibility_state=OLD.eligibility_state
         OR NOT EXISTS (
           SELECT 1 FROM plm.sol_reference_eligibility_events e
            WHERE e.reference_solution_id=OLD.reference_solution_id
              AND e.reference_version_id=OLD.current_version_ref
              AND e.scope=OLD.scope
              AND e.project_id IS NOT DISTINCT FROM OLD.project_id
              AND e.event_kind='HUMAN'
              AND e.prior_state=OLD.eligibility_state
              AND e.result_state=NEW.eligibility_state
              AND e.reason=NEW.eligibility_reason
              AND e.prior_lock_version=OLD.lock_version
              AND e.result_lock_version=NEW.lock_version
         ) THEN RAISE EXCEPTION 'Reference eligibility event mismatch'; END IF;
      RETURN NEW;
    END IF;
    IF NEW.current_version_ref IS NULL
       OR to_jsonb(NEW)-'current_version_ref'-'lock_version'-'eligibility_state'-'eligibility_reason'
          <>to_jsonb(OLD)-'current_version_ref'-'lock_version'-'eligibility_state'-'eligibility_reason'
       OR NOT EXISTS (
         SELECT 1 FROM plm.sol_reference_versions v
          JOIN plm.sol_reference_versions p
            ON p.reference_version_id=OLD.current_version_ref
           AND p.reference_solution_id=OLD.reference_solution_id AND p.scope=OLD.scope
          WHERE v.reference_version_id=NEW.current_version_ref
            AND v.reference_solution_id=OLD.reference_solution_id
            AND v.scope=OLD.scope AND v.project_id IS NOT DISTINCT FROM OLD.project_id
            AND v.supersedes_version_ref=p.reference_version_id
            AND v.version_no=p.version_no+1
       ) THEN RAISE EXCEPTION 'Reference revision pointer mismatch'; END IF;
    IF OLD.eligibility_state='ELIGIBLE' THEN
      IF NEW.eligibility_state<>'RESTRICTED'
         OR NEW.eligibility_reason<>'CURRENT_VERSION_CHANGED_REQUIRES_REVIEW'
         OR NOT EXISTS (
           SELECT 1 FROM plm.sol_reference_eligibility_events e
            WHERE e.reference_solution_id=OLD.reference_solution_id
              AND e.reference_version_id=NEW.current_version_ref
              AND e.scope=OLD.scope
              AND e.project_id IS NOT DISTINCT FROM OLD.project_id
              AND e.event_kind='SYSTEM_INVALIDATION'
              AND e.prior_state='ELIGIBLE' AND e.result_state='RESTRICTED'
              AND e.reason=NEW.eligibility_reason
              AND e.prior_lock_version=OLD.lock_version
              AND e.result_lock_version=NEW.lock_version
         ) THEN RAISE EXCEPTION 'Reference revision eligibility invalidation missing'; END IF;
    ELSIF NEW.eligibility_state IS DISTINCT FROM OLD.eligibility_state
       OR NEW.eligibility_reason IS DISTINCT FROM OLD.eligibility_reason THEN
      RAISE EXCEPTION 'Reference revision cannot change eligibility';
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ReferenceSolution history is immutable';
END; $$;
"""

_EVENT_OWNER = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_eligibility_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='INSERT' AND EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions r
      JOIN plm.sol_reference_versions v
        ON v.reference_version_id=NEW.reference_version_id
       AND v.reference_solution_id=NEW.reference_solution_id
       AND v.scope=NEW.scope AND v.project_id IS NOT DISTINCT FROM NEW.project_id
     WHERE r.reference_solution_id=NEW.reference_solution_id
       AND r.scope=NEW.scope AND r.project_id IS NOT DISTINCT FROM NEW.project_id
       AND r.eligibility_state=NEW.prior_state
       AND r.lock_version=NEW.prior_lock_version
       AND ((NEW.event_kind='HUMAN' AND r.current_version_ref=NEW.reference_version_id)
         OR (NEW.event_kind='SYSTEM_INVALIDATION'
             AND v.supersedes_version_ref=r.current_version_ref))
  ) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'Reference eligibility event prior state mismatch or immutable';
END; $$;

CREATE FUNCTION plm.assert_solution_reference_eligibility_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions r
     WHERE r.reference_solution_id=NEW.reference_solution_id
       AND r.scope=NEW.scope AND r.project_id IS NOT DISTINCT FROM NEW.project_id
       AND r.current_version_ref=NEW.reference_version_id
       AND r.eligibility_state=NEW.result_state
       AND r.eligibility_reason=NEW.reason
       AND r.lock_version=NEW.result_lock_version
  ) THEN RAISE EXCEPTION 'Reference eligibility transaction is incomplete'; END IF;
  RETURN NULL;
END; $$;
"""

# Previous 0150 Guard, restored only when no eligibility history exists.
_PRIOR_ROOT = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_foundation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_no integer;
BEGIN
  IF TG_OP='INSERT' THEN
    IF TG_TABLE_NAME='sol_reference_versions' THEN
      IF NEW.version_no=1 THEN
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
       <>to_jsonb(OLD)-'current_version_ref'-'lock_version'
       OR NEW.lock_version<>OLD.lock_version+1
       OR NEW.current_version_ref IS NULL
       OR NEW.current_version_ref IS NOT DISTINCT FROM OLD.current_version_ref
       OR NOT EXISTS (
         SELECT 1 FROM plm.sol_reference_versions v
          JOIN plm.sol_reference_versions p
            ON p.reference_version_id=OLD.current_version_ref
           AND p.reference_solution_id=OLD.reference_solution_id AND p.scope=OLD.scope
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
"""

_CLOSED_EVENT = r"""
CREATE OR REPLACE FUNCTION plm.guard_solution_reference_eligibility_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reference eligibility Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    op.drop_constraint("ck_sol_reference_eligibility__lock",
                       "sol_reference_eligibility_events", schema="plm", type_="check")
    op.create_check_constraint(
        "ck_sol_reference_eligibility__lock", "sol_reference_eligibility_events",
        "prior_lock_version>=0 AND result_lock_version=prior_lock_version+1",
        schema="plm")
    op.execute(_EVENT_OWNER)
    op.execute(_ROOT_WITH_ELIGIBILITY)
    op.execute(sa.text(
        "CREATE CONSTRAINT TRIGGER trg_sol_reference_eligibility_events__closure "
        "AFTER INSERT ON plm.sol_reference_eligibility_events "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION plm.assert_solution_reference_eligibility_closure()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference eligibility Guard downgrade is disabled")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_reference_eligibility_events) "
        "OR EXISTS (SELECT 1 FROM plm.sol_reference_solutions "
        "WHERE eligibility_state<>'REFERENCE_ONLY' OR eligibility_reason IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Reference eligibility history prevents Guard downgrade")
    op.execute("DROP TRIGGER trg_sol_reference_eligibility_events__closure "
               "ON plm.sol_reference_eligibility_events")
    op.execute("DROP FUNCTION plm.assert_solution_reference_eligibility_closure()")
    op.execute(_CLOSED_EVENT)
    op.execute(_PRIOR_ROOT)
    op.drop_constraint("ck_sol_reference_eligibility__lock",
                       "sol_reference_eligibility_events", schema="plm", type_="check")
    op.create_check_constraint(
        "ck_sol_reference_eligibility__lock", "sol_reference_eligibility_events",
        "prior_lock_version>=1 AND result_lock_version=prior_lock_version+1",
        schema="plm")
