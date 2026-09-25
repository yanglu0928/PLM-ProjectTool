from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError,
    create_production_login_app,
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


if __name__ == "__main__":
    unittest.main()
