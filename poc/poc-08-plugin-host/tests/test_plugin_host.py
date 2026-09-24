from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from fastapi.testclient import TestClient

from poc08_plugin_host.api import create_app
from poc08_plugin_host.errors import PluginHostError
from poc08_plugin_host.host import PluginHost
from poc08_plugin_host.manifest import PluginManifest, current_os_key
from poc08_plugin_host.registry import PluginRegistry, PluginService


FIXTURES = POC_DIR / "fixtures" / "plugins"


class PluginHostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PluginRegistry(os_key=current_os_key())
        self.host = PluginHost(python_executable=sys.executable)
        self.service = PluginService(self.registry, self.host)

    def activate(self, name: str):
        return self.registry.activate(FIXTURES / name)

    def assert_plugin_error(self, code: str, callback) -> PluginHostError:
        with self.assertRaises(PluginHostError) as context:
            callback()
        self.assertEqual(code, context.exception.code)
        return context.exception

    def test_json_rpc_echo_happy_path(self) -> None:
        self.activate("echo-v1")
        result = self.service.invoke("com.plm.echo", "echo", {"value": "中文"})
        self.assertEqual({"value": "中文"}, result.result["echo"])
        self.assertEqual("1.0.0", result.plugin_version)

    def test_crash_isolated_and_fastapi_remains_healthy(self) -> None:
        self.activate("crash")
        self.activate("echo-v1")
        client = TestClient(create_app(self.service))
        failed = client.post("/poc/plugin/invoke", json={"plugin_id": "com.plm.crash", "method": "run"})
        self.assertEqual(502, failed.status_code)
        self.assertEqual("PLUGIN_CRASH", failed.json()["error"]["code"])
        self.assertEqual(200, client.get("/health").status_code)
        recovered = client.post("/poc/plugin/invoke", json={"plugin_id": "com.plm.echo", "method": "version"})
        self.assertEqual(200, recovered.status_code)

    def test_timeout_is_terminated_and_fastapi_remains_healthy(self) -> None:
        self.activate("timeout")
        client = TestClient(create_app(self.service))
        started = time.perf_counter()
        failed = client.post(
            "/poc/plugin/invoke",
            json={"plugin_id": "com.plm.timeout", "method": "run", "timeout_seconds": 0.2},
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(504, failed.status_code)
        self.assertEqual("PLUGIN_TIMEOUT", failed.json()["error"]["code"])
        self.assertLess(elapsed, 2.0)
        self.assertEqual(200, client.get("/health").status_code)

    def test_invalid_json_fails_closed(self) -> None:
        self.activate("invalid-json")
        self.assert_plugin_error(
            "PLUGIN_INVALID_RESPONSE",
            lambda: self.service.invoke("com.plm.invalid-json", "run"),
        )

    def test_incompatible_api_rejected_before_activation(self) -> None:
        self.assert_plugin_error("PLUGIN_INCOMPATIBLE_VERSION", lambda: self.activate("incompatible"))

    def test_sensitive_environment_is_not_inherited(self) -> None:
        previous = {name: os.environ.get(name) for name in ("DATABASE_URL", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "KEY")}
        try:
            for name in previous:
                os.environ[name] = "synthetic-secret-must-not-cross-boundary"
            self.activate("env-probe")
            result = self.service.invoke("com.plm.env-probe", "probe")
            self.assertFalse(any(result.result["visible"].values()))
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_independent_update_switches_active_version(self) -> None:
        self.activate("echo-v1")
        first = self.service.invoke("com.plm.echo", "version")
        self.activate("echo-v2")
        second = self.service.invoke("com.plm.echo", "version")
        self.assertEqual("1.0.0", first.result["version"])
        self.assertEqual("1.1.0", second.result["version"])

    def test_disabled_plugin_rejected_before_process_start(self) -> None:
        self.activate("echo-v1")
        self.registry.set_enabled("com.plm.echo", False)
        self.assert_plugin_error("PLUGIN_DISABLED", lambda: self.service.invoke("com.plm.echo", "version"))

    def test_entry_point_hash_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poc08-tamper-") as temporary:
            target = Path(temporary) / "plugin"
            shutil.copytree(FIXTURES / "echo-v1", target)
            entry = target / "plugin.py"
            entry.write_text(entry.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            self.assert_plugin_error("PLUGIN_SIGNATURE_INVALID", lambda: self.registry.activate(target))

    def test_entry_point_cannot_escape_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poc08-boundary-") as temporary:
            base = Path(temporary)
            plugin_dir = base / "plugin"
            plugin_dir.mkdir()
            outside = base / "outside.py"
            outside.write_text("print('outside')\n", encoding="utf-8")
            manifest = json.loads((FIXTURES / "echo-v1" / "manifest.json").read_text(encoding="utf-8"))
            manifest["entry_point"] = "../outside.py"
            (plugin_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assert_plugin_error("PLUGIN_INVALID_ENTRY_POINT", lambda: self.registry.activate(plugin_dir))

    def test_missing_required_manifest_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poc08-manifest-") as temporary:
            target = Path(temporary) / "plugin"
            shutil.copytree(FIXTURES / "echo-v1", target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["supported_formats"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assert_plugin_error("PLUGIN_INVALID_MANIFEST", lambda: self.registry.activate(target))

    def test_unknown_method_is_structured_remote_error(self) -> None:
        self.activate("echo-v1")
        self.assert_plugin_error(
            "PLUGIN_REMOTE_ERROR",
            lambda: self.service.invoke("com.plm.echo", "unknown"),
        )

    def test_twenty_concurrent_invocations_are_isolated(self) -> None:
        self.activate("echo-v1")

        def invoke(value: int) -> int:
            result = self.service.invoke("com.plm.echo", "echo", {"value": value})
            return result.result["echo"]["value"]

        with ThreadPoolExecutor(max_workers=20) as executor:
            values = list(executor.map(invoke, range(20)))
        self.assertEqual(list(range(20)), values)


if __name__ == "__main__":
    unittest.main()
