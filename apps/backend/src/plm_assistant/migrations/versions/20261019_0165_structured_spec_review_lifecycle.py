"""Open only audited SOL-06 Review lifecycle transitions.

Revision ID: 20261019_0165
Revises: 20261012_0164
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261019_0165"
down_revision = "20261012_0164"
branch_labels = None
depends_on = None


_ROOT_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_structured_solution_spec_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_no integer; latest_id uuid; latest_project uuid; latest_type text;
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
       OR NEW.review_round_ref IS NOT NULL THEN
      RAISE EXCEPTION 'StructuredSolutionSpec initial state is invalid';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(
      'plm.sol_structured_specs:' || NEW.spec_series_id::text, 0));
    SELECT version_no,structured_solution_spec_id,project_id,spec_type
      INTO latest_no,latest_id,latest_project,latest_type
      FROM plm.sol_structured_specs WHERE spec_series_id=NEW.spec_series_id
     ORDER BY version_no DESC LIMIT 1;
    IF (latest_no IS NULL AND (
          NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
       OR (latest_no IS NOT NULL AND (
          NEW.version_no<>latest_no+1
          OR NEW.supersedes_version_ref IS DISTINCT FROM latest_id
          OR NEW.project_id<>latest_project OR NEW.spec_type<>latest_type)) THEN
      RAISE EXCEPTION 'StructuredSolutionSpec version chain is invalid';
    END IF;
    RETURN NEW;
  ELSIF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec history is immutable';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(
    'plm.sol_structured_specs:' || NEW.spec_series_id::text, 0));
  IF NEW.structured_solution_spec_id<>OLD.structured_solution_spec_id
     OR NEW.spec_series_id<>OLD.spec_series_id OR NEW.project_id<>OLD.project_id
     OR NEW.spec_type<>OLD.spec_type OR NEW.version_no<>OLD.version_no
     OR NEW.content_fingerprint<>OLD.content_fingerprint
     OR NEW.supersedes_version_ref IS DISTINCT FROM OLD.supersedes_version_ref
     OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at THEN
    RAISE EXCEPTION 'StructuredSolutionSpec immutable content changed';
  END IF;
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW'
     AND OLD.review_ref IS NULL AND OLD.review_round_ref IS NULL
     AND NEW.review_ref IS NOT NULL AND NEW.review_round_ref IS NOT NULL THEN
    RETURN NEW;
  ELSIF OLD.version_state='IN_REVIEW'
     AND NEW.version_state IN ('APPROVED','RETURNED')
     AND NEW.review_ref=OLD.review_ref
     AND NEW.review_round_ref=OLD.review_round_ref THEN
    RETURN NEW;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED'
     AND NEW.review_ref=OLD.review_ref
     AND NEW.review_round_ref=OLD.review_round_ref THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'StructuredSolutionSpec lifecycle transition is invalid';
END; $$;
"""


