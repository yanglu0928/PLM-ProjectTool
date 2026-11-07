"""Allow one immutable PluginExecution row per Job attempt."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261106_0233"
down_revision = "20261105_0232"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_plg_executions__job", "plg_executions",
        schema="plm", type_="unique",
    )
    op.create_unique_constraint(
        "uq_plg_executions__job_attempt", "plg_executions",
        ["job_id", "attempt_no"], schema="plm",
    )


def downgrade() -> None:
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
              FROM plm.plg_executions
             GROUP BY job_id
            HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade PluginExecution per-attempt history: multiple attempts exist';
          END IF;
        END
        $$;
    """))
    op.drop_constraint(
        "uq_plg_executions__job_attempt", "plg_executions",
        schema="plm", type_="unique",
    )
    op.create_unique_constraint(
        "uq_plg_executions__job", "plg_executions",
        ["job_id"], schema="plm",
    )
