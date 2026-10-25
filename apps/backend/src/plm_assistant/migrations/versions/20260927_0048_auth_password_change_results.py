"""CR-AUT-007: immutable before/after credential password-change result."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision='20260927_0048'
down_revision='20260927_0047'
branch_labels=None
depends_on=None


def upgrade():
    ids=('result_id','user_id','before_credential_id','credential_id','audit_event_id','trace_id')
    op.create_table('auth_password_change_results',
        *(sa.Column(c,UUID(as_uuid=True),nullable=False) for c in ids),
        *(sa.Column(c,sa.BigInteger(),nullable=False) for c in ('before_credential_version','credential_version',
            'before_user_version','user_version','revoked_session_count')),
        sa.Column('changed_at',TIMESTAMP(timezone=True,precision=6),nullable=False),
        sa.Column('accepted_at',TIMESTAMP(timezone=True,precision=6),nullable=False,server_default=sa.text('statement_timestamp()')),
        sa.PrimaryKeyConstraint('result_id',name='pk_auth_password_change_results'),
        sa.ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_change__user'),
        sa.ForeignKeyConstraint(['before_credential_id','user_id','before_credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_change__before'),
        sa.ForeignKeyConstraint(['credential_id','user_id','credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'],name='fk_auth_change__after'),
        sa.ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_change__audit'),
        sa.UniqueConstraint('user_id','credential_version',name='uq_auth_change__credential'),
        sa.UniqueConstraint('user_id','user_version',name='uq_auth_change__user_version'),
        sa.UniqueConstraint('audit_event_id',name='uq_auth_change__audit'),
        sa.CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in ids)
            + ' AND before_credential_id<>credential_id'
            + ' AND before_credential_version BETWEEN 1 AND 9223372036854775806'
            + ' AND credential_version>1 AND credential_version-1=before_credential_version'
            + ' AND before_user_version BETWEEN 0 AND 9223372036854775806'
            + ' AND user_version>0 AND user_version-1=before_user_version AND revoked_session_count>0'
            + ' AND isfinite(changed_at) AND isfinite(accepted_at) AND changed_at<=accepted_at',name='ck_auth_change__shape'),
        schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_password_change_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM 1 FROM plm.auth_users WHERE user_id=NEW.user_id FOR UPDATE;
      IF NOT EXISTS(
        SELECT 1 FROM plm.auth_users u
        JOIN plm.auth_password_credentials oldc ON oldc.password_credential_id=NEW.before_credential_id
          AND oldc.user_id=u.user_id AND oldc.credential_version=NEW.before_credential_version
        JOIN plm.auth_password_credentials c ON c.password_credential_id=NEW.credential_id
          AND c.user_id=u.user_id AND c.credential_version=NEW.credential_version
        JOIN plm.aud_events a ON a.audit_event_id=NEW.audit_event_id
        WHERE u.user_id=NEW.user_id AND u.state='ENABLED' AND u.updated_by=u.user_id
          AND u.active_password_credential_id=c.password_credential_id
          AND u.credential_version=c.credential_version AND u.lock_version=NEW.user_version
          AND u.updated_at=NEW.changed_at AND c.must_change_password=false AND c.changed_by=u.user_id
          AND isfinite(oldc.changed_at) AND isfinite(c.changed_at)
          AND u.created_at<=oldc.changed_at AND oldc.changed_at<=c.changed_at AND c.changed_at<=u.updated_at
          AND a.actor_type='USER' AND a.actor_id=u.user_id AND a.original_actor_id IS NULL
          AND a.actor_hint_digest IS NULL AND a.trace_id=NEW.trace_id
          AND a.event_scope='DEPLOYMENT' AND a.target_project_id IS NULL AND a.action='PASSWORD_CHANGED'
          AND a.outcome='SUCCESS' AND a.target_owner_module='auth' AND a.target_object_type='AUT-01'
          AND a.target_object_id=u.user_id AND a.target_version_id IS NULL AND a.reason_code IS NULL
          AND a.before_state='CREDENTIAL_V'||NEW.before_credential_version::text
          AND a.after_state='CREDENTIAL_V'||NEW.credential_version::text
          AND isfinite(a.occurred_at) AND u.updated_at<=a.occurred_at AND a.occurred_at<=NEW.accepted_at
          AND NEW.accepted_at<=statement_timestamp()
          AND NOT EXISTS(SELECT 1 FROM plm.auth_sessions s WHERE s.user_id=u.user_id AND s.revoked_at IS NULL)
          AND NEW.revoked_session_count=(SELECT count(*) FROM plm.auth_sessions s WHERE s.user_id=u.user_id
            AND s.revoked_at=u.updated_at AND s.revoke_reason='PASSWORD_CHANGED')
      ) THEN RAISE EXCEPTION 'Invalid password change result source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_password_change_result_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Password change results are immutable'; END $$;
    CREATE TRIGGER trg_auth_change_source BEFORE INSERT ON plm.auth_password_change_results
      FOR EACH ROW EXECUTE FUNCTION plm.validate_password_change_result();
    CREATE TRIGGER trg_auth_change_immutable BEFORE UPDATE OR DELETE ON plm.auth_password_change_results
      FOR EACH ROW EXECUTE FUNCTION plm.reject_password_change_result_change();
    CREATE TRIGGER trg_auth_change_truncate BEFORE TRUNCATE ON plm.auth_password_change_results
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_password_change_result_change();
    """)


def downgrade():
    op.execute("""LOCK TABLE plm.auth_password_change_results IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.auth_password_change_results)
      THEN RAISE EXCEPTION 'Cannot discard password change history'; END IF; END $$;""")
    op.drop_table('auth_password_change_results',schema='plm')
    op.execute('DROP FUNCTION plm.validate_password_change_result()')
    op.execute('DROP FUNCTION plm.reject_password_change_result_change()')
