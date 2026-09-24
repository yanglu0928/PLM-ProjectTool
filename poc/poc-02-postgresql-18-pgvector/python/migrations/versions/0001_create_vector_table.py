"""Create the PoC vector table."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "poc02_migration_vectors",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("embedding", Vector(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("poc02_migration_vectors")
