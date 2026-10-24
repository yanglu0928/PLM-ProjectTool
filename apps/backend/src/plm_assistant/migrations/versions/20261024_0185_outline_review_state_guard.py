"""Close Outline Review lifecycle transitions against immutable results.

Revision ID: 20261024_0185
Revises: 20261023_0184
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261024_0185"
down_revision = "20261023_0184"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_outline_review_version_transition()
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
    RAISE EXCEPTION 'OutlineVersion update is outside Review Owner';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_outline_review_version_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_state text;
BEGIN
  SELECT version_state INTO latest_state FROM plm.sol_outline_versions
   WHERE solution_outline_id=NEW.solution_outline_id
     AND project_id=NEW.project_id
   ORDER BY version_no DESC LIMIT 1 FOR SHARE;
  IF latest_state='IN_REVIEW' THEN
    RAISE EXCEPTION 'OutlineVersion cannot be created during Review';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_outline_review_approved_pointer()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['current_approved_version_ref','lock_version'])
       IS DISTINCT FROM
     (to_jsonb(OLD)-ARRAY['current_approved_version_ref','lock_version'])
     OR OLD.outline_state<>'ACTIVE' OR NEW.outline_state<>'ACTIVE'
     OR NEW.lock_version<>OLD.lock_version+1
     OR NEW.current_approved_version_ref IS NULL
     OR NEW.current_approved_version_ref
        IS NOT DISTINCT FROM OLD.current_approved_version_ref
     OR NOT EXISTS (
       SELECT 1 FROM plm.sol_outline_versions v
        WHERE v.solution_outline_version_id=NEW.current_approved_version_ref
          AND v.solution_outline_id=NEW.solution_outline_id
          AND v.project_id=NEW.project_id
          AND v.version_state='APPROVED'
          AND v.review_ref IS NOT NULL AND v.review_round_ref IS NOT NULL
     ) THEN
    RAISE EXCEPTION 'Outline approval pointer is outside Review Owner';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.guard_outline_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root_row plm.sol_outlines%ROWTYPE;
        version_row plm.sol_outline_versions%ROWTYPE;
        previous_row plm.sol_outline_versions%ROWTYPE;
        review_row plm.rvw_reviews%ROWTYPE;
        round_row plm.rvw_review_rounds%ROWTYPE;
        latest_id uuid;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'Outline Review result history is immutable';
  END IF;
  SELECT * INTO root_row FROM plm.sol_outlines
   WHERE solution_outline_id=NEW.solution_outline_id
     AND project_id=NEW.project_id FOR SHARE;
  SELECT * INTO version_row FROM plm.sol_outline_versions
   WHERE solution_outline_version_id=NEW.solution_outline_version_id
     AND solution_outline_id=NEW.solution_outline_id
     AND project_id=NEW.project_id FOR SHARE;
  SELECT solution_outline_version_id INTO latest_id FROM plm.sol_outline_versions
   WHERE solution_outline_id=NEW.solution_outline_id
     AND project_id=NEW.project_id ORDER BY version_no DESC LIMIT 1;
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  IF root_row.solution_outline_id IS NULL OR root_row.outline_state<>'ACTIVE'
     OR root_row.current_approved_version_ref
        IS DISTINCT FROM NEW.current_approved_version_ref
     OR latest_id IS DISTINCT FROM NEW.solution_outline_version_id
     OR (root_row.current_approved_version_ref IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM plm.sol_outline_versions current_approved
        WHERE current_approved.solution_outline_version_id
              =root_row.current_approved_version_ref
          AND current_approved.solution_outline_id=NEW.solution_outline_id
          AND current_approved.project_id=NEW.project_id
          AND current_approved.version_state='APPROVED'
          AND current_approved.review_ref IS NOT NULL
          AND current_approved.review_round_ref IS NOT NULL))
     OR version_row.solution_outline_version_id IS NULL
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'SOL-03'
     OR review_row.subject_id IS DISTINCT FROM NEW.solution_outline_id
     OR review_row.policy_code<>'SOLUTION_OUTLINE_ALL_V1'
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id
        IS DISTINCT FROM NEW.solution_outline_version_id
     OR round_row.round_state IS DISTINCT FROM review_row.review_state
     OR NOT EXISTS (
       SELECT 1 FROM plm.rvw_subject_snapshots s
        WHERE s.review_id=NEW.review_id
          AND s.review_round_id=NEW.review_round_id
          AND s.scope='PROJECT' AND s.project_id=NEW.project_id
          AND s.subject_type='SOL-03'
          AND s.subject_id=NEW.solution_outline_id
          AND s.subject_version_id=NEW.solution_outline_version_id
          AND s.content_fingerprint=version_row.content_fingerprint
     ) THEN
    RAISE EXCEPTION 'Outline Review result does not match current facts';
  END IF;
  IF NEW.event_type='START' THEN
    IF version_row.version_state<>'IN_REVIEW'
       OR review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_id
       OR round_row.started_by IS DISTINCT FROM NEW.actor_id
       OR NEW.previous_approved_version_ref
          IS DISTINCT FROM NEW.current_approved_version_ref THEN
      RAISE EXCEPTION 'Outline Review start result is invalid';
    END IF;
  ELSIF NEW.event_type='APPROVED' THEN
    IF version_row.version_state<>'APPROVED'
       OR review_row.review_state<>'APPROVED'
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref
          IS DISTINCT FROM NEW.solution_outline_version_id
       OR NOT EXISTS (SELECT 1 FROM plm.rvw_round_events e
         WHERE e.review_id=NEW.review_id
           AND e.review_round_id=NEW.review_round_id
           AND e.actor_id=NEW.actor_id AND e.result_state='APPROVED') THEN
      RAISE EXCEPTION 'Outline Review approval result is invalid';
    END IF;
    IF NEW.previous_approved_version_ref IS NOT NULL THEN
      SELECT * INTO previous_row FROM plm.sol_outline_versions
       WHERE solution_outline_version_id=NEW.previous_approved_version_ref
         AND solution_outline_id=NEW.solution_outline_id
         AND project_id=NEW.project_id FOR SHARE;
      IF previous_row.solution_outline_version_id IS NULL
         OR previous_row.version_state<>'SUPERSEDED'
         OR previous_row.version_no>=version_row.version_no THEN
        RAISE EXCEPTION 'Outline previous approval was not superseded';
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
      RAISE EXCEPTION 'Outline Review nonapproval result is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'Outline Review result event is invalid';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_outline_review_version_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_outline_review_state_results r
      WHERE r.solution_outline_version_id=NEW.solution_outline_version_id
        AND r.solution_outline_id=NEW.solution_outline_id
        AND r.project_id=NEW.project_id AND r.event_type='START'
        AND r.review_id=NEW.review_ref AND r.review_round_id=NEW.review_round_ref)
      THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='IN_REVIEW'
        AND NEW.version_state IN ('APPROVED','RETURNED') THEN
    IF EXISTS (SELECT 1 FROM plm.sol_outline_review_state_results r
      WHERE r.solution_outline_version_id=NEW.solution_outline_version_id
        AND r.solution_outline_id=NEW.solution_outline_id
        AND r.project_id=NEW.project_id
        AND r.event_type=CASE WHEN NEW.version_state='APPROVED' THEN 'APPROVED'
          ELSE (SELECT review_state FROM plm.rvw_reviews
                 WHERE review_id=NEW.review_ref) END
        AND r.review_id=NEW.review_ref AND r.review_round_id=NEW.review_round_ref)
      THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_outline_review_state_results r
      WHERE r.solution_outline_id=NEW.solution_outline_id
        AND r.project_id=NEW.project_id
        AND r.previous_approved_version_ref=NEW.solution_outline_version_id
        AND r.event_type='APPROVED') THEN RETURN NULL; END IF;
  END IF;
  RAISE EXCEPTION 'OutlineVersion Review transition has no immutable result';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_outline_review_pointer_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM plm.sol_outline_review_state_results r
    WHERE r.solution_outline_id=NEW.solution_outline_id
      AND r.project_id=NEW.project_id
      AND r.event_type='APPROVED'
      AND r.previous_approved_version_ref
          IS NOT DISTINCT FROM OLD.current_approved_version_ref
      AND r.current_approved_version_ref=NEW.current_approved_version_ref)
    THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Outline approval pointer has no immutable result';
END; $$;
"""