_REVIEW_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.guard_structured_spec_review_state_result()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE review_row plm.rvw_reviews%ROWTYPE;
        round_row plm.rvw_review_rounds%ROWTYPE;
        version_row plm.sol_structured_specs%ROWTYPE;
        previous_row plm.sol_structured_specs%ROWTYPE;
        latest_id uuid; approved_id uuid;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec Review result is immutable';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(
    'plm.sol_structured_specs:' || NEW.spec_series_id::text, 0));
  SELECT * INTO version_row FROM plm.sol_structured_specs
   WHERE structured_solution_spec_id=NEW.structured_solution_spec_id
     AND spec_series_id=NEW.spec_series_id AND project_id=NEW.project_id
   FOR SHARE;
  SELECT structured_solution_spec_id INTO latest_id
    FROM plm.sol_structured_specs
   WHERE spec_series_id=NEW.spec_series_id AND project_id=NEW.project_id
   ORDER BY version_no DESC LIMIT 1;
  SELECT structured_solution_spec_id INTO approved_id
    FROM plm.sol_structured_specs
   WHERE spec_series_id=NEW.spec_series_id AND project_id=NEW.project_id
     AND version_state='APPROVED';
  SELECT * INTO review_row FROM plm.rvw_reviews
   WHERE review_id=NEW.review_id FOR SHARE;
  SELECT * INTO round_row FROM plm.rvw_review_rounds
   WHERE review_round_id=NEW.review_round_id FOR SHARE;
  IF version_row.structured_solution_spec_id IS NULL
     OR version_row.review_ref IS DISTINCT FROM NEW.review_id
     OR version_row.review_round_ref IS DISTINCT FROM NEW.review_round_id
     OR review_row.review_id IS NULL OR review_row.scope<>'PROJECT'
     OR review_row.project_id IS DISTINCT FROM NEW.project_id
     OR review_row.subject_type<>'SOL-06'
     OR review_row.subject_id IS DISTINCT FROM NEW.spec_series_id
     OR review_row.policy_code<>'STRUCTURED_SPEC_ALL_V1'
     OR round_row.review_round_id IS NULL
     OR round_row.review_id IS DISTINCT FROM NEW.review_id
     OR round_row.project_id IS DISTINCT FROM NEW.project_id
     OR round_row.subject_version_id IS DISTINCT FROM NEW.structured_solution_spec_id
     OR review_row.review_state IS DISTINCT FROM round_row.round_state THEN
    RAISE EXCEPTION 'StructuredSolutionSpec Review result does not match current facts';
  END IF;
  IF NEW.event_type='START' THEN
    IF version_row.version_state<>'IN_REVIEW'
       OR latest_id IS DISTINCT FROM NEW.structured_solution_spec_id
       OR review_row.review_state<>'IN_REVIEW'
       OR review_row.active_round_id IS DISTINCT FROM NEW.review_round_id
       OR round_row.started_by IS DISTINCT FROM NEW.actor_id
       OR NEW.previous_approved_version_ref IS DISTINCT FROM approved_id
       OR NEW.current_approved_version_ref IS DISTINCT FROM approved_id THEN
      RAISE EXCEPTION 'StructuredSolutionSpec Review start result is invalid';
    END IF;
  ELSIF NEW.event_type='APPROVED' THEN
    IF version_row.version_state<>'APPROVED'
       OR approved_id IS DISTINCT FROM NEW.structured_solution_spec_id
       OR review_row.review_state<>'APPROVED'
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM NEW.structured_solution_spec_id
       OR NOT EXISTS (SELECT 1 FROM plm.rvw_round_events e
         WHERE e.review_id=NEW.review_id
           AND e.review_round_id=NEW.review_round_id
           AND e.actor_id=NEW.actor_id AND e.result_state='APPROVED') THEN
      RAISE EXCEPTION 'StructuredSolutionSpec Review approval result is invalid';
    END IF;
    IF NEW.previous_approved_version_ref IS NOT NULL THEN
      SELECT * INTO previous_row FROM plm.sol_structured_specs
       WHERE structured_solution_spec_id=NEW.previous_approved_version_ref
         AND spec_series_id=NEW.spec_series_id AND project_id=NEW.project_id
       FOR SHARE;
      IF previous_row.structured_solution_spec_id IS NULL
         OR previous_row.version_state<>'SUPERSEDED'
         OR previous_row.version_no>=version_row.version_no THEN
        RAISE EXCEPTION 'StructuredSolutionSpec prior approval was not superseded';
      END IF;
    END IF;
  ELSIF NEW.event_type IN ('RETURNED','WITHDRAWN') THEN
    IF version_row.version_state<>'RETURNED'
       OR review_row.review_state<>NEW.event_type
       OR review_row.active_round_id IS NOT NULL
       OR NEW.current_approved_version_ref IS DISTINCT FROM approved_id
       OR NEW.previous_approved_version_ref IS DISTINCT FROM approved_id
       OR NOT EXISTS (SELECT 1 FROM plm.rvw_round_events e
         WHERE e.review_id=NEW.review_id
           AND e.review_round_id=NEW.review_round_id
           AND e.actor_id=NEW.actor_id AND e.result_state=NEW.event_type) THEN
      RAISE EXCEPTION 'StructuredSolutionSpec Review nonapproval result is invalid';
    END IF;
  ELSE
    RAISE EXCEPTION 'StructuredSolutionSpec Review result event is invalid';
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_structured_spec_review_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'StructuredSolutionSpec Review result history cannot be truncated';
END; $$;

