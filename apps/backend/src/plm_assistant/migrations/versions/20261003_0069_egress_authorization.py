"""Egress authorization, revocation history, and immutable first results.

Revision ID: 20261003_0069
Revises: 20261003_0068
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20261003_0069"
down_revision = "20261003_0068"
branch_labels = None
depends_on = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"


def _nonzero(*columns: str) -> str:
    return " AND ".join(f"{column}<>{_ZERO}" for column in columns)


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)

    op.create_table(
        "ai_egress_authorizations",
        sa.Column("authorization_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("egress_preview_id", ident, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", ident),
        sa.Column("purpose_ref", sa.Text(), nullable=False),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("ai_provider_id", ident, nullable=False),
        sa.Column("provider_config_version_id", ident, nullable=False),
        sa.Column("ai_model_id", ident, nullable=False),
        sa.Column("data_region", sa.Text(), nullable=False),
        sa.Column("allowed_data_categories", postgresql.JSONB(), nullable=False),
        sa.Column("minimal_payload_policy_ref", sa.Text(), nullable=False),
        sa.Column("max_record_count", sa.BigInteger(), nullable=False),
        sa.Column("max_payload_bytes", sa.BigInteger(), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_retry_attempts", sa.Integer(), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("source_refs_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("authorization_state", sa.Text(), nullable=False,
                  server_default=sa.text("'AUTHORIZED'")),
        sa.Column("approved_by", ident, nullable=False),
        sa.Column("approved_role", sa.Text(), nullable=False),
        sa.Column("approved_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("valid_until", timestamp, nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"],
            name="fk_ai_egress_authorizations__preview", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_ai_egress_authorizations__project", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authorizations__approver", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["ai_model_id"], ["plm.ai_models.ai_model_id"],
            name="fk_ai_egress_authorizations__model", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_version_id", "ai_provider_id"],
            ["plm.ai_provider_config_versions.provider_config_version_id",
             "plm.ai_provider_config_versions.ai_provider_id"],
            name="fk_ai_egress_authorizations__provider_config", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("egress_preview_id", name="uq_ai_egress_authorizations__preview"),
        sa.CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL AND approved_role='DeploymentAdmin') OR "
            "(scope='PROJECT' AND project_id IS NOT NULL "
            "AND approved_role IN ('ProjectManager','CustomerManager'))",
            name="ck_ai_egress_authorizations__scope_role",
        ),
        sa.CheckConstraint(
            "authorization_state IN ('AUTHORIZED','REVOKED') AND lock_version BETWEEN 0 AND 1",
            name="ck_ai_egress_authorizations__state",
        ),
        sa.CheckConstraint(
            "purpose_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND minimal_payload_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND data_region ~ '^[a-z][a-z0-9-]{0,63}$' "
            "AND operation_type IN ('AI_TASK','RETRIEVAL_RUN','INDEX_BUILD','INDEX_REBUILD')",
            name="ck_ai_egress_authorizations__refs",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_data_categories)='array' "
            "AND jsonb_array_length(allowed_data_categories) BETWEEN 1 AND 64",
            name="ck_ai_egress_authorizations__categories",
        ),
        sa.CheckConstraint(
            "max_record_count BETWEEN 0 AND 1000000000 "
            "AND max_payload_bytes BETWEEN 1 AND 1073741824 "
            "AND max_input_tokens BETWEEN 1 AND 1048576 "
            "AND max_retry_attempts BETWEEN 1 AND 10",
            name="ck_ai_egress_authorizations__bounds",
        ),
        sa.CheckConstraint(
            "octet_length(payload_fingerprint)=32 AND octet_length(source_refs_fingerprint)=32",
            name="ck_ai_egress_authorizations__fingerprints",
        ),
        sa.CheckConstraint(
            _nonzero("authorization_id", "egress_preview_id", "ai_provider_id",
                     "provider_config_version_id", "ai_model_id", "approved_by"),
            name="ck_ai_egress_authorizations__uuid",
        ),
        sa.CheckConstraint(
            "approved_at<valid_until AND isfinite(approved_at) AND isfinite(valid_until) "
            "AND created_xid>0",
            name="ck_ai_egress_authorizations__time",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_ai_egress_authorizations__project_state_expiry",
        "ai_egress_authorizations",
        ["project_id", "authorization_state", "valid_until", "authorization_id"],
        schema="plm",
    )

    op.create_table(
        "ai_egress_authorization_revocations",
        sa.Column("revocation_id", ident, primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("authorization_id", ident, nullable=False),
        sa.Column("revoked_by", ident, nullable=False),
        sa.Column("revoked_role", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("revoked_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_authz_revocations__authorization", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authz_revocations__actor", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_authz_revocations__audit", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("authorization_id", name="uq_ai_egress_authz_revocations__authorization"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_egress_authz_revocations__audit"),
        sa.CheckConstraint(
            _nonzero("revocation_id", "authorization_id", "revoked_by", "audit_event_id", "trace_id")
            + " AND revoked_role IN ('OriginalApprover','DeploymentAdmin','ProjectManager','CustomerManager') "
              "AND reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$' "
              "AND char_length(reason_summary) BETWEEN 1 AND 2000 "
              "AND char_length(btrim(reason_summary))>0 "
              "AND isfinite(revoked_at) AND created_xid>0",
            name="ck_ai_egress_authz_revocations__shape",
        ),
        schema="plm",
    )

    op.create_table(
        "ai_egress_authorize_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("authorization_id", ident, nullable=False),
        sa.Column("egress_preview_id", ident, nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("approved_role", sa.Text(), nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("result_state", sa.Text(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("approved_at", timestamp, nullable=False),
        sa.Column("valid_until", timestamp, nullable=False),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_authorize_results__authorization", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["egress_preview_id"], ["plm.ai_egress_previews.egress_preview_id"],
            name="fk_ai_egress_authorize_results__preview", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_authorize_results__actor", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_authorize_results__audit", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("authorization_id", name="uq_ai_egress_authorize_results__authorization"),
        sa.UniqueConstraint("egress_preview_id", name="uq_ai_egress_authorize_results__preview"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_egress_authorize_results__audit"),
        sa.CheckConstraint(
            _nonzero("result_id", "authorization_id", "egress_preview_id", "actor_id",
                     "audit_event_id", "trace_id")
            + " AND approved_role IN ('DeploymentAdmin','ProjectManager','CustomerManager') "
              "AND result_state='AUTHORIZED' AND lock_version=0 "
              "AND approved_at<valid_until AND isfinite(approved_at) AND isfinite(valid_until) "
              "AND created_xid>0",
            name="ck_ai_egress_authorize_results__shape",
        ),
        schema="plm",
    )

    op.create_table(
        "ai_egress_revoke_results",
        sa.Column("result_id", ident, primary_key=True),
        sa.Column("authorization_id", ident, nullable=False),
        sa.Column("revocation_id", ident, nullable=False),
        sa.Column("actor_id", ident, nullable=False),
        sa.Column("revoked_role", sa.Text(), nullable=False),
        sa.Column("audit_event_id", ident, nullable=False),
        sa.Column("trace_id", ident, nullable=False),
        sa.Column("result_state", sa.Text(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", timestamp, nullable=False),
        sa.Column("created_xid", sa.BigInteger(), nullable=False,
                  server_default=sa.text("txid_current()")),
        sa.ForeignKeyConstraint(
            ["authorization_id"], ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_ai_egress_revoke_results__authorization", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["revocation_id"], ["plm.ai_egress_authorization_revocations.revocation_id"],
            name="fk_ai_egress_revoke_results__revocation", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["plm.auth_users.user_id"],
            name="fk_ai_egress_revoke_results__actor", ondelete="NO ACTION",
        ),
        sa.ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_ai_egress_revoke_results__audit", ondelete="NO ACTION",
        ),
        sa.UniqueConstraint("authorization_id", name="uq_ai_egress_revoke_results__authorization"),
        sa.UniqueConstraint("revocation_id", name="uq_ai_egress_revoke_results__revocation"),
        sa.UniqueConstraint("audit_event_id", name="uq_ai_egress_revoke_results__audit"),
        sa.CheckConstraint(
            _nonzero("result_id", "authorization_id", "revocation_id", "actor_id",
                     "audit_event_id", "trace_id")
            + " AND revoked_role IN ('OriginalApprover','DeploymentAdmin','ProjectManager','CustomerManager') "
              "AND result_state='REVOKED' AND lock_version=1 "
              "AND isfinite(revoked_at) AND created_xid>0",
            name="ck_ai_egress_revoke_results__shape",
        ),
        schema="plm",
    )

    op.execute(r"""
        CREATE FUNCTION plm.guard_ai_egress_authorization()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            preview plm.ai_egress_previews%ROWTYPE;
            provider_state text;
            current_config uuid;
            model_state text;
            category jsonb;
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'AI egress authorization history is immutable';
            ELSIF TG_OP='UPDATE' THEN
                IF OLD.authorization_state<>'AUTHORIZED' OR NEW.authorization_state<>'REVOKED'
                   OR NEW.lock_version<>OLD.lock_version+1
                   OR ROW(NEW.egress_preview_id,NEW.scope,NEW.project_id,NEW.purpose_ref,
                          NEW.operation_type,NEW.ai_provider_id,NEW.provider_config_version_id,
                          NEW.ai_model_id,NEW.data_region,NEW.allowed_data_categories,
                          NEW.minimal_payload_policy_ref,NEW.max_record_count,
                          NEW.max_payload_bytes,NEW.max_input_tokens,NEW.max_retry_attempts,
                          NEW.payload_fingerprint,NEW.source_refs_fingerprint,NEW.approved_by,
                          NEW.approved_role,NEW.approved_at,NEW.valid_until,NEW.created_xid)
                      IS DISTINCT FROM
                      ROW(OLD.egress_preview_id,OLD.scope,OLD.project_id,OLD.purpose_ref,
                          OLD.operation_type,OLD.ai_provider_id,OLD.provider_config_version_id,
                          OLD.ai_model_id,OLD.data_region,OLD.allowed_data_categories,
                          OLD.minimal_payload_policy_ref,OLD.max_record_count,
                          OLD.max_payload_bytes,OLD.max_input_tokens,OLD.max_retry_attempts,
                          OLD.payload_fingerprint,OLD.source_refs_fingerprint,OLD.approved_by,
                          OLD.approved_role,OLD.approved_at,OLD.valid_until,OLD.created_xid)
                THEN
                    RAISE EXCEPTION 'AI egress authorization transition is invalid';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.authorization_state<>'AUTHORIZED' OR NEW.lock_version<>0 THEN
                RAISE EXCEPTION 'AI egress authorization must start AUTHORIZED at version zero';
            END IF;
            SELECT * INTO preview FROM plm.ai_egress_previews
             WHERE egress_preview_id=NEW.egress_preview_id FOR KEY SHARE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'AI egress authorization preview is missing';
            END IF;
            IF ROW(NEW.scope,NEW.project_id,NEW.purpose_ref,NEW.operation_type,
                   NEW.ai_provider_id,NEW.provider_config_version_id,NEW.ai_model_id,
                   NEW.data_region,NEW.minimal_payload_policy_ref,NEW.payload_fingerprint,
                   NEW.source_refs_fingerprint)
               IS DISTINCT FROM
               ROW(preview.scope,preview.project_id,preview.purpose_ref,preview.operation_type,
                   preview.ai_provider_id,preview.provider_config_version_id,preview.ai_model_id,
                   preview.data_region,preview.minimal_payload_policy_ref,
                   preview.payload_fingerprint,preview.source_refs_fingerprint)
               OR NOT (NEW.allowed_data_categories <@ preview.allowed_data_categories)
               OR NEW.max_record_count>preview.estimated_record_count
               OR NEW.max_payload_bytes>preview.max_payload_bytes
               OR NEW.max_input_tokens>preview.max_input_tokens
               OR NEW.max_retry_attempts>preview.max_retry_attempts
               OR NEW.approved_at<preview.created_at
               OR NEW.approved_at<transaction_timestamp()
               OR NEW.approved_at>statement_timestamp()
               OR NEW.valid_until<=statement_timestamp()
               OR NEW.valid_until>preview.expires_at
               OR NOT EXISTS (
                    SELECT 1 FROM plm.ai_egress_preview_source_refs
                     WHERE egress_preview_id=NEW.egress_preview_id
               )
            THEN
                RAISE EXCEPTION 'AI egress authorization exceeds or mismatches preview';
            END IF;
            SELECT p.provider_state,p.current_config_version_ref
              INTO provider_state,current_config
              FROM plm.ai_providers p WHERE p.ai_provider_id=NEW.ai_provider_id FOR KEY SHARE;
            SELECT m.model_state INTO model_state FROM plm.ai_models m
             WHERE m.ai_model_id=NEW.ai_model_id AND m.ai_provider_id=NEW.ai_provider_id
             FOR KEY SHARE;
            IF provider_state IS DISTINCT FROM 'ACTIVE'
               OR current_config IS DISTINCT FROM NEW.provider_config_version_id
               OR model_state IS DISTINCT FROM 'AVAILABLE'
            THEN
                RAISE EXCEPTION 'AI egress authorization provider route is unavailable';
            END IF;
            FOR category IN SELECT value FROM jsonb_array_elements(NEW.allowed_data_categories)
            LOOP
                IF jsonb_typeof(category)<>'string' OR length(btrim(category#>>'{}'))=0
                   OR length(category#>>'{}')>64 THEN
                    RAISE EXCEPTION 'AI egress authorization category is invalid';
                END IF;
            END LOOP;
            IF (SELECT count(*)<>count(DISTINCT value)
                  FROM jsonb_array_elements(NEW.allowed_data_categories)) THEN
                RAISE EXCEPTION 'AI egress authorization category is duplicated';
            END IF;
            RETURN NEW;
        END; $$;

        CREATE TRIGGER trg_ai_egress_authorization_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_egress_authorizations
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_egress_authorization();

        CREATE FUNCTION plm.guard_ai_egress_revocation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE auth_row plm.ai_egress_authorizations%ROWTYPE;
        BEGIN
            IF TG_OP<>'INSERT' THEN
                RAISE EXCEPTION 'AI egress revocation history is immutable';
            END IF;
            SELECT * INTO auth_row FROM plm.ai_egress_authorizations
             WHERE authorization_id=NEW.authorization_id FOR KEY SHARE;
            IF NOT FOUND OR auth_row.authorization_state<>'AUTHORIZED'
               OR NEW.revoked_at<auth_row.approved_at
               OR NOT (
                    (auth_row.scope='GLOBAL' AND
                     (NEW.revoked_role='OriginalApprover'
                      AND NEW.revoked_by=auth_row.approved_by
                      OR NEW.revoked_role='DeploymentAdmin'))
                    OR
                    (auth_row.scope='PROJECT' AND
                     (NEW.revoked_role='OriginalApprover'
                      AND NEW.revoked_by=auth_row.approved_by
                      OR NEW.revoked_role IN ('ProjectManager','CustomerManager')))
               )
            THEN
                RAISE EXCEPTION 'AI egress revocation authority is invalid';
            END IF;
            RETURN NEW;
        END; $$;

        CREATE TRIGGER trg_ai_egress_revocation_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_egress_authorization_revocations
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_egress_revocation();

        CREATE FUNCTION plm.guard_ai_egress_authorize_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE auth_row plm.ai_egress_authorizations%ROWTYPE;
        BEGIN
            IF TG_OP<>'INSERT' THEN
                RAISE EXCEPTION 'AI egress authorize result history is immutable';
            END IF;
            SELECT * INTO auth_row FROM plm.ai_egress_authorizations
             WHERE authorization_id=NEW.authorization_id FOR KEY SHARE;
            IF NOT FOUND OR auth_row.authorization_state<>'AUTHORIZED'
               OR auth_row.lock_version<>0
               OR ROW(NEW.egress_preview_id,NEW.actor_id,NEW.approved_role,
                      NEW.result_state,NEW.lock_version,NEW.approved_at,NEW.valid_until)
                  IS DISTINCT FROM
                  ROW(auth_row.egress_preview_id,auth_row.approved_by,
                      auth_row.approved_role,auth_row.authorization_state,
                      auth_row.lock_version,auth_row.approved_at,
                      auth_row.valid_until)
            THEN
                RAISE EXCEPTION 'AI egress authorize result does not match authorization';
            END IF;
            RETURN NEW;
        END; $$;

        CREATE TRIGGER trg_ai_egress_authorize_result_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_egress_authorize_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_egress_authorize_result();

        CREATE FUNCTION plm.guard_ai_egress_revoke_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            auth_row plm.ai_egress_authorizations%ROWTYPE;
            revoke_row plm.ai_egress_authorization_revocations%ROWTYPE;
        BEGIN
            IF TG_OP<>'INSERT' THEN
                RAISE EXCEPTION 'AI egress revoke result history is immutable';
            END IF;
            SELECT * INTO auth_row FROM plm.ai_egress_authorizations
             WHERE authorization_id=NEW.authorization_id FOR KEY SHARE;
            SELECT * INTO revoke_row FROM plm.ai_egress_authorization_revocations
             WHERE revocation_id=NEW.revocation_id
               AND authorization_id=NEW.authorization_id FOR KEY SHARE;
            IF auth_row.authorization_state IS DISTINCT FROM 'REVOKED'
               OR auth_row.lock_version IS DISTINCT FROM 1
               OR revoke_row.revocation_id IS NULL
               OR ROW(NEW.actor_id,NEW.revoked_role,NEW.audit_event_id,NEW.trace_id,
                      NEW.result_state,NEW.lock_version,NEW.revoked_at)
                  IS DISTINCT FROM
                  ROW(revoke_row.revoked_by,revoke_row.revoked_role,
                      revoke_row.audit_event_id,revoke_row.trace_id,
                      auth_row.authorization_state,auth_row.lock_version,
                      revoke_row.revoked_at)
            THEN
                RAISE EXCEPTION 'AI egress revoke result does not match revocation';
            END IF;
            RETURN NEW;
        END; $$;

        CREATE TRIGGER trg_ai_egress_revoke_result_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plm.ai_egress_revoke_results
        FOR EACH ROW EXECUTE FUNCTION plm.guard_ai_egress_revoke_result();

        CREATE FUNCTION plm.assert_ai_egress_authorization_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_id uuid;
            current_state text;
            authorize_count integer;
            revocation_count integer;
            revoke_count integer;
        BEGIN
            target_id:=NEW.authorization_id;
            SELECT authorization_state INTO current_state
              FROM plm.ai_egress_authorizations WHERE authorization_id=target_id;
            IF NOT FOUND THEN RETURN NULL; END IF;
            SELECT count(*) INTO authorize_count FROM plm.ai_egress_authorize_results
             WHERE authorization_id=target_id;
            SELECT count(*) INTO revocation_count FROM plm.ai_egress_authorization_revocations
             WHERE authorization_id=target_id;
            SELECT count(*) INTO revoke_count FROM plm.ai_egress_revoke_results
             WHERE authorization_id=target_id;
            IF authorize_count<>1
               OR (current_state='AUTHORIZED' AND (revocation_count<>0 OR revoke_count<>0))
               OR (current_state='REVOKED' AND (revocation_count<>1 OR revoke_count<>1))
            THEN
                RAISE EXCEPTION 'AI egress authorization history is incomplete';
            END IF;
            RETURN NULL;
        END; $$;

        CREATE CONSTRAINT TRIGGER trg_ai_egress_authz_history_root
        AFTER INSERT OR UPDATE ON plm.ai_egress_authorizations
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.assert_ai_egress_authorization_history();
        CREATE CONSTRAINT TRIGGER trg_ai_egress_authz_history_authorize_result
        AFTER INSERT ON plm.ai_egress_authorize_results
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.assert_ai_egress_authorization_history();
        CREATE CONSTRAINT TRIGGER trg_ai_egress_authz_history_revocation
        AFTER INSERT ON plm.ai_egress_authorization_revocations
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.assert_ai_egress_authorization_history();
        CREATE CONSTRAINT TRIGGER trg_ai_egress_authz_history_revoke_result
        AFTER INSERT ON plm.ai_egress_revoke_results
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
        EXECUTE FUNCTION plm.assert_ai_egress_authorization_history();

        CREATE FUNCTION plm.guard_ai_egress_authorization_truncate()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'AI egress authorization history cannot be truncated'; END; $$;
        CREATE TRIGGER trg_ai_egress_authorization_truncate
        BEFORE TRUNCATE ON plm.ai_egress_authorizations
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_egress_authorization_truncate();
        CREATE TRIGGER trg_ai_egress_revocation_truncate
        BEFORE TRUNCATE ON plm.ai_egress_authorization_revocations
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_egress_authorization_truncate();
        CREATE TRIGGER trg_ai_egress_authorize_result_truncate
        BEFORE TRUNCATE ON plm.ai_egress_authorize_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_egress_authorization_truncate();
        CREATE TRIGGER trg_ai_egress_revoke_result_truncate
        BEFORE TRUNCATE ON plm.ai_egress_revoke_results
        FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_ai_egress_authorization_truncate();
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline AI egress authorization downgrade is disabled")
    tables = (
        "ai_egress_revoke_results",
        "ai_egress_authorize_results",
        "ai_egress_authorization_revocations",
        "ai_egress_authorizations",
    )
    op.execute("LOCK TABLE " + ",".join("plm." + table for table in tables)
               + " IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$ BEGIN
            IF EXISTS(SELECT 1 FROM plm.ai_egress_authorizations)
               OR EXISTS(SELECT 1 FROM plm.ai_egress_authorization_revocations)
               OR EXISTS(SELECT 1 FROM plm.ai_egress_authorize_results)
               OR EXISTS(SELECT 1 FROM plm.ai_egress_revoke_results)
            THEN RAISE EXCEPTION 'AI egress authorization history prevents downgrade';
            END IF;
        END $$;
    """)
    trigger_tables = (
        ("ai_egress_revoke_results", "trg_ai_egress_revoke_result_truncate"),
        ("ai_egress_authorize_results", "trg_ai_egress_authorize_result_truncate"),
        ("ai_egress_authorization_revocations", "trg_ai_egress_revocation_truncate"),
        ("ai_egress_authorizations", "trg_ai_egress_authorization_truncate"),
        ("ai_egress_revoke_results", "trg_ai_egress_authz_history_revoke_result"),
        ("ai_egress_authorization_revocations", "trg_ai_egress_authz_history_revocation"),
        ("ai_egress_authorize_results", "trg_ai_egress_authz_history_authorize_result"),
        ("ai_egress_authorizations", "trg_ai_egress_authz_history_root"),
        ("ai_egress_revoke_results", "trg_ai_egress_revoke_result_guard"),
        ("ai_egress_authorize_results", "trg_ai_egress_authorize_result_guard"),
        ("ai_egress_authorization_revocations", "trg_ai_egress_revocation_guard"),
        ("ai_egress_authorizations", "trg_ai_egress_authorization_guard"),
    )
    for table, trigger in trigger_tables:
        op.execute(f"DROP TRIGGER {trigger} ON plm.{table}")
    op.execute("DROP FUNCTION plm.guard_ai_egress_authorization_truncate()")
    op.execute("DROP FUNCTION plm.assert_ai_egress_authorization_history()")
    op.execute("DROP FUNCTION plm.guard_ai_egress_revoke_result()")
    op.execute("DROP FUNCTION plm.guard_ai_egress_authorize_result()")
    op.execute("DROP FUNCTION plm.guard_ai_egress_revocation()")
    op.execute("DROP FUNCTION plm.guard_ai_egress_authorization()")
    for table in tables:
        if table == "ai_egress_authorizations":
            op.drop_index(
                "ix_ai_egress_authorizations__project_state_expiry",
                table_name=table, schema="plm",
            )
        op.drop_table(table, schema="plm")
