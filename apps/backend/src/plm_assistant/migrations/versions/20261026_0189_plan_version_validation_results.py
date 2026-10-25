"""Store immutable first-response snapshots for PlanVersion validation.

Revision ID: 20261026_0189
Revises: 20261026_0188
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261026_0189"
down_revision = "20261026_0188"
branch_labels = None
depends_on = None

_TABLE = "pln_plan_version_validation_results"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("blocking_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  nullable=False),
        sa.PrimaryKeyConstraint("audit_event_id",
                                name="pk_pln_plan_version_validation_results"),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_pln_validation_results__audit", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_validation_results__version", ondelete="NO ACTION"),
        sa.CheckConstraint("octet_length(snapshot_fingerprint)=32",
                           name="ck_pln_validation_results__fingerprint"),
        sa.CheckConstraint("jsonb_typeof(blocking_issues)='array'",
                           name="ck_pln_validation_results__blocking_array"),
        sa.CheckConstraint("jsonb_typeof(warnings)='array'",
                           name="ck_pln_validation_results__warnings_array"),
        sa.CheckConstraint("jsonb_typeof(coverage_summary)='object'",
                           name="ck_pln_validation_results__coverage_object"),
        sa.CheckConstraint("valid = (jsonb_array_length(blocking_issues)=0)",
                           name="ck_pln_validation_results__valid"),
        sa.CheckConstraint("isfinite(checked_at)",
                           name="ck_pln_validation_results__checked_at"),
        schema="plm",
    )
    op.create_index("ix_pln_validation_results__version_time", _TABLE,
                    ["project_id", "plan_version_id", "checked_at", "audit_event_id"],
                    schema="plm")
    op.execute("""
CREATE OR REPLACE FUNCTION plm.guard_plan_version_validation_result()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'PlanVersion validation reports are immutable';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM plm.aud_events AS e
    WHERE e.audit_event_id=NEW.audit_event_id
      AND e.event_scope='PROJECT'
      AND e.target_project_id=NEW.project_id
      AND e.actor_type='USER'
      AND e.action='PLAN_VERSION_VALIDATED'
      AND e.outcome='SUCCESS'
      AND e.target_owner_module='plan'
      AND e.target_object_type='PLN-02'
      AND e.target_object_id=NEW.plan_version_id
      AND e.target_version_id=NEW.plan_version_id
  ) THEN
    RAISE EXCEPTION 'PlanVersion validation report requires its matching AuditEvent';
  END IF;
  RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION plm.reject_plan_version_validation_result_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PlanVersion validation history cannot be truncated';
END; $$;
""")
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_plan_version_validation_result()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLE}__no_truncate BEFORE TRUNCATE ON plm.{_TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plan_version_validation_result_truncate()"
    )


def _has_history() -> bool:
    return bool(op.get_bind().execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE})")).scalar_one())


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PlanVersion validation result downgrade is disabled")
    if _has_history():
        raise RuntimeError("PlanVersion validation report history prevents downgrade")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__owner ON plm.{_TABLE}")
    op.execute(f"DROP TRIGGER trg_{_TABLE}__no_truncate ON plm.{_TABLE}")
    op.drop_index("ix_pln_validation_results__version_time", table_name=_TABLE, schema="plm")
    op.drop_table(_TABLE, schema="plm")
    op.execute("DROP FUNCTION plm.guard_plan_version_validation_result()")
    op.execute("DROP FUNCTION plm.reject_plan_version_validation_result_truncate()")
