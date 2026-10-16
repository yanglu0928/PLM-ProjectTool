"""CR-JOB-002: user concurrency version, independent of Lease renewal."""
from alembic import op
import sqlalchemy as sa

revision='20260927_0043'
down_revision='20260926_0042'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('job_jobs',sa.Column('lock_version',sa.BigInteger(),nullable=False,server_default=sa.text('0')),schema='plm')
    op.create_check_constraint('ck_job_jobs__lock_version','job_jobs','lock_version>=0',schema='plm')
    op.execute("""
    CREATE FUNCTION plm.bump_job_resource_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.lock_version IS DISTINCT FROM OLD.lock_version THEN
        RAISE EXCEPTION 'Job resource version is database-owned';
      END IF;
      IF (to_jsonb(NEW)-ARRAY['lock_version','lease_expires_at'])
          IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['lock_version','lease_expires_at']) THEN
        IF OLD.lock_version>=9223372036854775807 THEN
          RAISE EXCEPTION 'Job resource version exhausted';
        END IF;
        NEW.lock_version := OLD.lock_version+1;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_job_jobs_resource_version BEFORE UPDATE ON plm.job_jobs
      FOR EACH ROW EXECUTE FUNCTION plm.bump_job_resource_version();
    """)

def downgrade():
    op.execute('DROP TRIGGER trg_job_jobs_resource_version ON plm.job_jobs')
    op.execute('DROP FUNCTION plm.bump_job_resource_version()')
    op.drop_constraint('ck_job_jobs__lock_version','job_jobs',schema='plm',type_='check')
    op.drop_column('job_jobs','lock_version',schema='plm')
