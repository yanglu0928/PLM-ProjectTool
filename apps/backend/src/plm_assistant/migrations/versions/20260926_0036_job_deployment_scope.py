"""CR-JOB-001 restore frozen DEPLOYMENT scope without remapping history."""
from alembic import context,op
import sqlalchemy as sa

revision="20260926_0036"
down_revision="20260926_0035"
branch_labels=None
depends_on=None

_TABLES=(("job_jobs","ck_job_jobs__scope"),("job_outbox_events","ck_job_outbox_events__scope"))
_OLD="(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)"
_NEW="(scope IN ('GLOBAL','DEPLOYMENT') AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)"


def _replace(expression):
    for table,constraint in _TABLES:
        op.drop_constraint(constraint,table,schema="plm",type_="check")
        op.create_check_constraint(constraint,table,expression,schema="plm")


def upgrade():
    _replace(_NEW)


def downgrade():
    if context.is_offline_mode():raise RuntimeError("offline Job scope downgrade disabled")
    op.execute("LOCK TABLE plm.job_jobs, plm.job_outbox_events IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.job_jobs WHERE scope='DEPLOYMENT') OR EXISTS(SELECT 1 FROM plm.job_outbox_events WHERE scope='DEPLOYMENT')")):
        raise RuntimeError("DEPLOYMENT Job/Outbox history exists; downgrade refused")
    _replace(_OLD)
