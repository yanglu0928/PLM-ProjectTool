"""CR-RVW-002 additive withdrawal history; never infer missing legacy reasons."""
from alembic import context, op
import sqlalchemy as sa

revision = "20260926_0035"
down_revision = "20260926_0034"
branch_labels = None
depends_on = None

_TABLE = "rvw_round_events"
_CHECK = "ck_rvw_events__withdrawal_reason"
_SHAPE = "withdrawal_reason IS NULL OR (event_type='WITHDRAWN' AND withdrawal_reason ~ '[^[:space:]]')"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("withdrawal_reason", sa.Text(), nullable=True), schema="plm")
    op.create_check_constraint(_CHECK, _TABLE, _SHAPE, schema="plm")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Review reason downgrade disabled")
    # Hold through Alembic's transaction: no concurrent reason can slip between
    # the loss-prevention check and column removal.
    op.execute("LOCK TABLE plm.rvw_round_events IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.rvw_round_events WHERE withdrawal_reason IS NOT NULL)")):
        raise RuntimeError("Review withdrawal reason history exists; downgrade refused")
    op.drop_constraint(_CHECK, _TABLE, schema="plm", type_="check")
    op.drop_column(_TABLE, "withdrawal_reason", schema="plm")