def upgrade() -> None:
    if not context.is_offline_mode():
        op.execute("LOCK TABLE plm.sol_outlines, plm.sol_outline_versions "
                   "IN ACCESS EXCLUSIVE MODE")
        if op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm.sol_outlines "
            "WHERE current_approved_version_ref IS NOT NULL) OR "
            "EXISTS (SELECT 1 FROM plm.sol_outline_versions "
            "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
            "OR review_round_ref IS NOT NULL)"
        )).scalar_one():
            raise RuntimeError("pre-existing Outline Review requires audited migration")
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_outline_review_state_results",
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("solution_outline_version_id", ident, nullable=False),
        sa.Column("solution_outline_id", ident, nullable=False),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("review_id", ident, nullable=False),
        sa.Column("review_round_id", ident, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("previous_approved_version_ref", ident),
        sa.Column("current_approved_version_ref", ident),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(
            timezone=True, precision=6), nullable=False,
            server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint(
            "solution_outline_version_id", "event_type",
            name="uq_sol_outline_review_results__version_event"),
        sa.UniqueConstraint(
            "review_id", "review_round_id", "event_type",
            name="uq_sol_outline_review_results__round_event"),
        sa.ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_sol_outline_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["previous_approved_version_ref", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_sol_outline_review_results__previous", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["current_approved_version_ref", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_sol_outline_review_results__current", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["review_id"], ["plm.rvw_reviews.review_id"],
                                name="fk_sol_outline_review_results__review",
                                ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
            name="fk_sol_outline_review_results__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_sol_outline_review_results__actor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint(
            "event_type IN ('START','APPROVED','RETURNED','WITHDRAWN')",
            name="ck_sol_outline_review_results__event"),
        sa.CheckConstraint(
            "(event_type='APPROVED' AND "
            "current_approved_version_ref=solution_outline_version_id) OR "
            "(event_type<>'APPROVED' AND current_approved_version_ref "
            "IS NOT DISTINCT FROM previous_approved_version_ref)",
            name="ck_sol_outline_review_results__pointer"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_outline_review_results__created_at"),
        schema="plm")
    op.create_index("ix_sol_outline_review_results__review_round",
                    "sol_outline_review_state_results",
                    ["review_id", "review_round_id"], schema="plm")
    op.execute(sa.text(_GUARDS))
    op.execute("DROP TRIGGER trg_sol_outline_versions__owner "
               "ON plm.sol_outline_versions")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_versions__owner "
        "BEFORE INSERT OR DELETE ON plm.sol_outline_versions "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_outline_version_foundation()")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_versions__review_update "
        "BEFORE UPDATE ON plm.sol_outline_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_outline_review_version_transition()")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_versions__review_insert "
        "BEFORE INSERT ON plm.sol_outline_versions FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_outline_review_version_insert()")
    op.execute("DROP TRIGGER trg_sol_outlines__owner ON plm.sol_outlines")
    op.execute(
        "CREATE TRIGGER trg_sol_outlines__owner "
        "BEFORE INSERT OR DELETE ON plm.sol_outlines FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_solution_identity_foundation()")
    op.execute(
        "CREATE TRIGGER trg_sol_outlines__review_pointer "
        "BEFORE UPDATE ON plm.sol_outlines FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_outline_review_approved_pointer()")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_review_results__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_outline_review_state_results "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_outline_review_state_result()")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_review_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_outline_review_state_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_outline_review_state_result()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_sol_outline_versions__review_closure "
        "AFTER UPDATE ON plm.sol_outline_versions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_outline_review_version_closure()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_sol_outlines__review_closure "
        "AFTER UPDATE ON plm.sol_outlines DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION plm.enforce_outline_review_pointer_closure()")
    op.create_index("uq_sol_outline_versions__outline_approved",
                    "sol_outline_versions", ["solution_outline_id"],
                    unique=True, schema="plm",
                    postgresql_where=sa.text("version_state='APPROVED'"))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Outline Review state downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.sol_outlines, plm.sol_outline_versions, "
        "plm.sol_outline_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_outline_review_state_results) "
        "OR EXISTS (SELECT 1 FROM plm.sol_outlines "
        "WHERE current_approved_version_ref IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM plm.sol_outline_versions "
        "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
        "OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("Outline Review state history prevents downgrade")
    op.drop_index("uq_sol_outline_versions__outline_approved",
                  table_name="sol_outline_versions", schema="plm")
    op.execute("DROP TRIGGER trg_sol_outline_versions__review_closure "
               "ON plm.sol_outline_versions")
    op.execute("DROP TRIGGER trg_sol_outlines__review_closure ON plm.sol_outlines")
    op.execute("DROP TRIGGER trg_sol_outline_versions__review_update "
               "ON plm.sol_outline_versions")
    op.execute("DROP TRIGGER trg_sol_outline_versions__review_insert "
               "ON plm.sol_outline_versions")
    op.execute("DROP TRIGGER trg_sol_outline_versions__owner "
               "ON plm.sol_outline_versions")
    op.execute(
        "CREATE TRIGGER trg_sol_outline_versions__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_outline_versions "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_solution_outline_version_foundation()")
    op.execute("DROP TRIGGER trg_sol_outlines__review_pointer ON plm.sol_outlines")
    op.execute("DROP TRIGGER trg_sol_outlines__owner ON plm.sol_outlines")
    op.execute(
        "CREATE TRIGGER trg_sol_outlines__owner "
        "BEFORE INSERT OR UPDATE OR DELETE ON plm.sol_outlines FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_solution_identity_foundation()")
    op.execute("DROP TRIGGER trg_sol_outline_review_results__owner "
               "ON plm.sol_outline_review_state_results")
    op.execute("DROP TRIGGER trg_sol_outline_review_results__no_truncate "
               "ON plm.sol_outline_review_state_results")
    op.drop_index("ix_sol_outline_review_results__review_round",
                  table_name="sol_outline_review_state_results", schema="plm")
    op.drop_table("sol_outline_review_state_results", schema="plm")
    for name in (
        "guard_outline_review_version_transition",
        "guard_outline_review_version_insert",
        "guard_outline_review_approved_pointer",
        "guard_outline_review_state_result",
        "enforce_outline_review_version_closure",
        "enforce_outline_review_pointer_closure",
    ):
        op.execute(f"DROP FUNCTION plm.{name}()")
