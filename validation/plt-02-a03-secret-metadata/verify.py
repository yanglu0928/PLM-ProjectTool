"""Disposable PostgreSQL verification of licensed admin Secret metadata reads."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.platform.application.secret_metadata import (
    SecretMetadataError, SecretMetadataQuery, SecretMetadataService,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_metadata_repository import SqlAlchemySecretMetadataRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Guard:
    def __init__(self):
        self.enabled = True
        self.calls = 0

    def require_valid(self, **_):
        self.calls += 1
        if not self.enabled:
            raise RuntimeError("synthetic expired License")
        return object()


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, role, token):
    user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role)).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential, user_id))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(b"synthetic-csrf").digest(), user_id))
    return user_id


def main():
    name = "plt02a03_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = user(db, "Synthetic Secret Admin", "DEPLOYMENT_ADMIN", admin_token)
                    user(db, "Synthetic Secret Member", "NONE", member_token)
                    ids = [row[0] for row in db.execute(
                        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                        "VALUES (%s,%s,%s),(%s,%s,%s) RETURNING secret_record_id",
                        ("AI_PROVIDER_KEY", "AI_PROVIDER_ADAPTER", actor,
                         "RERANKER_KEY", "RERANKER_ADAPTER", actor),
                    ).fetchall()]
                    version = db.execute("INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,1,%s,'{}'::jsonb,'synthetic-provider',%s) RETURNING secret_version_id", (ids[0], b"synthetic-ciphertext", actor)).fetchone()[0]
                    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (version, ids[0]))
                guard = Guard()
                service = SecretMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemySecretMetadataRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                admin_query = SecretMetadataQuery(admin_token, uuid.uuid4())
                member_query = SecretMetadataQuery(member_token, uuid.uuid4())
                try:
                    service.get(member_query, ids[0])
                except SecretMetadataError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("member read accepted")
                assert guard.calls == 0
                detail = service.get(admin_query, ids[0])
                assert detail.current_version_no == 1 and detail.state == "ACTIVE"
                assert detail.lock_version == 1
                assert "synthetic-ciphertext" not in repr(detail)
                assert "synthetic-provider" not in repr(detail)
                page = service.list_page(admin_query, limit=1)
                assert len(page) == 1
                second = service.list_page(admin_query, after=page[0].secret_id, limit=1)
                assert len(second) == 1 and second[0].secret_id != page[0].secret_id
                newest = service.list_http_page(admin_query, limit=2)
                assert newest[0].created_at == newest[1].created_at
                assert len(newest) == 2 and newest[0].secret_id == max(ids)
                older = service.list_http_page(
                    admin_query, after=(newest[0].created_at, newest[0].secret_id), limit=2,
                )
                assert len(older) == 1 and older[0].secret_id == min(ids)
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',current_version_ref=NULL,lock_version=2 WHERE secret_record_id=%s", (ids[0],))
                disabled = service.get(admin_query, ids[0])
                assert disabled.state == "DISABLED" and disabled.current_version_no is None
                assert disabled.lock_version == 2
                assert "synthetic-ciphertext" not in repr(disabled)
                guard.enabled = False
                try:
                    service.list_page(admin_query)
                except SecretMetadataError as exc:
                    assert exc.code == "SECRET_UNAVAILABLE"
                else:
                    raise AssertionError("expired License allowed")
                print("PASS: PostgreSQL admin-only metadata, safe projection, lock version, signed-cursor keyset source and License denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
