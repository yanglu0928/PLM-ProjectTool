"""Add closed GLOBAL ReferenceVersion publication event history.

Revision ID: 20261009_0157
Revises: 20261009_0156
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261009_0157"
down_revision = "20261009_0156"
branch_labels = None
depends_on = None

_TABLE = "sol_global_reference_publication_events"
_GUARD = r"""
CREATE FUNCTION plm.guard_global_reference_publication_closed()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'GLOBAL Reference publication Owner is not installed';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    stamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    op.create_table(
        _TABLE,
        sa.Column("publication_event_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("reference_solution_id", ident, nullable=False),
        sa.Column("reference_version_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False,
                  server_default=sa.text("'GLOBAL'")),
        sa.Column("event_no", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.Text(), nullable=False),
        sa.Column("display_label", sa.Text()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("created_at", stamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.UniqueConstraint("reference_solution_id", "event_no",
                            name="uq_sol_global_publications__root_no"),
        sa.ForeignKeyConstraint(
            ["reference_version_id", "reference_solution_id", "scope"],
            ["plm.sol_reference_versions.reference_version_id",
             "plm.sol_reference_versions.reference_solution_id",
             "plm.sol_reference_versions.scope"],
            name="fk_sol_global_publications__version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                                name="fk_sol_global_publications__actor",
                                ondelete="NO ACTION"),
        sa.CheckConstraint("scope='GLOBAL'", name="ck_sol_global_publications__scope"),
        sa.CheckConstraint("event_no>0", name="ck_sol_global_publications__number"),
        sa.CheckConstraint("event_kind IN ('PUBLISH','REVOKE')",
                           name="ck_sol_global_publications__kind"),
        sa.CheckConstraint(
            "(event_kind='PUBLISH' AND display_label IS NOT NULL AND "
            "char_length(display_label) BETWEEN 1 AND 160 AND "
            "display_label=btrim(display_label) AND "
            "display_label !~ '[[:cntrl:]]') OR "
            "(event_kind='REVOKE' AND display_label IS NULL)",
            name="ck_sol_global_publications__label"),
        sa.CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND "
                           "reason=btrim(reason) AND reason !~ '[[:cntrl:]]'",
                           name="ck_sol_global_publications__reason"),
        sa.CheckConstraint("isfinite(created_at)",
                           name="ck_sol_global_publications__created_at"),
        schema="plm",
    )
    op.create_index("ix_sol_global_publications__version", _TABLE,
                    ["reference_version_id", "event_no"], schema="plm")
    op.execute(_GUARD)
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_global_publications__owner "
        f"BEFORE INSERT OR UPDATE OR DELETE ON plm.{_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION plm.guard_global_reference_publication_closed()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_sol_global_publications__no_truncate "
        f"BEFORE TRUNCATE ON plm.{_TABLE} FOR EACH STATEMENT "
        "EXECUTE FUNCTION plm.reject_solution_reference_truncate()"
    ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline GLOBAL Reference publication downgrade is disabled")
    if op.get_bind().execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM plm.{_TABLE})"
    )).scalar_one():
        raise RuntimeError("GLOBAL Reference publication history prevents downgrade")
    op.drop_index("ix_sol_global_publications__version", table_name=_TABLE,
                  schema="plm")
    op.drop_table(_TABLE, schema="plm")
    op.execute("DROP FUNCTION plm.guard_global_reference_publication_closed()")
