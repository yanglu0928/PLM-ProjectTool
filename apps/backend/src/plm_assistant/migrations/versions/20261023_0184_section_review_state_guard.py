"""Open only result-closed Section Review lifecycle transitions.

Revision ID: 20261023_0184
Revises: 20261023_0183
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa


revision = "20261023_0184"
down_revision = "20261023_0183"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_section_review_version_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['version_state','review_ref','review_round_ref'])
       IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['version_state','review_ref','review_round_ref'])
     OR NOT (
       (OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
        AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
        AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL)
       OR (OLD.version_state='IN_REVIEW'
           AND NEW.version_state IN ('APPROVED','RETURNED')
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
       OR (OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
           AND NEW.review_ref IS NOT DISTINCT FROM OLD.review_ref
           AND NEW.review_round_ref IS NOT DISTINCT FROM OLD.review_round_ref)
     ) THEN
    RAISE EXCEPTION 'SectionVersion update is outside Review Owner';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_section_review_version_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_state text;
BEGIN
  SELECT version_state INTO latest_state FROM plm.sol_section_versions
   WHERE solution_section_id=NEW.solution_section_id
     AND project_id=NEW.project_id
   ORDER BY version_no DESC LIMIT 1 FOR SHARE;
  IF latest_state='IN_REVIEW' THEN
    RAISE EXCEPTION 'SectionVersion cannot be created during Review';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_section_review_approved_pointer()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['current_approved_version_ref','lock_version'])
       IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['current_approved_version_ref','lock_version'])
     OR OLD.section_state<>'ACTIVE' OR NEW.section_state<>'ACTIVE'
     OR NEW.lock_version<>OLD.lock_version+1
     OR NEW.current_approved_version_ref IS NULL
     OR NEW.current_approved_version_ref
        IS NOT DISTINCT FROM OLD.current_approved_version_ref
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_section_versions v
        WHERE v.solution_section_version_id=NEW.current_approved_version_ref
          AND v.solution_section_id=NEW.solution_section_id
          AND v.project_id=NEW.project_id
          AND v.version_state='APPROVED'
          AND v.review_ref IS NOT NULL AND v.review_round_ref IS NOT NULL
     ) THEN
    RAISE EXCEPTION 'Section approval pointer is outside Review Owner';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_section_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root_row plm.sol_sections%ROWTYPE;
        version_row plm.sol_section_versions%ROWTYPE;
        previous_row plm.sol_section_versions%ROWTYPE;
        review_row plm.rvw_reviews%ROWTYPE;
        round_row plm.rvw_review_rounds%ROWTYPE;
        latest_id uuid;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Section Review result history is immutable';
  END IF;
  SELECT * INTO root_row FROM plm.sol_sections
   WHERE solution_section_id=NEW.solution_section_id
     AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO version_row FROM plm.sol_section_versions
   WHERE solution_section_version_id=NEW.solution_section_version_id
     AND solution_section_id=NEW.solution_section_id
     AND project_id=NEW.project_id FOR SHARE;
  SELECT solution_section_version_id INTO latest_id FROM plm.sol_section_versions
   WHERE solution_section_id=NEW.solution_section_id
     AND project_id=NEW.project_id ORDER BY version_no DESC LIMIT 1;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  IF root_row.solution_section_id IS NULL OR root_row.section_state<>'ACTIVE'
     OR root_row.current_approved_version_ref
        IS DISTINCT FROM NEW.current_approved_version_ref
     OR latest_id IS DISTINCT FROM NEW.solution_section_version_id
     OR (root_row.current_approved_version_ref IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM plm.sol_section_versions current_approved
        WHERE current_approved.solution_section_version_id
              =root_row.current_approved_version_ref
          AND current_approved.solution_section_id=NEW.solution_section_id
          AND current_approved.project_id=NEW.project_id
          AND current_approved.version_state='APPROVED'
          AND current_approved.review_ref IS NOT NULL
          AND current_approved.review_round_ref IS NOT NULL))
     OR version_row.solution_section_version_id IS NULL
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'SOL-05'
     OR review_row.subject_id IS DISTINCT FROM NEW.solution_section_id
     OR review_row.policy_code<>'SOLUTION_SECTION_ALL_V1'
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id
        IS DISTINCT FROM NEW.solution_section_version_id
     OR round_row.round_state IS DISTINCT FROM review_row.review_state
     OR NOT EXISTS (
       SELECT 1 FROM plm.rvw_subject_snapshots s
        WHERE s.review_id=NEW.review_id
          AND s.review_round_id=NEW.review_round_id
          AND s.scope='PROJECT' AND s.project_id=NEW.project_id
          AND s.subject_type='SOL-05'
          AND s.subject_id=NEW.solution_section_id
          AND s.subject_version_id=NEW.solution_section_version_id
          AND s.content_fingerprint=version_row.content_fingerprint
     ) THEN
    RAISE EXCEPTION 'Section Review result does not match current facts';
  END IF;
  IF NEW.event_type='START' THEN
    IF latest_id IS DISTINCT FROM NEW.solution_section_version_id
       OR version_row.version_state<>'IN_REVIEW'
       OR review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_id
       OR round_row.started_by IS DISTINCT FROM NEW.actor_id
       OR NEW.previous_approved_version_ref
          IS DISTINCT FROM NEW.current_approved_version_ref THEN
      RAISE EXCEPTION 'Section Review start result is invalid';
    END IF;
  ELSIF NEW.event_type='APPROVED' THEN
    IF version_row.version_state<>'APPROVED'
       OR review_row.review_state<>'APPROVED'
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref
          IS DISTINCT FROM NEW.solution_section_version_id
       OR NOT EXISTS (SELECT 1 FROM plm.rvw_round_events e
         WHERE e.review_id=NEW.review_id
           AND e.review_round_id=NEW.review_round_id
           AND e.actor_id=NEW.actor_id AND e.result_state='APPROVED') THEN
      RAISE EXCEPTION 'Section Review approval result is invalid';
    END IF;
    IF NEW.previous_approved_version_ref IS NOT NULL THEN
      SELECT * INTO previous_row FROM plm.sol_section_versions
       WHERE solution_section_version_id=NEW.previous_approved_version_ref
         AND solution_section_id=NEW.solution_section_id
         AND project_id=NEW.project_id FOR SHARE;
      IF previous_row.solution_section_version_id IS NULL
         OR previous_row.version_state<>'SUPERSEDED'
         OR previous_row.version_no>=version_row.version_no THEN
        RAISE EXCEPTION 'Section previous approval was not superseded';
      END IF;
    END IF;
  ELSIF NEW.event_type IN ('RETURNED','WITHDRAWN') THEN
    IF version_row.version_state<>'RETURNED'
       OR review_row.review_state<>NEW.event_type
       OR review_row.active_round_id IS NOT NULL
       OR NEW.previous_approved_version_ref
          IS DISTINCT FROM NEW.current_approved_version_ref
       OR NOT EXISTS (SELECT 1 FROM plm.rvw_round_events e
         WHERE e.review_id=NEW.review_id
           AND e.review_round_id=NEW.review_round_id
           AND e.actor_id=NEW.actor_id AND e.result_state=NEW.event_type) THEN
      RAISE EXCEPTION 'Section Review nonapproval result is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Section Review result event is invalid';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_section_review_version_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_section_review_state_results r
      WHERE r.solution_section_version_id=NEW.solution_section_version_id
        AND r.solution_section_id=NEW.solution_section_id
        AND r.project_id=NEW.project_id AND r.event_type='START'
        AND r.review_id=NEW.review_ref AND r.review_round_id=NEW.review_round_ref)
      THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='IN_REVIEW'
        AND NEW.version_state IN ('APPROVED','RETURNED') THEN
    IF EXISTS (SELECT 1 FROM plm.sol_section_review_state_results r
      WHERE r.solution_section_version_id=NEW.solution_section_version_id
        AND r.solution_section_id=NEW.solution_section_id
        AND r.project_id=NEW.project_id
        AND r.event_type=CASE WHEN NEW.version_state='APPROVED' THEN 'APPROVED'
          ELSE (SELECT review_state FROM plm.rvw_reviews
                 WHERE review_id=NEW.review_ref) END
        AND r.review_id=NEW.review_ref AND r.review_round_id=NEW.review_round_ref)
      THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_section_review_state_results r
      WHERE r.solution_section_id=NEW.solution_section_id
        AND r.project_id=NEW.project_id
        AND r.previous_approved_version_ref=NEW.solution_section_version_id
        AND r.event_type='APPROVED') THEN RETURN NULL; END IF;
  END IF;
  RAISE EXCEPTION 'SectionVersion Review transition has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_section_review_pointer_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM plm.sol_section_review_state_results r
    WHERE r.solution_section_id=NEW.solution_section_id
      AND r.project_id=NEW.project_id
      AND r.event_type='APPROVED'
      AND r.previous_approved_version_ref
          IS NOT DISTINCT FROM OLD.current_approved_version_ref
      AND r.current_approved_version_ref=NEW.current_approved_version_ref)
    THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Section approval pointer has no immutable result';
END; $$;
"""


