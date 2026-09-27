"""CR-AUT-007 immutable administrator reset first credential source."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID,TIMESTAMP

revision='20260927_0049'
down_revision='20260927_0048'
branch_labels=None
depends_on=None


def upgrade():
    ids=('result_id','user_id','actor_id','before_credential_id','credential_id','audit_event_id','trace_id')
    op.create_table('auth_password_reset_results',
        *(sa.Column(c,UUID(as_uuid=True),nullable=False) for c in ids),
        *(sa.Column(c,sa.BigInteger(),nullable=False) for c in ('before_credential_version','credential_version',
            'before_user_version','user_version','revoked_session_count')),
        sa.Column('target_state',sa.Text(),nullable=False),
        sa.Column('changed_at',TIMESTAMP(timezone=True,precision=6),nullable=False),
        sa.Column('accepted_at',TIMESTAMP(timezone=True,precision=6),nullable=False,server_default=sa.text('statement_timestamp()')),
        sa.PrimaryKeyConstraint('result_id',name='pk_auth_password_reset_results'),
        sa.ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_reset__user'),
        sa.ForeignKeyConstraint(['actor_id'],['plm.auth_users.user_id'],name='fk_auth_reset__actor'),
        sa.ForeignKeyConstraint(['before_credential_id','user_id','before_credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_reset__before'),
        sa.ForeignKeyConstraint(['credential_id','user_id','credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_reset__after'),
        sa.ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_reset__audit'),
        sa.UniqueConstraint('user_id','credential_version',name='uq_auth_reset__credential'),
        sa.UniqueConstraint('user_id','user_version',name='uq_auth_reset__user_version'),
        sa.UniqueConstraint('audit_event_id',name='uq_auth_reset__audit'),
        sa.CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in ids)
            + ' AND before_credential_id<>credential_id'
            + ' AND before_credential_version BETWEEN 1 AND 9223372036854775806'
            + ' AND credential_version>1 AND credential_version-1=before_credential_version'
            + ' AND before_user_version BETWEEN 0 AND 9223372036854775806'
            + ' AND user_version>0 AND user_version-1=before_user_version AND revoked_session_count>=0'
            + " AND target_state IN ('ENABLED','DISABLED')"
            + ' AND isfinite(changed_at) AND isfinite(accepted_at) AND changed_at<=accepted_at',name='ck_auth_reset__shape'),
        schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_password_reset_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM 1 FROM plm.auth_users WHERE user_id IN (NEW.user_id,NEW.actor_id) ORDER BY user_id FOR UPDATE;
      IF NOT EXISTS(
        SELECT 1 FROM plm.auth_users u
        JOIN plm.auth_users actor ON actor.user_id=NEW.actor_id
        JOIN plm.auth_password_credentials ac ON ac.password_credential_id=actor.active_password_credential_id
          AND ac.user_id=actor.user_id AND ac.credential_version=actor.credential_version
        JOIN plm.auth_password_credentials oldc ON oldc.password_credential_id=NEW.before_credential_id
          AND oldc.user_id=u.user_id AND oldc.credential_version=NEW.before_credential_version
        JOIN plm.auth_password_credentials c ON c.password_credential_id=NEW.credential_id
          AND c.user_id=u.user_id AND c.credential_version=NEW.credential_version
        JOIN plm.aud_events a ON a.audit_event_id=NEW.audit_event_id
        WHERE u.user_id=NEW.user_id AND u.state=NEW.target_state AND u.updated_by=NEW.actor_id
          AND actor.state='ENABLED' AND actor.deployment_role='DEPLOYMENT_ADMIN'
          AND ((actor.user_id<>u.user_id AND ac.must_change_password=false)
            OR (actor.user_id=u.user_id AND oldc.must_change_password=false))
          AND u.active_password_credential_id=c.password_credential_id
          AND u.credential_version=c.credential_version AND u.lock_version=NEW.user_version
          AND u.updated_at=NEW.changed_at AND c.must_change_password=true AND c.changed_by=NEW.actor_id
          AND isfinite(oldc.changed_at) AND isfinite(c.changed_at)
          AND u.created_at<=oldc.changed_at AND oldc.changed_at<=c.changed_at AND c.changed_at<=u.updated_at
          AND a.actor_type='USER' AND a.actor_id=NEW.actor_id AND a.original_actor_id IS NULL
          AND a.actor_hint_digest IS NULL AND a.trace_id=NEW.trace_id
          AND a.event_scope='DEPLOYMENT' AND a.target_project_id IS NULL AND a.action='PASSWORD_RESET'
          AND a.outcome='SUCCESS' AND a.target_owner_module='auth' AND a.target_object_type='AUT-01'
          AND a.target_object_id=u.user_id AND a.target_version_id IS NULL AND a.reason_code IS NULL
          AND a.before_state='CREDENTIAL_V'||NEW.before_credential_version::text
          AND a.after_state='CREDENTIAL_V'||NEW.credential_version::text
          AND isfinite(a.occurred_at) AND u.updated_at<=a.occurred_at AND a.occurred_at<=NEW.accepted_at
          AND NEW.accepted_at<=statement_timestamp()
          AND NOT EXISTS(SELECT 1 FROM plm.auth_sessions s WHERE s.user_id=u.user_id AND s.revoked_at IS NULL)
          AND NEW.revoked_session_count=(SELECT count(*) FROM plm.auth_sessions s WHERE s.user_id=u.user_id
            AND s.revoked_at=u.updated_at AND s.revoke_reason='PASSWORD_RESET')
      ) THEN RAISE EXCEPTION 'Invalid password reset result source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_password_reset_result_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Password reset results are immutable'; END $$;
    CREATE TRIGGER trg_auth_reset_source BEFORE INSERT ON plm.auth_password_reset_results
      FOR EACH ROW EXECUTE FUNCTION plm.validate_password_reset_result();
    CREATE TRIGGER trg_auth_reset_immutable BEFORE UPDATE OR DELETE ON plm.auth_password_reset_results
      FOR EACH ROW EXECUTE FUNCTION plm.reject_password_reset_result_change();
    CREATE TRIGGER trg_auth_reset_truncate BEFORE TRUNCATE ON plm.auth_password_reset_results
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_password_reset_result_change();
    """)


def downgrade():
    op.execute("""LOCK TABLE plm.auth_password_reset_results IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.auth_password_reset_results)
      THEN RAISE EXCEPTION 'Cannot discard password reset history'; END IF; END $$;""")
    op.drop_table('auth_password_reset_results',schema='plm')
    op.execute('DROP FUNCTION plm.validate_password_reset_result()')
    op.execute('DROP FUNCTION plm.reject_password_reset_result_change()')
