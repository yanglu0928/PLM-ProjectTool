"""Add bounded REVIEW_LIST and Reviewer Inbox indexes.

Revision ID: 20261019_0166
Revises: 20261019_0165
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261019_0166"
down_revision = "20261019_0165"
branch_labels = None
depends_on = None


REVIEW_LIST_INDEX = "ix_rvw_reviews__scope_created"
REVIEWER_PENDING_INDEX = "ix_rvw_assignments__reviewer_pending"


def upgrade() -> None:
    op.create_index(
        REVIEW_LIST_INDEX, "rvw_reviews",
        ["scope", "scope_project_key", sa.text("created_at DESC"),
         sa.text("review_id DESC")],
        schema="plm",
    )
    op.create_index(
        REVIEWER_PENDING_INDEX, "rvw_review_assignments",
        ["scope", "scope_project_key", "reviewer_id", "review_round_id"],
        schema="plm",
        postgresql_where=sa.text("assignment_state='PENDING'"),
    )


def downgrade() -> None:
    op.drop_index(
        REVIEWER_PENDING_INDEX, table_name="rvw_review_assignments",
        schema="plm",
    )
    op.drop_index(
        REVIEW_LIST_INDEX, table_name="rvw_reviews", schema="plm",
    )