def upgrade() -> None:
    op.execute(sa.text(_GUARDS))
    op.execute("DROP TRIGGER trg_sol_section_versions__owner ON plm.sol_section_versions")
    op.execute(
        "CREATE TRIGGER trg_sol_section_versions__owner "
        "BEFORE INSERT OR DELETE ON plm.sol_section_versions "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_section_version_foundation()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_versions__review_update "
        "BEFORE UPDATE ON plm.sol_section_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_section_review_version_transition()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_versions__review_insert "
        "BEFORE INSERT ON plm.sol_section_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_section_review_version_insert()")
    op.execute("DROP TRIGGER trg_sol_sections__owner ON plm.sol_sections")
    op.execute(
        "CREATE TRIGGER trg_sol_sections__owner "
        "BEFORE INSERT OR DELETE ON plm.sol_sections FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_solution_identity_foundation()")
    op.execute(
        "CREATE TRIGGER trg_sol_sections__review_pointer "
        "BEFORE UPDATE ON plm.sol_sections FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_section_review_approved_pointer()")
    op.execute("DROP TRIGGER trg_sol_section_review_results__closed "
               "ON plm.sol_section_review_state_results")
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_review_state_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_section_review_state_result()")
    op.execute("DROP TRIGGER trg_sol_section_review_results__no_truncate "
               "ON plm.sol_section_review_state_results")
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_section_review_state_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_section_review_state_result()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_sol_section_versions__review_closure "
        "AFTER UPDATE ON plm.sol_section_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_section_review_version_closure()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_sol_sections__review_closure "
        "AFTER UPDATE ON plm.sol_sections DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_section_review_pointer_closure()")
    op.create_index("uq_sol_section_versions__section_approved",
                    "sol_section_versions", ["solution_section_id"],
                    unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='APPROVED'"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Section Review state downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.sol_sections, plm.sol_section_versions, "
        "plm.sol_section_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_section_review_state_results) "
        "OR EXISTS (SELECT 1 FROM plm.sol_sections "
        "WHERE current_approved_version_ref IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.sol_section_versions "
        "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
        "OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Section Review state history prevents downgrade")
    op.drop_index("uq_sol_section_versions__section_approved",
                  table_name="sol_section_versions", schema="plm")
    op.execute("DROP TRIGGER trg_sol_section_versions__review_closure "
               "ON plm.sol_section_versions")
    op.execute("DROP TRIGGER trg_sol_sections__review_closure ON plm.sol_sections")
    op.execute("DROP TRIGGER trg_sol_section_versions__review_update "
               "ON plm.sol_section_versions")
    op.execute("DROP TRIGGER trg_sol_section_versions__review_insert "
               "ON plm.sol_section_versions")
    op.execute("DROP TRIGGER trg_sol_section_versions__owner ON plm.sol_section_versions")
    op.execute(
        "CREATE TRIGGER trg_sol_section_versions__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_versions "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_section_version_foundation()")
    op.execute("DROP TRIGGER trg_sol_sections__review_pointer ON plm.sol_sections")
    op.execute("DROP TRIGGER trg_sol_sections__owner ON plm.sol_sections")
    op.execute(
        "CREATE TRIGGER trg_sol_sections__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_sections "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_identity_foundation()")
    op.execute("DROP TRIGGER trg_sol_section_review_results__owner "
               "ON plm.sol_section_review_state_results")
    op.execute("DROP TRIGGER trg_sol_section_review_results__no_truncate "
               "ON plm.sol_section_review_state_results")
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__closed "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_section_review_state_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_section_review_state_result_closed()")
    op.execute(
        "CREATE TRIGGER trg_sol_section_review_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_section_review_state_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_section_review_state_result_closed()")
    for name in (
        "guard_section_review_version_transition",
        "guard_section_review_version_insert",
        "guard_section_review_approved_pointer",
        "guard_section_review_state_result",
        "enforce_section_review_version_closure",
        "enforce_section_review_pointer_closure",
    ):
        op.execute(f"DROP FUNCTION plm.{name}()")