CREATE OR REPLACE FUNCTION plm.enforce_structured_spec_review_closure()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.version_state='DRAFT' AND NEW.version_state='IN_REVIEW' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_spec_review_state_results x
      WHERE x.structured_solution_spec_id=NEW.structured_solution_spec_id
        AND x.event_type='START' AND x.review_id=NEW.review_ref
        AND x.review_round_id=NEW.review_round_ref) THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='IN_REVIEW'
        AND NEW.version_state IN ('APPROVED','RETURNED') THEN
    IF EXISTS (SELECT 1 FROM plm.sol_spec_review_state_results x
      WHERE x.structured_solution_spec_id=NEW.structured_solution_spec_id
        AND x.event_type=CASE WHEN NEW.version_state='APPROVED' THEN 'APPROVED'
          ELSE (SELECT review_state FROM plm.rvw_reviews
                 WHERE review_id=NEW.review_ref) END
        AND x.review_id=NEW.review_ref
        AND x.review_round_id=NEW.review_round_ref) THEN RETURN NULL; END IF;
  ELSIF OLD.version_state='APPROVED' AND NEW.version_state='SUPERSEDED' THEN
    IF EXISTS (SELECT 1 FROM plm.sol_spec_review_state_results x
      WHERE x.spec_series_id=NEW.spec_series_id AND x.project_id=NEW.project_id
        AND x.previous_approved_version_ref=NEW.structured_solution_spec_id
        AND x.event_type='APPROVED') THEN RETURN NULL; END IF;
  END IF;
  RAISE EXCEPTION 'StructuredSolutionSpec Review transition has no immutable result';
