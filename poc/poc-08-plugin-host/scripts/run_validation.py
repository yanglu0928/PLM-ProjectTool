from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from fastapi.testclient import TestClient

from poc08_plugin_host.api import create_app
from poc08_plugin_host.errors import PluginHostError
from poc08_plugin_host.host import PluginHost
from poc08_plugin_host.manifest import current_os_key
from poc08_plugin_host.registry import PluginRegistry, PluginService


FIXTURES = POC_DIR / "fixtures" / "plugins"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    registry = PluginRegistry(os_key=current_os_key())
    service = PluginService(registry, PluginHost(python_executable=sys.executable))
    scenarios: list[dict[str, object]] = []

    def record(name: str, callback: Callable[[], object]) -> None:
        started = time.perf_counter()
        try:
            detail = callback()
            scenarios.append({"name": name, "status": "PASS", "duration_ms": round((time.perf_counter() - started) * 1000, 2), "detail": detail})
        except Exception as exc:  # validation runner must preserve every failed scenario
            scenarios.append({"name": name, "status": "FAIL", "duration_ms": round((time.perf_counter() - started) * 1000, 2), "error_type": type(exc).__name__, "message": str(exc)})

    for fixture in ("echo-v1", "crash", "timeout", "invalid-json", "env-probe"):
        registry.activate(FIXTURES / fixture)
    client = TestClient(create_app(service))

    record("json_rpc_echo", lambda: service.invoke("com.plm.echo", "echo", {"value": "中文"}).result)

    def crash_isolation():
        response = client.post("/poc/plugin/invoke", json={"plugin_id": "com.plm.crash", "method": "run"})
        health = client.get("/health")
        assert response.status_code == 502 and response.json()["error"]["code"] == "PLUGIN_CRASH"
        assert health.status_code == 200
        return {"error_code": "PLUGIN_CRASH", "health_after_failure": "PASS"}

    record("crash_isolation", crash_isolation)

    def timeout_isolation():
        response = client.post("/poc/plugin/invoke", json={"plugin_id": "com.plm.timeout", "method": "run", "timeout_seconds": 0.2})
        health = client.get("/health")
        assert response.status_code == 504 and response.json()["error"]["code"] == "PLUGIN_TIMEOUT"
        assert health.status_code == 200
        return {"error_code": "PLUGIN_TIMEOUT", "health_after_failure": "PASS"}

    record("timeout_isolation", timeout_isolation)

    def expected_error(plugin_id: str, code: str):
        try:
            service.invoke(plugin_id, "run")
        except PluginHostError as exc:
            assert exc.code == code
            return {"error_code": code}
        raise AssertionError(f"Expected {code}")

    record("invalid_json", lambda: expected_error("com.plm.invalid-json", "PLUGIN_INVALID_RESPONSE"))

    def incompatible_version():
        try:
            registry.activate(FIXTURES / "incompatible")
        except PluginHostError as exc:
            assert exc.code == "PLUGIN_INCOMPATIBLE_VERSION"
            return {"error_code": exc.code, "rejected_before_launch": True}
        raise AssertionError("Incompatible plugin was accepted")

    record("incompatible_version", incompatible_version)

    def environment_isolation():
        result = service.invoke("com.plm.env-probe", "probe").result
        assert not any(result["visible"].values())
        return {"sensitive_names_visible": 0}

    record("environment_isolation", environment_isolation)

    def independent_update():
        before = service.invoke("com.plm.echo", "version").result["version"]
        registry.activate(FIXTURES / "echo-v2")
        after = service.invoke("com.plm.echo", "version").result["version"]
        assert before == "1.0.0" and after == "1.1.0"
        return {"before": before, "after": after, "host_code_changed": False}

    record("independent_update", independent_update)

    def disable_control():
        registry.set_enabled("com.plm.echo", False)
        try:
            service.invoke("com.plm.echo", "version")
        except PluginHostError as exc:
            assert exc.code == "PLUGIN_DISABLED"
            registry.set_enabled("com.plm.echo", True)
            return {"error_code": exc.code, "rejected_before_launch": True}
        raise AssertionError("Disabled plugin was invoked")

    record("enable_disable", disable_control)

    def tamper_rejection():
        with tempfile.TemporaryDirectory(prefix="poc08-validation-") as temporary:
            target = Path(temporary) / "plugin"
            shutil.copytree(FIXTURES / "echo-v1", target)
            entry = target / "plugin.py"
            entry.write_text(entry.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            try:
                registry.activate(target)
            except PluginHostError as exc:
                assert exc.code == "PLUGIN_SIGNATURE_INVALID"
                return {"error_code": exc.code, "rejected_before_launch": True}
        raise AssertionError("Tampered plugin was accepted")

    record("signature_tamper", tamper_rejection)

    def concurrent_invocations():
        def invoke(value: int) -> int:
            result = service.invoke("com.plm.echo", "echo", {"value": value})
            return result.result["echo"]["value"]

        with ThreadPoolExecutor(max_workers=20) as executor:
            values = list(executor.map(invoke, range(20)))
        assert values == list(range(20))
        return {"concurrency": 20, "successful_invocations": 20}

    record("twenty_concurrent_invocations", concurrent_invocations)

    passed = sum(item["status"] == "PASS" for item in scenarios)
    result = {
        "schema_version": "poc08.validation.v1",
        "environment": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "plugin_os_key": current_os_key(),
        },
        "protocol": "JSON-RPC 2.0 over stdio",
        "scenario_count": len(scenarios),
        "passed_count": passed,
        "failed_count": len(scenarios) - passed,
        "scenarios": scenarios,
        "status": "PASS" if passed == len(scenarios) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": passed, "total": len(scenarios)}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
