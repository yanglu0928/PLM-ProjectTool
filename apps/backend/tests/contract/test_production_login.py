from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError,
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.entrypoints.serve_windows import main as serve_windows_main
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class ProductionLoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def settings(self, origins: tuple[str, ...]) -> BootstrapSettings:
        return BootstrapSettings(data_root=Path(self.temp_dir.name), trusted_origins=origins)

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
            self.assertEqual(bare.post("/api/v1/projects").status_code, 404)
            self.assertEqual(bare.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 404)
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.get("/health/ready").status_code, 200)
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
                   return_value=SecretListCursorCodec(b"q" * 32)):
            app = create_production_platform_app(settings)
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.get("/api/v1/admin/secrets").status_code, 401)
            self.assertEqual(client.get("/api/v1/admin/secrets/" + "1" * 36).status_code, 422)
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 405)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.get("/health/ready").status_code, 200)
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
            factory.assert_called_once_with(settings)

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
                   return_value=SecretListCursorCodec(b"q" * 32)):
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
                   "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                   return_value=Mock()) as write_factory:
            app = create_production_platform_write_app(settings)
        license_factory.assert_called_once()
        write_factory.assert_called_once()
        with TestClient(app, base_url="http://localhost") as client:
            self.assertEqual(client.post("/api/v1/admin/secrets").status_code, 403)
            self.assertEqual(client.get("/api/v1/projects").status_code, 401)
            self.assertEqual(client.post("/api/v1/projects").status_code, 403)
            self.assertEqual(client.patch("/api/v1/projects/00000000-0000-0000-0000-000000000001").status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:rotate"
            ).status_code, 403)
            self.assertEqual(client.post(
                "/api/v1/admin/secrets/00000000-0000-0000-0000-000000000001:disable"
            ).status_code, 403)
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