END; $$;
"""


_OLD_ROOT_GUARD = r"""
CREATE OR REPLACE FUNCTION plm.guard_structured_solution_spec_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE latest_no integer; latest_id uuid; latest_project uuid; latest_type text;
BEGIN
  IF TG_OP<>'INSERT' THEN
    RAISE EXCEPTION 'StructuredSolutionSpec history is immutable';
  END IF;
  IF NEW.version_state<>'DRAFT' OR NEW.review_ref IS NOT NULL
     OR NEW.review_round_ref IS NOT NULL THEN
    RAISE EXCEPTION 'StructuredSolutionSpec initial state is invalid';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(
    'plm.sol_structured_specs:' || NEW.spec_series_id::text, 0));
  SELECT version_no,structured_solution_spec_id,project_id,spec_type
    INTO latest_no,latest_id,latest_project,latest_type
    FROM plm.sol_structured_specs WHERE spec_series_id=NEW.spec_series_id
   ORDER BY version_no DESC LIMIT 1;
  IF (latest_no IS NULL AND (
        NEW.version_no<>1 OR NEW.supersedes_version_ref IS NOT NULL))
     OR (latest_no IS NOT NULL AND (
        NEW.version_no<>latest_no+1
        OR NEW.supersedes_version_ref IS DISTINCT FROM latest_id
        OR NEW.project_id<>latest_project OR NEW.spec_type<>latest_type)) THEN
    RAISE EXCEPTION 'StructuredSolutionSpec version chain is invalid';
  END IF;
  RETURN NEW;
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    op.create_table(
        "sol_spec_review_state_results",
        sa.Column("review_state_result_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("structured_solution_spec_id", ident, nullable=False),
        sa.Column("spec_series_id", ident, nullable=False),
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
            "structured_solution_spec_id", "event_type",
            name="uq_sol_spec_review_results__version_event"),
        sa.UniqueConstraint(
            "review_id", "review_round_id", "event_type",
            name="uq_sol_spec_review_results__round_event"),
        sa.ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id"],
            name="fk_sol_spec_review_results__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["previous_approved_version_ref", "spec_series_id", "project_id"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id"],
            name="fk_sol_spec_review_results__previous", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["current_approved_version_ref", "spec_series_id", "project_id"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id"],
            name="fk_sol_spec_review_results__current", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["review_id"], ["plm.rvw_reviews.review_id"],
            name="fk_sol_spec_review_results__review", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
            name="fk_sol_spec_review_results__round", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["plm.auth_users.user_id"],
            name="fk_sol_spec_review_results__actor", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "event_type IN ('START','APPROVED','RETURNED','WITHDRAWN')",
            name="ck_sol_spec_review_results__event"),
        sa.CheckConstraint(
            "(event_type='APPROVED' AND "
            "current_approved_version_ref=structured_solution_spec_id) OR "
            "(event_type<>'APPROVED' AND current_approved_version_ref "
            "IS NOT DISTINCT FROM previous_approved_version_ref)",
            name="ck_sol_spec_review_results__pointer"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_spec_review_results__created_at"),
        schema="plm")
    op.create_index(
        "ix_sol_spec_review_results__review_round",
        "sol_spec_review_state_results", ["review_id", "review_round_id"],
        schema="plm")
    op.create_index(
        "uq_sol_specs__series_approved", "sol_structured_specs",
        ["spec_series_id"], unique=True, schema="plm",
        postgresql_where=sa.text("version_state='APPROVED'"))
    op.execute(sa.text(_ROOT_GUARD + _REVIEW_GUARDS))
    op.execute(
        "CREATE TRIGGER trg_sol_spec_review_results__immutable "
        "BEFORE INSERT OR UPDATE OR DELETE ON "
        "plm.sol_spec_review_state_results FOR EACH ROW EXECUTE FUNCTION "
        "plm.guard_structured_spec_review_state_result()")
    op.execute(
        "CREATE TRIGGER trg_sol_spec_review_results__no_truncate "
        "BEFORE TRUNCATE ON plm.sol_spec_review_state_results "
        "FOR EACH STATEMENT EXECUTE FUNCTION "
        "plm.reject_structured_spec_review_result_truncate()")
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_sol_specs__review_closure "
        "AFTER UPDATE ON plm.sol_structured_specs DEFERRABLE INITIALLY "
        "DEFERRED FOR EACH ROW EXECUTE FUNCTION "
        "plm.enforce_structured_spec_review_closure()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline StructuredSolutionSpec Review downgrade is disabled")
    op.execute(
        "LOCK TABLE plm.sol_structured_specs, "
        "plm.sol_spec_review_state_results IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.sol_spec_review_state_results) "
        "OR EXISTS (SELECT 1 FROM plm.sol_structured_specs "
        "WHERE version_state<>'DRAFT' OR review_ref IS NOT NULL "
        "OR review_round_ref IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("StructuredSolutionSpec Review history prevents downgrade")
    op.execute("DROP TRIGGER trg_sol_specs__review_closure ON plm.sol_structured_specs")
    op.execute(
        "DROP TRIGGER trg_sol_spec_review_results__immutable "
        "ON plm.sol_spec_review_state_results")
    op.execute(
        "DROP TRIGGER trg_sol_spec_review_results__no_truncate "
        "ON plm.sol_spec_review_state_results")
    op.drop_index(
        "uq_sol_specs__series_approved", table_name="sol_structured_specs",
        schema="plm")
    op.drop_index(
        "ix_sol_spec_review_results__review_round",
        table_name="sol_spec_review_state_results", schema="plm")
    op.drop_table("sol_spec_review_state_results", schema="plm")
    for function in (
        "enforce_structured_spec_review_closure",
        "guard_structured_spec_review_state_result",
        "reject_structured_spec_review_result_truncate",
    ):
        op.execute(f"DROP FUNCTION plm.{function}()")
    op.execute(sa.text(_OLD_ROOT_GUARD))
