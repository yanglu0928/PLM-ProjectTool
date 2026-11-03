"""Install the Plugin package metadata INSERT Owner and keep records append-only."""
from __future__ import annotations

from alembic import op

revision = "20261103_0223"
down_revision = "20261102_0222"
branch_labels = None
depends_on = None

_TABLES = (
    "plg_packages",
    "plg_manifest_operations",
    "plg_manifest_dependencies",
    "plg_package_verifications",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
    op.execute("""
CREATE OR REPLACE FUNCTION plm.reject_plugin_package_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plugin package metadata is immutable';
END; $$
""")
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__immutable "
            f"BEFORE UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_package_mutation()"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TRIGGER trg_{table}__immutable ON plm.{table}")
    op.execute("DROP FUNCTION plm.reject_plugin_package_mutation()")
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed "
            f"BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_package_write()"
        )
