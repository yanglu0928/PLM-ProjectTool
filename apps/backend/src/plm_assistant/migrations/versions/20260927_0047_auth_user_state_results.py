"""CR-AUT-006: immutable first enable/disable result, not replay authority."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision='20260927_0047'
down_revision='20260927_0046'
branch_labels=None
depends_on=None


def upgrade():
    ids=('result_id','user_id','actor_id','audit_event_id','trace_id')
    op.create_table('auth_user_state_results',
        *(sa.Column(c,UUID(as_uuid=True),nullable=False) for c in ids),
        *(sa.Column(c,sa.Text(),nullable=False) for c in ('operation','username_display','account_state','deployment_role')),
        *(sa.Column(c,sa.BigInteger(),nullable=False) for c in ('expected_version','credential_version','lock_version','revoked_session_count')),
        *(sa.Column(c,TIMESTAMP(timezone=True,precision=6),nullable=False) for c in ('created_at','updated_at')),
        sa.Column('accepted_at',TIMESTAMP(timezone=True,precision=6),nullable=False,server_default=sa.text('statement_timestamp()')),
        sa.PrimaryKeyConstraint('result_id',name='pk_auth_user_state_results'),
        sa.ForeignKeyConstraint(['user_id'],['plm.auth_users.user_id'],name='fk_auth_state__user'),
        sa.ForeignKeyConstraint(['actor_id'],['plm.auth_users.user_id'],name='fk_auth_state__actor'),
        sa.ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_auth_state__audit'),
        sa.UniqueConstraint('user_id','lock_version',name='uq_auth_state__user_version'),
        sa.UniqueConstraint('audit_event_id',name='uq_auth_state__audit'),
        sa.CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in ids)
            + " AND char_length(username_display) BETWEEN 1 AND 255"
            + " AND deployment_role IN ('NONE','DEPLOYMENT_ADMIN') AND credential_version>0"
            + " AND expected_version BETWEEN 0 AND 9223372036854775806 AND lock_version>0"
            + " AND lock_version-1=expected_version AND revoked_session_count>=0"
            + " AND ((operation='ENABLE' AND account_state='ENABLED' AND revoked_session_count=0)"
            + " OR (operation='DISABLE' AND account_state='DISABLED'))"
            + " AND isfinite(created_at) AND isfinite(updated_at) AND isfinite(accepted_at)"
            + " AND created_at<=updated_at AND updated_at<=accepted_at",name='ck_auth_state__shape'),schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_user_state_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM 1 FROM plm.auth_users WHERE user_id=NEW.user_id FOR UPDATE;
      IF NOT EXISTS (
        SELECT 1 FROM plm.auth_users u
        JOIN plm.auth_password_credentials c ON c.password_credential_id=u.active_password_credential_id
          AND c.user_id=u.user_id AND c.credential_version=u.credential_version
        JOIN plm.aud_events a ON a.audit_event_id=NEW.audit_event_id
        WHERE u.user_id=NEW.user_id AND u.updated_by=NEW.actor_id
          AND u.state=NEW.account_state AND u.deployment_role=NEW.deployment_role
          AND u.username_display=NEW.username_display AND u.credential_version=NEW.credential_version
          AND u.lock_version=NEW.lock_version AND u.created_at=NEW.created_at AND u.updated_at=NEW.updated_at
          AND a.actor_type='USER' AND a.actor_id=NEW.actor_id AND a.original_actor_id IS NULL
          AND a.actor_hint_digest IS NULL AND a.trace_id=NEW.trace_id
          AND a.event_scope='DEPLOYMENT' AND a.target_project_id IS NULL
          AND a.action=CASE NEW.operation WHEN 'ENABLE' THEN 'USER_ENABLED' ELSE 'USER_DISABLED' END
          AND a.outcome='SUCCESS' AND a.target_owner_module='auth' AND a.target_object_type='AUT-01'
          AND a.target_object_id=u.user_id AND a.target_version_id IS NULL AND a.reason_code IS NULL
          AND a.before_state=CASE NEW.operation WHEN 'ENABLE' THEN 'DISABLED' ELSE 'ENABLED' END
          AND a.after_state=NEW.account_state
          AND isfinite(a.occurred_at) AND u.updated_at<=a.occurred_at AND a.occurred_at<=NEW.accepted_at
          AND NEW.accepted_at<=statement_timestamp()
          AND (NEW.operation='ENABLE' OR (
            NOT EXISTS(SELECT 1 FROM plm.auth_sessions s WHERE s.user_id=u.user_id AND s.revoked_at IS NULL)
            AND NEW.revoked_session_count=(SELECT count(*) FROM plm.auth_sessions s
              WHERE s.user_id=u.user_id AND s.revoked_at=u.updated_at AND s.revoke_reason='USER_DISABLED')
          ))
      ) THEN RAISE EXCEPTION 'Invalid User state result source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_user_state_result_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'User state results are immutable'; END $$;
    CREATE TRIGGER trg_auth_state_source BEFORE INSERT ON plm.auth_user_state_results
      FOR EACH ROW EXECUTE FUNCTION plm.validate_user_state_result();
    CREATE TRIGGER trg_auth_state_immutable BEFORE UPDATE OR DELETE ON plm.auth_user_state_results
      FOR EACH ROW EXECUTE FUNCTION plm.reject_user_state_result_change();
    CREATE TRIGGER trg_auth_state_truncate BEFORE TRUNCATE ON plm.auth_user_state_results
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_user_state_result_change();
    """)


def downgrade():
    op.execute("""LOCK TABLE plm.auth_user_state_results IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.auth_user_state_results)
      THEN RAISE EXCEPTION 'Cannot discard User state result history'; END IF; END $$;""")
    op.drop_table('auth_user_state_results',schema='plm')
    op.execute('DROP FUNCTION plm.validate_user_state_result()')
    op.execute('DROP FUNCTION plm.reject_user_state_result_change()')
