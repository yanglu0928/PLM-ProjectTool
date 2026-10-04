"""CR-JOB-006: immutable Audit-owned user retry lineage; no public retry command."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision='20260927_0045'
down_revision='20260927_0044'
branch_labels=None
depends_on=None

def upgrade():
    ids=('new_export_id','source_export_id','source_job_id','source_failure_event_id','new_job_id','new_event_id','retry_audit_event_id')
    op.create_table('aud_export_retry_generations',
        *(sa.Column(c,UUID(as_uuid=True),nullable=False) for c in ids),
        sa.Column('expected_source_version',sa.BigInteger(),nullable=False),
        sa.Column('first_job_version',sa.BigInteger(),nullable=False),
        sa.Column('created_at',TIMESTAMP(timezone=True,precision=6),nullable=False,server_default=sa.text('statement_timestamp()')),
        sa.PrimaryKeyConstraint('new_export_id',name='pk_aud_export_retry_generations'),
        sa.ForeignKeyConstraint(['new_export_id'],['plm.aud_export_acceptances.export_id'],name='fk_aud_retry__new_acceptance'),
        sa.ForeignKeyConstraint(['source_export_id'],['plm.aud_export_acceptances.export_id'],name='fk_aud_retry__source_acceptance'),
        sa.ForeignKeyConstraint(['source_failure_event_id'],['plm.aud_events.audit_event_id'],name='fk_aud_retry__failure'),
        sa.ForeignKeyConstraint(['retry_audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_aud_retry__audit'),
        sa.UniqueConstraint('new_job_id',name='uq_aud_retry__new_job'),
        sa.UniqueConstraint('new_event_id',name='uq_aud_retry__new_event'),
        sa.UniqueConstraint('retry_audit_event_id',name='uq_aud_retry__audit'),
        sa.CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in ids)+
            ' AND new_export_id<>source_export_id AND new_job_id<>source_job_id AND expected_source_version>=0 AND first_job_version=0 AND isfinite(created_at)',name='ck_aud_retry__shape'),
        schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_audit_retry_generation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM plm.aud_exports prior_root
        JOIN plm.aud_export_acceptances oa ON oa.export_id=prior_root.export_id
        JOIN plm.aud_events f ON f.audit_event_id=NEW.source_failure_event_id
        JOIN plm.aud_exports fresh ON fresh.export_id=NEW.new_export_id
        JOIN plm.aud_export_acceptances na ON na.export_id=fresh.export_id
        JOIN plm.aud_events e ON e.audit_event_id=NEW.retry_audit_event_id
        WHERE prior_root.export_id=NEW.source_export_id
          AND oa.job_id=NEW.source_job_id AND na.job_id=NEW.new_job_id AND na.event_id=NEW.new_event_id
          AND ROW(prior_root.scope,prior_root.project_id,prior_root.purpose,prior_root.start_at,prior_root.end_at,prior_root.action,prior_root.outcome,
            prior_root.filter_actor_id,prior_root.target_object_type,prior_root.target_object_id,prior_root.filter_trace_id,
            prior_root.policy_version,prior_root.projection_version,prior_root.format_version,prior_root.intent_hash)
            IS NOT DISTINCT FROM
            ROW(fresh.scope,fresh.project_id,fresh.purpose,fresh.start_at,fresh.end_at,fresh.action,fresh.outcome,
            fresh.filter_actor_id,fresh.target_object_type,fresh.target_object_id,fresh.filter_trace_id,
            fresh.policy_version,fresh.projection_version,fresh.format_version,fresh.intent_hash)
          AND f.actor_type='SYSTEM' AND f.actor_id IS NOT NULL AND f.original_actor_id=prior_root.actor_id
          AND f.actor_hint_digest IS NULL AND f.trace_id=prior_root.trace_id
          AND f.event_scope=prior_root.scope AND f.target_project_id IS NOT DISTINCT FROM prior_root.project_id
          AND f.action='AUDIT_EXPORT_FAILED' AND f.outcome='FAILED'
          AND f.target_owner_module='jobs' AND f.target_object_type='JOB-01'
          AND f.target_object_id=oa.job_id AND f.target_version_id IS NULL
          AND f.reason_code='AUDIT_UNAVAILABLE' AND f.before_state='RUNNING' AND f.after_state='FAILED'
          AND f.occurred_at>=oa.accepted_at AND fresh.requested_at>=f.occurred_at
          AND e.actor_type='USER' AND e.actor_id=fresh.actor_id AND e.original_actor_id IS NULL
          AND e.actor_hint_digest IS NULL AND e.trace_id=fresh.trace_id
          AND e.event_scope=fresh.scope AND e.target_project_id IS NOT DISTINCT FROM fresh.project_id
          AND e.action='AUDIT_EXPORT_USER_RETRY_REQUESTED' AND e.outcome='SUCCESS'
          AND e.target_owner_module='jobs' AND e.target_object_type='JOB-01'
          AND e.target_object_id=na.job_id AND e.target_version_id IS NULL
          AND e.reason_code='USER_RETRY' AND e.before_state='FAILED' AND e.after_state='PENDING'
          AND e.occurred_at>=na.accepted_at AND NEW.created_at>=e.occurred_at
      ) THEN RAISE EXCEPTION 'Invalid Audit retry generation source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_audit_retry_generation_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Audit retry generations are immutable'; END $$;
    CREATE TRIGGER trg_aud_retry_source BEFORE INSERT ON plm.aud_export_retry_generations
      FOR EACH ROW EXECUTE FUNCTION plm.validate_audit_retry_generation();
    CREATE TRIGGER trg_aud_retry_immutable BEFORE UPDATE OR DELETE ON plm.aud_export_retry_generations
      FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_retry_generation_change();
    CREATE TRIGGER trg_aud_retry_truncate BEFORE TRUNCATE ON plm.aud_export_retry_generations
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_retry_generation_change();
    """)

def downgrade():
    op.execute("""LOCK TABLE plm.aud_export_retry_generations IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.aud_export_retry_generations)
      THEN RAISE EXCEPTION 'Cannot discard Audit retry generation history'; END IF; END $$;""")
    op.drop_table('aud_export_retry_generations',schema='plm')
    op.execute('DROP FUNCTION plm.validate_audit_retry_generation()')
    op.execute('DROP FUNCTION plm.reject_audit_retry_generation_change()')
