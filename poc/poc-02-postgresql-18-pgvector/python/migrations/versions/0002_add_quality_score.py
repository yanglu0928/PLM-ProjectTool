"""Add a quality score while retaining existing rows."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "poc02_migration_vectors",
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.alter_column("poc02_migration_vectors", "quality_score", server_default=None)


def downgrade() -> None:
    op.drop_column("poc02_migration_vectors", "quality_score")
