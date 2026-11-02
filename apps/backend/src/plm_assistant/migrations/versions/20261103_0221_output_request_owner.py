"""Enable transactional OUT-01 create Owner and bind its Job."""
from __future__ import annotations
from alembic import op
revision="20261103_0221"
down_revision="20261102_0220"
branch_labels=None
depends_on=None
def upgrade()->None:
    for table in ("out_context_snapshots","out_output_requests"):
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
    op.create_foreign_key("fk_out_output_requests__job","out_output_requests","job_jobs",
        ["job_ref"],["job_id"],source_schema="plm",referent_schema="plm",ondelete="NO ACTION")
def downgrade()->None:
    op.drop_constraint("fk_out_output_requests__job","out_output_requests",
        schema="plm",type_="foreignkey")
    for table in ("out_context_snapshots","out_output_requests"):
        op.execute(f"CREATE TRIGGER trg_{table}__owner_closed "
            f"BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.reject_output_foundation_write()")
