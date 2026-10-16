"""Disposable PostgreSQL/ASGI proof of explicit Windows Provider read composition."""

from __future__ import annotations

import runpy
import uuid
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError, create_production_login_app,
    create_production_platform_app, create_production_platform_write_app,
)
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec

helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ai-01-a03-p02-provider-append" / "verify.py"))
connect, seed_user, seed_secret = (helpers["connect"], helpers["seed_user"], helpers["seed_secret"])
CSRF = b"c" * 32


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


def main() -> None:
    name = "ai01a04p05_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Platform Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Platform Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                guard = Guard()
                creator = AIProviderCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, secret_proof=SqlAlchemyAIProviderSecretProof(),
                    repository=SqlAlchemyAIProviderCreateRepository(), receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()), clock=lambda: datetime.now(timezone.utc),
                )
                ids = [creator.create(CreateAIProvider(
                    admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    f"Synthetic Platform Provider {index}", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                )) for index in range(3)]
                prefix = "plm_assistant.entrypoints.production_login."
                with TemporaryDirectory(prefix="plm-provider-platform-") as directory, ExitStack() as stack:
                    settings = BootstrapSettings(data_root=Path(directory), trusted_origins=("http://localhost",))
                    stack.enter_context(patch(prefix + "read_database_url", return_value=url))
                    stack.enter_context(patch(
                        "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                        return_value=SimpleNamespace(guard=guard),
                    ))
                    for key, codec in (
                        ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                        ("create_windows_ai_provider_list_cursor_codec", ProviderListCursorCodec(b"i" * 32)),
                        ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                        ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                        ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                        ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                        ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                        ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                        ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                        ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                    ):
                        stack.enter_context(patch(prefix + key, return_value=codec))
                    stack.enter_context(patch(
                        "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                        return_value=object(),
                    ))
                    stack.enter_context(patch(
                        prefix + "create_windows_document_upload_token_issuer",
                        return_value=HmacUploadTokenIssuer(
                            provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                            key_ref="document-upload-token-v1",
                        ),
                    ))
                    path = "/api/v1/admin/ai/providers"
                    headers = {"cookie": "plm_session=" + admin_token.hex()}
                    member_headers = {"cookie": "plm_session=" + member_token.hex()}
                    with TestClient(create_production_login_app(settings), base_url="http://localhost") as client:
                        assert client.get(path, headers=headers).status_code == 404
                    for factory in (create_production_platform_app, create_production_platform_write_app):
                        with TestClient(factory(settings), base_url="http://localhost") as client:
                            first = client.get(path + "?page_size=2", headers=headers)
                            assert first.status_code == 200, first.text
                            cursor = first.json()["data"]["next_cursor"]
                            assert cursor and len(first.json()["data"]["items"]) == 2
                            second = client.get(path + "?page_size=2&cursor=" + cursor, headers=headers)
                            assert second.status_code == 200 and len(second.json()["data"]["items"]) == 1, second.text
                            assert {item["provider_id"] for item in first.json()["data"]["items"] + second.json()["data"]["items"]} == {str(item) for item in ids}
                            detail = client.get(path + "/" + str(ids[0]), headers=headers)
                            assert detail.status_code == 200 and detail.headers["etag"] == '"v0"', detail.text
                            assert detail.json()["data"]["secret_ref_masked"] == "****" + secret.hex[-8:]
                            assert str(secret) not in first.text + second.text + detail.text
                            assert client.get(path, headers=member_headers).status_code == 404
                            guard.enabled = False
                            assert client.get(path, headers=headers).status_code == 403
                            guard.enabled = True
                    with patch(prefix + "create_windows_ai_provider_list_cursor_codec", side_effect=RuntimeError("synthetic missing key")):
                        for factory in (create_production_platform_app, create_production_platform_write_app):
                            try:
                                factory(settings)
                            except ProductionLoginStartupError as exc:
                                assert "synthetic missing" not in str(exc)
                            else:
                                raise AssertionError("platform started without dedicated Provider cursor key")
                print("PASS: both explicit platform modes Provider GET/LIST, real Session/PG, admin/License, masked ETag, login closed, missing key fails closed")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
