"""Disposable PostgreSQL 18 proof for Schema0069 egress authorization history."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261003_0068"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name, autocommit=True, connect_timeout=5,
    )


def config(name: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    ))


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid egress authorization operation accepted")


PREVIEW_INSERT = (
    "INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,"
    "ai_provider_id,provider_config_version_id,ai_model_id,data_region,allowed_data_categories,"
    "minimal_payload_policy_ref,estimated_record_count,max_payload_bytes,max_input_tokens,"
    "max_retry_attempts,payload_fingerprint,source_refs_fingerprint,risk_codes,created_by,"
    "trace_id,expires_at) VALUES ('PROJECT',%s,'gap.analysis.v1','AI_TASK',%s,%s,%s,"
    "'cn-beijing',%s,'minimum.document.text.v1',2,65536,4096,3,%s,%s,%s,%s,%s,"
    "statement_timestamp()+interval '2 hours') RETURNING egress_preview_id"
)

AUTHORIZATION_INSERT = (
    "INSERT INTO plm.ai_egress_authorizations(egress_preview_id,scope,project_id,purpose_ref,"
    "operation_type,ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
    "allowed_data_categories,minimal_payload_policy_ref,max_record_count,max_payload_bytes,"
    "max_input_tokens,max_retry_attempts,payload_fingerprint,source_refs_fingerprint,"
    "approved_by,approved_role,valid_until) VALUES (%s,'PROJECT',%s,'gap.analysis.v1',"
    "'AI_TASK',%s,%s,%s,'cn-beijing',%s,'minimum.document.text.v1',2,65536,4096,3,"
    "%s,%s,%s,%s,statement_timestamp()+interval '1 hour') "
    "RETURNING authorization_id,approved_at,valid_until"
)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    empty = f"ai04a04p03_{suffix}_empty"
    data = f"ai04a04p03_{suffix}_data"
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in (empty, data):
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty_config = config(empty)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            command.downgrade(empty_config, PREVIOUS)
            command.upgrade(empty_config, "head")

            data_config = config(data)
            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Egress Approver','egress approver') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGAUTH1','egauth1','Egress Authorization',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                provider, provider_config = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
                        "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
                        (provider, provider_config, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
                        "ai_provider_id,config_version_no,provider_kind,display_name,"
                        "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,"
                        "can_structured_output,can_embedding,can_rerank,created_by) VALUES "
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Authorization Provider',"
                        "'endpoint.authorization.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
                        "true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-authorization','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]

                def create_preview() -> uuid.UUID:
                    preview = db.execute(
                        PREVIEW_INSERT,
                        (project, provider, provider_config, model,
                         Jsonb(["TECHNICAL_DOCUMENT", "SURVEY_RECORD"]), b"p" * 32,
                         b"s" * 32, Jsonb(["EXTERNAL_PROVIDER"]), actor, uuid.uuid4()),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,"
                        "ref_ordinal,resource_type,owner_module,object_type,object_id,version_id,"
                        "scope,project_id) VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',"
                        "%s,%s,'PROJECT',%s)",
                        (preview, uuid.uuid4(), uuid.uuid4(), project),
                    )
                    return preview

                first_preview = create_preview()

            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                def audit(action: str, trace: uuid.UUID, target: uuid.UUID) -> uuid.UUID:
                    return db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                        "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
                        "target_object_id) VALUES (%s,'PROJECT',%s,'USER',%s,%s,'SUCCESS',"
                        "'ai','AI-04',%s) RETURNING audit_event_id",
                        (trace, project, actor, action, target),
                    ).fetchone()[0]

                def create_preview() -> uuid.UUID:
                    preview = db.execute(
                        PREVIEW_INSERT,
                        (project, provider, provider_config, model,
                         Jsonb(["TECHNICAL_DOCUMENT", "SURVEY_RECORD"]), b"p" * 32,
                         b"s" * 32, Jsonb(["EXTERNAL_PROVIDER"]), actor, uuid.uuid4()),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,"
                        "ref_ordinal,resource_type,owner_module,object_type,object_id,version_id,"
                        "scope,project_id) VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',"
                        "%s,%s,'PROJECT',%s)",
                        (preview, uuid.uuid4(), uuid.uuid4(), project),
                    )
                    return preview

                def authorize(preview: uuid.UUID) -> tuple:
                    trace = uuid.uuid4()
                    with db.transaction():
                        audit_id = audit("AI_EGRESS_AUTHORIZE", trace, preview)
                        row = db.execute(
                            AUTHORIZATION_INSERT,
                            (preview, project, provider, provider_config, model,
                             Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, b"s" * 32,
                             actor, "ProjectManager"),
                        ).fetchone()
                        result_id = uuid.uuid4()
                        db.execute(
                            "INSERT INTO plm.ai_egress_authorize_results(result_id,authorization_id,"
                            "egress_preview_id,actor_id,approved_role,audit_event_id,trace_id,"
                            "result_state,lock_version,approved_at,valid_until) VALUES "
                            "(%s,%s,%s,%s,'ProjectManager',%s,%s,'AUTHORIZED',0,%s,%s)",
                            (result_id, row[0], preview, actor, audit_id, trace, row[1], row[2]),
                        )
                    return row[0], result_id, row[1], row[2]

                authorization, authorize_result, approved_at, valid_until = authorize(first_preview)
                assert db.execute(
                    "SELECT authorization_state,lock_version FROM plm.ai_egress_authorizations "
                    "WHERE authorization_id=%s", (authorization,),
                ).fetchone() == ("AUTHORIZED", 0)

                missing_result_preview = create_preview()
                reject(
                    db, AUTHORIZATION_INSERT,
                    (missing_result_preview, project, provider, provider_config, model,
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, b"s" * 32,
                     actor, "ProjectManager"),
                )
                widened_preview = create_preview()
                reject(
                    db, AUTHORIZATION_INSERT.replace("2,65536,4096,3", "2,65537,4096,3"),
                    (widened_preview, project, provider, provider_config, model,
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, b"s" * 32,
                     actor, "ProjectManager"),
                )
                wrong_role_preview = create_preview()
                reject(
                    db, AUTHORIZATION_INSERT,
                    (wrong_role_preview, project, provider, provider_config, model,
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, b"s" * 32,
                     actor, "ImplementationMember"),
                )
                backdated_preview = create_preview()
                backdated_insert = AUTHORIZATION_INSERT.replace(
                    "approved_by,approved_role,valid_until)",
                    "approved_by,approved_role,approved_at,valid_until)",
                ).replace(
                    "%s,%s,statement_timestamp()+interval '1 hour')",
                    "%s,%s,statement_timestamp()-interval '1 minute',"
                    "statement_timestamp()+interval '1 hour')",
                )
                reject(
                    db, backdated_insert,
                    (backdated_preview, project, provider, provider_config, model,
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, b"s" * 32,
                     actor, "ProjectManager"),
                )

                second_authorization, _, _, _ = authorize(create_preview())
                reject(
                    db,
                    "UPDATE plm.ai_egress_authorizations SET authorization_state='REVOKED',"
                    "lock_version=1 WHERE authorization_id=%s",
                    (second_authorization,),
                )

                event_only_trace = uuid.uuid4()
                event_only_audit = audit("AI_EGRESS_REVOKE", event_only_trace, second_authorization)
                reject(
                    db,
                    "INSERT INTO plm.ai_egress_authorization_revocations(authorization_id,"
                    "revoked_by,revoked_role,reason_code,reason_summary,audit_event_id,trace_id) "
                    "VALUES (%s,%s,'OriginalApprover','USER_CANCELLED','Synthetic cancellation',%s,%s)",
                    (second_authorization, actor, event_only_audit, event_only_trace),
                )

                revoke_trace = uuid.uuid4()
                with db.transaction():
                    revoke_audit = audit("AI_EGRESS_REVOKE", revoke_trace, authorization)
                    revocation = db.execute(
                        "INSERT INTO plm.ai_egress_authorization_revocations(authorization_id,"
                        "revoked_by,revoked_role,reason_code,reason_summary,audit_event_id,trace_id) "
                        "VALUES (%s,%s,'OriginalApprover','USER_CANCELLED',"
                        "'Synthetic cancellation',%s,%s) RETURNING revocation_id,revoked_at",
                        (authorization, actor, revoke_audit, revoke_trace),
                    ).fetchone()
                    db.execute(
                        "UPDATE plm.ai_egress_authorizations SET authorization_state='REVOKED',"
                        "lock_version=1 WHERE authorization_id=%s", (authorization,),
                    )
                    revoke_result = uuid.uuid4()
                    db.execute(
                        "INSERT INTO plm.ai_egress_revoke_results(result_id,authorization_id,"
                        "revocation_id,actor_id,revoked_role,audit_event_id,trace_id,result_state,"
                        "lock_version,revoked_at) VALUES (%s,%s,%s,%s,'OriginalApprover',%s,%s,"
                        "'REVOKED',1,%s)",
                        (revoke_result, authorization, revocation[0], actor, revoke_audit,
                         revoke_trace, revocation[1]),
                    )
                assert db.execute(
                    "SELECT authorization_state,lock_version FROM plm.ai_egress_authorizations "
                    "WHERE authorization_id=%s", (authorization,),
                ).fetchone() == ("REVOKED", 1)
                reject(
                    db,
                    "UPDATE plm.ai_egress_authorizations SET authorization_state='AUTHORIZED',"
                    "lock_version=0 WHERE authorization_id=%s", (authorization,),
                )
                reject(
                    db, "UPDATE plm.ai_egress_authorize_results SET lock_version=1 WHERE result_id=%s",
                    (authorize_result,),
                )
                reject(
                    db, "DELETE FROM plm.ai_egress_revoke_results WHERE result_id=%s",
                    (revoke_result,),
                )
                reject(db, "TRUNCATE plm.ai_egress_authorizations CASCADE")
                sensitive = {"api_key", "secret_ref", "request_body", "response_body", "customer_body"}
                for table in (
                    "ai_egress_authorizations", "ai_egress_authorization_revocations",
                    "ai_egress_authorize_results", "ai_egress_revoke_results",
                ):
                    columns = {row[0] for row in db.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' "
                        "AND table_name=%s", (table,),
                    )}
                    assert not columns.intersection(sensitive), (table, columns.intersection(sensitive))

            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "AI egress authorization history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("populated egress authorization downgrade accepted")
            print(
                "PASS: 0069 empty up/down/re-up, existing preview upgrade, drift, bounded authorize, "
                "atomic first results, one-way revoke history, immutable/nonempty guards"
            )
        finally:
            for name in reversed(created):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
