"""CR-AUT-005: immutable Auth-owned first creation response; not replay authority."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision = '20260927_0046'
down_revision = '20260927_0045'
branch_labels = None
depends_on = None


def upgrade():
    ids = ('user_id','credential_id','actor_id','audit_event_id','trace_id')
    op.create_table('auth_user_create_results',
        *(sa.Column(c, UUID(as_uuid=True), nullable=False) for c in ids),
        *(sa.Column(c, sa.Text(), nullable=False) for c in ('username_display','account_state','deployment_role')),
        *(sa.Column(c, sa.BigInteger(), nullable=False) for c in ('credential_version','lock_version')),
        *(sa.Column(c, TIMESTAMP(timezone=True, precision=6), nullable=False) for c in ('created_at','updated_at')),
        sa.Column('accepted_at', TIMESTAMP(timezone=True, precision=6), nullable=False,
            server_default=sa.text('statement_timestamp()')),
        sa.PrimaryKeyConstraint('user_id', name='pk_auth_user_create_results'),
        sa.ForeignKeyConstraint(['user_id'], ['plm.auth_users.user_id'], name='fk_auth_create__user'),
        sa.ForeignKeyConstraint(['actor_id'], ['plm.auth_users.user_id'], name='fk_auth_create__actor'),
        sa.ForeignKeyConstraint(['credential_id','user_id','credential_version'],
            ['plm.auth_password_credentials.password_credential_id','plm.auth_password_credentials.user_id',
             'plm.auth_password_credentials.credential_version'], name='fk_auth_create__credential'),
        sa.ForeignKeyConstraint(['audit_event_id'], ['plm.aud_events.audit_event_id'], name='fk_auth_create__audit'),
        sa.UniqueConstraint('credential_id', name='uq_auth_create__credential'),
        sa.UniqueConstraint('audit_event_id', name='uq_auth_create__audit'),
        sa.CheckConstraint(' AND '.join(c+"<>'00000000-0000-0000-0000-000000000000'::uuid" for c in ids)
            + " AND user_id<>actor_id AND char_length(username_display) BETWEEN 1 AND 255"
            + " AND account_state='ENABLED' AND deployment_role='NONE' AND credential_version=1 AND lock_version=1"
            + " AND isfinite(created_at) AND isfinite(updated_at) AND isfinite(accepted_at)"
            + " AND created_at<=updated_at AND updated_at<=accepted_at", name='ck_auth_create__shape'),
        schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_user_create_result() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM 1 FROM plm.auth_users WHERE user_id=NEW.user_id FOR UPDATE;
      IF NOT EXISTS (
        SELECT 1 FROM plm.auth_users u
        JOIN plm.auth_password_credentials c ON c.password_credential_id=NEW.credential_id
        JOIN plm.aud_events a ON a.audit_event_id=NEW.audit_event_id
        WHERE u.user_id=NEW.user_id AND u.created_by=NEW.actor_id AND u.updated_by=NEW.actor_id
          AND u.state='ENABLED' AND u.deployment_role='NONE' AND u.credential_version=1 AND u.lock_version=1
          AND u.active_password_credential_id=c.password_credential_id
          AND u.username_display=NEW.username_display AND u.created_at=NEW.created_at AND u.updated_at=NEW.updated_at
          AND c.user_id=u.user_id AND c.credential_version=1 AND c.changed_by=NEW.actor_id
          AND c.must_change_password=false AND isfinite(c.changed_at)
          AND u.created_at<=c.changed_at AND c.changed_at<=u.updated_at
          AND a.actor_type='USER' AND a.actor_id=NEW.actor_id AND a.original_actor_id IS NULL
          AND a.actor_hint_digest IS NULL AND a.trace_id=NEW.trace_id
          AND a.event_scope='DEPLOYMENT' AND a.target_project_id IS NULL
          AND a.action='USER_CREATED' AND a.outcome='SUCCESS'
          AND a.target_owner_module='auth' AND a.target_object_type='AUT-01'
          AND a.target_object_id=u.user_id AND a.target_version_id IS NULL
          AND a.before_state IS NULL AND a.after_state='ENABLED' AND a.reason_code IS NULL
          AND isfinite(a.occurred_at) AND u.updated_at<=a.occurred_at AND a.occurred_at<=NEW.accepted_at
      ) THEN RAISE EXCEPTION 'Invalid User creation result source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_user_create_result_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'User creation results are immutable'; END $$;
    CREATE TRIGGER trg_auth_create_source BEFORE INSERT ON plm.auth_user_create_results
      FOR EACH ROW EXECUTE FUNCTION plm.validate_user_create_result();
    CREATE TRIGGER trg_auth_create_immutable BEFORE UPDATE OR DELETE ON plm.auth_user_create_results
      FOR EACH ROW EXECUTE FUNCTION plm.reject_user_create_result_change();
    CREATE TRIGGER trg_auth_create_truncate BEFORE TRUNCATE ON plm.auth_user_create_results
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_user_create_result_change();
    """)


def downgrade():
    op.execute("""LOCK TABLE plm.auth_user_create_results IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.auth_user_create_results)
      THEN RAISE EXCEPTION 'Cannot discard User creation result history'; END IF; END $$;""")
    op.drop_table('auth_user_create_results', schema='plm')
    op.execute('DROP FUNCTION plm.validate_user_create_result()')
    op.execute('DROP FUNCTION plm.reject_user_create_result_change()')
