from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError,
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.entrypoints.serve_windows import main as serve_windows_main
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec


class ProductionLoginTests(unittest.TestCase):
    def test_export_composition_constructor_failure_disposes_both_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        prefix='plm_assistant.entrypoints.production_login.'
        for factory in (create_production_platform_app,create_production_platform_write_app):
            for dependency in ('AuditExportContentReader','create_audit_export_result_router','create_audit_export_download_router'):
                runtime=Mock();runtime.is_ready.return_value=True
                with ExitStack() as stack:
                    for name,value in (('read_database_url','postgresql+psycopg://localhost/test'),
                        ('create_database_runtime',runtime),('_schema_current',True),
                        ('create_windows_secret_list_cursor_codec',SecretListCursorCodec(b'q'*32)),
                        ('create_windows_project_member_cursor_codec',MemberListCursorCodec(b'm'*32)),
                        ('create_windows_project_department_cursor_codec',DepartmentListCursorCodec(b'd'*32))):
                        stack.enter_context(patch(prefix+name,return_value=value))
                    stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=Mock(guard=Mock())))
                    failed=stack.enter_context(patch(prefix+dependency,side_effect=RuntimeError('private failure')))
                    with self.assertRaises(ProductionLoginStartupError) as caught:factory(self.settings(('http://localhost',)))
                    self.assertNotIn('private',str(caught.exception));failed.assert_called_once()
                runtime.dispose.assert_called_once()

    def setUp(self) -> None:
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_audit_cursor_codec",
            return_value=AuditListCursorCodec(b"a"*32),
        ))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",
            return_value=DocumentListCursorCodec(b"x" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",
            return_value=VersionListCursorCodec(b"z" * 32),
        ))
        self.enterContext(patch(
            "plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",
            return_value=ParseListCursorCodec(b"p" * 32),
        ))

    def settings(self, origins: tuple[str, ...]) -> BootstrapSettings:
        return BootstrapSettings(data_root=Path(self.temp_dir.name), trusted_origins=origins)

    def test_missing_audit_cursor_disposes_both_platform_modes(self):
        from contextlib import ExitStack
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        for factory in (create_production_platform_app,create_production_platform_write_app):
            runtime=Mock();runtime.is_ready.return_value=True
            with ExitStack() as stack:
                prefix="plm_assistant.entrypoints.production_login."
                for name,value in (("read_database_url","postgresql+psycopg://test:synthetic@localhost/test"),
                    ("create_database_runtime",runtime),("_schema_current",True),
                    ("create_windows_secret_list_cursor_codec",SecretListCursorCodec(b"q"*32)),
                    ("create_windows_project_member_cursor_codec",MemberListCursorCodec(b"m"*32)),
                    ("create_windows_project_department_cursor_codec",DepartmentListCursorCodec(b"d"*32))):
                    stack.enter_context(patch(prefix+name,return_value=value))
                stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",return_value=Mock(guard=Mock())))
                stack.enter_context(patch(prefix+"create_windows_audit_cursor_codec",side_effect=RuntimeError("sensitive synthetic missing key")))
                with self.assertRaises(ProductionLoginStartupError) as exc:factory(self.settings(("http://localhost",)))
                self.assertNotIn("sensitive",str(exc.exception))
            runtime.dispose.assert_called_once()

    def test_empty_or_insecure_origin_never_reads_credential(self) -> None:
        with patch("plm_assistant.entrypoints.production_login.read_database_url") as reader:
            for origins in ((), ("http://plm.example.test",)):
                with self.subTest(origins=origins):
                    with self.assertRaises(ProductionLoginStartupError):
                        create_production_login_app(self.settings(origins))
            reader.assert_not_called()

    def test_missing_credential_fails_without_revealing_target(self) -> None:
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   side_effect=RuntimeError("synthetic-password")):
            with self.assertRaises(ProductionLoginStartupError) as captured:
                create_production_login_app(self.settings(("http://localhost",)))
        self.assertNotIn("synthetic-password", str(captured.exception))

    def test_database_unavailable_disposes_and_does_not_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = False
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_login_app(self.settings(("http://localhost",)))
        runtime.dispose.assert_called_once()

    def test_outdated_schema_disposes_and_does_not_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=False):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_login_app(self.settings(("http://localhost",)))
        runtime.dispose.assert_called_once()

    def test_opt_in_route_and_shutdown_disposal(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True):
            app = create_production_login_app(self.settings(("http://localhost",)))
        with TestClient(create_app(), base_url="http://localhost") as bare:
            self.assertEqual(bare.post("/api/v1/auth/login").status_code, 404)
            self.assertEqual(bare.get("/api/v1/projects").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 404)
            self.assertEqual(bare.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(bare.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 404)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(bare.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 404)
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.get("/health/ready").status_code, 200)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 404)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 404)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 404)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 404)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 404)
            response = client.post("/api/v1/auth/login", headers={"origin": "http://evil.test"},
                                   json={"username": "a", "password": "b"})
            self.assertEqual(response.status_code, 403)
        runtime.dispose.assert_called_once()

    def test_windows_launcher_passes_nonsecret_settings_to_factory(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv", ["serve_windows", str(bootstrap)]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_login_app",
             return_value="synthetic-app") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.kwargs["factory"], True)
            self.assertEqual(run.call_args.kwargs["proxy_headers"], False)
            self.assertEqual(run.call_args.args[0](), "synthetic-app")
            factory.assert_called_once_with(settings)

    def test_windows_launcher_rejects_nonloopback_plain_http(self) -> None:
        settings = BootstrapSettings(
            data_root=Path(self.temp_dir.name), bind_host="0.0.0.0",
            trusted_origins=("https://plm.example.test",),
        )
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv", ["serve_windows", str(bootstrap)]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run:
            self.assertEqual(serve_windows_main(), 1)
            run.assert_not_called()

    def test_platform_requires_license_and_cursor_key_before_routes_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())) as license_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   side_effect=RuntimeError("synthetic missing cursor key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing cursor key", str(caught.exception))
        license_factory.assert_called_once_with(runtime, settings)
        runtime.dispose.assert_called_once()

    def test_platform_mounts_read_only_with_explicit_trust_sources(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)):
            app = create_production_platform_app(settings)
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.get("/api/v1/admin/secrets").status_code, 401)
            self.assertEqual(client.get("/api/v1/admin/audit-events").status_code,401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/audit-events").status_code,401)
            self.assertEqual(client.get("/api/v1/admin/secrets/" + "1" * 36).status_code, 422)
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 405)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions/00000000-0000-0000-0000-000000000002/content").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 403)
            self.assertEqual(client.post("/api/v1/global/document-uploads").status_code, 404)
            self.assertEqual(client.put("/api/v1/global/document-uploads/00000000-0000-0000-0000-000000000001/content").status_code, 404)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 403)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 403)
            self.assertEqual(client.get("/health/ready").status_code, 200)
        runtime.dispose.assert_called_once()

    def test_platform_download_storage_failure_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.LocalFileStorage",
                   side_effect=RuntimeError("synthetic-storage-path")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic-storage-path", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_member_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   side_effect=RuntimeError("synthetic missing member key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing member key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_department_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   side_effect=RuntimeError("synthetic missing department key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing department key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_document_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_list_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Document key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Document key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_platform_missing_version_cursor_key_disposes_before_publish(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_version_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Version key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Version key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_windows_launcher_platform_mode_is_explicit(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv",
             ["serve_windows", str(bootstrap), "--platform"]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_platform_app",
             return_value="synthetic-platform") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.args[0](), "synthetic-platform")
            self.assertEqual(run.call_args.kwargs["workers"], 1)
            factory.assert_called_once_with(settings)

    def test_missing_parse_cursor_key_disposes_platform(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_parse_cursor_codec",
                   side_effect=RuntimeError("synthetic missing Parse key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_app(settings)
        self.assertNotIn("synthetic missing Parse key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_write_mode_missing_master_key_disposes_without_publishing(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)):
            with self.assertRaises(ProductionLoginStartupError):
                create_production_platform_write_app(settings)
        runtime.dispose.assert_called_once()

    def test_write_mode_mounts_only_after_all_sources_exist(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())) as license_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                   return_value=Mock()) as write_factory, patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                   return_value=Mock()) as upload_issuer_factory:
            app = create_production_platform_write_app(settings)
        license_factory.assert_called_once()
        write_factory.assert_called_once()
        upload_issuer_factory.assert_called_once()
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.post("/api/v1/global/document-uploads").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/document-uploads").status_code, 403)
            self.assertEqual(client.put("/api/v1/global/document-uploads/00000000-0000-0000-0000-000000000001/content").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001:archive").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 401)
            self.assertEqual(client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents").status_code, 401)
            self.assertEqual(client.get("/api/v1/global/documents/00000000-0000-0000-0000-000000000001/versions").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/departments/00000000-0000-0000-0000-000000000002:deactivate").status_code, 403)
            self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002").status_code, 403)
            for action in ("suspend", "resume", "remove"):
                self.assertEqual(client.post("/api/v1/projects/00000000-0000-0000-0000-000000000001/members/00000000-0000-0000-0000-000000000002:" + action).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:rotate"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:disable"
            ).status_code, 403)
        runtime.dispose.assert_called_once()

    def test_write_mode_missing_upload_key_disposes_without_publishing(self) -> None:
        runtime = Mock()
        runtime.is_ready.return_value = True
        settings = self.settings(("http://localhost",))
        from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
        with patch("plm_assistant.entrypoints.production_login.read_database_url",
                   return_value="postgresql+psycopg://test:synthetic@localhost/test"), patch(
                   "plm_assistant.entrypoints.production_login.create_database_runtime",
                   return_value=runtime), patch(
                   "plm_assistant.entrypoints.production_login._schema_current",
                   return_value=True), patch(
                   "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                   return_value=Mock(guard=Mock())), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                   return_value=SecretListCursorCodec(b"q" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                   return_value=MemberListCursorCodec(b"m" * 32)), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                   return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                   "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                   return_value=Mock()), patch(
                   "plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                   side_effect=RuntimeError("synthetic missing upload key")):
            with self.assertRaises(ProductionLoginStartupError) as caught:
                create_production_platform_write_app(settings)
        self.assertNotIn("synthetic missing upload key", str(caught.exception))
        runtime.dispose.assert_called_once()

    def test_windows_launcher_write_mode_is_explicit(self) -> None:
        settings = self.settings(("http://localhost",))
        bootstrap = Path(self.temp_dir.name) / "bootstrap.yaml"
        bootstrap.write_text("data_root: ignored\n", encoding="utf-8")
        with patch("plm_assistant.entrypoints.serve_windows.sys.platform", "win32"), patch(
             "plm_assistant.entrypoints.serve_windows.sys.argv",
             ["serve_windows", str(bootstrap), "--platform-write"]), patch(
             "plm_assistant.entrypoints.serve_windows.load_bootstrap_settings",
             return_value=settings), patch(
             "plm_assistant.entrypoints.serve_windows.uvicorn.run") as run, patch(
             "plm_assistant.entrypoints.serve_windows.create_production_platform_write_app",
             return_value="synthetic-write-platform") as factory:
            self.assertEqual(serve_windows_main(), 0)
            self.assertEqual(run.call_args.args[0](), "synthetic-write-platform")
            factory.assert_called_once_with(settings)


if __name__ == "__main__":
    unittest.main()
