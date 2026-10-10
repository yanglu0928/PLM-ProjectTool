"""Create the SC-04 validation-only Schema contract."""

from alembic import op

from schema_contract import metadata


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS plm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)
