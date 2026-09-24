from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from .errors import PluginHostError
from .manifest import PluginManifest


SAFE_ENV_KEYS = {
    "COMSPEC",
    "LANG",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "WINDIR",
}


@dataclass(frozen=True)
class InvocationResult:
    result: Any
    plugin_id: str
    plugin_version: str


class PluginHost:
    def __init__(self, *, python_executable: str | None = None, max_stderr_chars: int = 2048) -> None:
        self.python_executable = python_executable or sys.executable
        self.max_stderr_chars = max_stderr_chars

    @staticmethod
    def _sanitized_environment(manifest: PluginManifest) -> dict[str, str]:
        environment = {key: value for key, value in os.environ.items() if key.upper() in SAFE_ENV_KEYS}
        environment.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "PLM_PLUGIN_API_VERSION": manifest.plugin_api_version,
                "PLM_PLUGIN_ID": manifest.plugin_id,
            }
        )
        return environment

    def invoke(
        self,
        manifest: PluginManifest,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_seconds: float = 2.0,
    ) -> InvocationResult:
        if not method or not isinstance(method, str):
            raise PluginHostError("PLUGIN_INVALID_REQUEST", "Plugin method must be a non-empty string")
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [self.python_executable, str(manifest.entry_point)],
            cwd=manifest.root,
            env=self._sanitized_environment(manifest),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        try:
            stdout, stderr = process.communicate(json.dumps(request, ensure_ascii=False) + "\n", timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            _, stderr = process.communicate()
            raise PluginHostError(
                "PLUGIN_TIMEOUT",
                "Plugin invocation exceeded its timeout",
                detail=stderr[-self.max_stderr_chars :] or None,
            ) from exc

        if process.returncode != 0:
            raise PluginHostError(
                "PLUGIN_CRASH",
                f"Plugin process exited with code {process.returncode}",
                detail=stderr[-self.max_stderr_chars :] or None,
            )

        lines = [line for line in stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise PluginHostError("PLUGIN_INVALID_RESPONSE", "Plugin must emit exactly one JSON-RPC response")
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise PluginHostError("PLUGIN_INVALID_RESPONSE", "Plugin emitted invalid JSON") from exc
        if not isinstance(response, dict) or response.get("jsonrpc") != "2.0" or response.get("id") != request["id"]:
            raise PluginHostError("PLUGIN_INVALID_RESPONSE", "Plugin emitted an invalid JSON-RPC envelope")
        if "error" in response:
            error = response["error"] if isinstance(response["error"], dict) else {}
            raise PluginHostError("PLUGIN_REMOTE_ERROR", str(error.get("message", "Plugin returned an error")))
        if "result" not in response:
            raise PluginHostError("PLUGIN_INVALID_RESPONSE", "Plugin response does not contain result or error")
        return InvocationResult(response["result"], manifest.plugin_id, manifest.version)
