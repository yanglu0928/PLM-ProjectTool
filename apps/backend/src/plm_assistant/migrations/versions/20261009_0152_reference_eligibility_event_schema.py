"""Add closed, immutable Reference eligibility result/event storage.

Revision ID: 20261009_0152
Revises: 20261009_0151
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0152"
down_revision = "20261009_0151"
branch_labels = None
depends_on = None

_TABLE = "sol_reference_eligibility_events"
_CLOSED = r"""
CREATE FUNCTION plm.guard_solution_reference_eligibility_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Reference eligibility Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    # No trustworthy historical decision can be reconstructed from a root
    # state alone. Refuse unknown/manual edits instead of minting evidence.
    op.execute(sa.text("""
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM plm.sol_reference_solutions
     WHERE eligibility_state<>'REFERENCE_ONLY' OR eligibility_reason IS NOT NULL
  ) THEN RAISE EXCEPTION 'Reference eligibility history requires audited forward repair';
  END IF;
END $$;
"""))
    ident = postgresql.UUID(as_uuid=True)
    stamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        _TABLE,
        sa.Column("eligibility_event_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("reference_version_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("event_kind", sa.Text(), nullable=False),
        sa.Column("prior_state", sa.Text(), nullable=False),
        sa.Column("result_state", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("prior_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("result_lock_version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", stamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("reference_solution_id", "result_lock_version",
                            name="uq_sol_reference_eligibility__root_lock"),
        sa.ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                                ["plm.sol_reference_versions.reference_version_id",
                                 "plm.sol_reference_versions.reference_solution_id",
                                 "plm.sol_reference_versions.scope"],
                                name="fk_sol_reference_eligibility__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_sol_reference_eligibility__actor", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_sol_reference_eligibility__project", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                           "(scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_sol_reference_eligibility__scope"),
        sa.CheckConstraint("event_kind IN ('HUMAN','SYSTEM_INVALIDATION')",
                           name="ck_sol_reference_eligibility__kind"),
        sa.CheckConstraint("(event_kind='HUMAN' AND ((prior_state='REFERENCE_ONLY' "
                           "AND result_state IN ('ELIGIBLE','RESTRICTED','REVOKED')) OR "
                           "(prior_state='ELIGIBLE' AND result_state IN ('RESTRICTED','REVOKED')) OR "
                           "(prior_state='RESTRICTED' AND result_state IN ('ELIGIBLE','REVOKED')))) "
                           "OR (event_kind='SYSTEM_INVALIDATION' AND prior_state='ELIGIBLE' "
                           "AND result_state='RESTRICTED' "
                           "AND reason='CURRENT_VERSION_CHANGED_REQUIRES_REVIEW')",
                           name="ck_sol_reference_eligibility__transition"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason) "
                           "AND reason !~ '[[:cntrl:]]'",
                           name="ck_sol_reference_eligibility__reason"),
        sa.CheckConstraint("prior_lock_version>=1 AND "
                           "result_lock_version=prior_lock_version+1",
                           name="ck_sol_reference_eligibility__lock"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_reference_eligibility__created_at"),
        schema="plm",
    )
    op.create_index("ix_sol_reference_eligibility__root_created", _TABLE,
                    ["reference_solution_id", "created_at"], schema="plm")
    op.execute(_CLOSED)
    op.execute(sa.text(
        f"CREATE TRIGGER trg_{_TABLE}__owner BEFORE INSERT OR UPDATE OR DELETE "
        f"ON plm.{_TABLE} FOR EACH ROW "
        "EXECUTE FUNCTION plm.guard_solution_reference_eligibility_closed()"
    ))
    op.execute(sa.text(
        f"CREATE TRIGGER trg_{_TABLE}__no_truncate BEFORE TRUNCATE "
        f"ON plm.{_TABLE} FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_reference_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Reference eligibility downgrade is disabled")
    if op.get_bind().execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE})"
    )).scalar_one():
        raise RuntimeError("Reference eligibility history prevents downgrade")
    op.execute(sa.text(f"DROP TRIGGER trg_{_TABLE}__owner ON plm.{_TABLE}"))
    op.execute(sa.text(f"DROP TRIGGER trg_{_TABLE}__no_truncate ON plm.{_TABLE}"))
    op.drop_index("ix_sol_reference_eligibility__root_created",
                  table_name=_TABLE, schema="plm")
    op.drop_table(_TABLE, schema="plm")
    op.execute("DROP FUNCTION plm.guard_solution_reference_eligibility_closed()")
