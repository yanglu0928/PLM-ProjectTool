"""Read-only Windows SCM command plan; never installs or changes a service."""

from __future__ import annotations

import json
import ipaddress
import subprocess
import sys
from pathlib import Path

from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    load_bootstrap_settings,
)
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES,
)
from plm_assistant.entrypoints.ai_probe_policy import create_deployment_ai_probe_registry
from plm_assistant.entrypoints.ai_execution_policy import (
    create_deployment_ai_execution_registry,
)
from plm_assistant.entrypoints.ai_task_policy import create_deployment_ai_task_policies


class WindowsServicePlanError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_SERVICE_PLAN_UNAVAILABLE")


def _regular_absolute_file(path: Path, *, names: tuple[str, ...] | None = None) -> Path:
    if (not isinstance(path, Path) or not path.is_absolute()
            or names is not None and path.name.lower() not in names
            or path.is_symlink()
            or not path.is_file()):
        raise WindowsServicePlanError()
    try:
        return path.resolve(strict=True)
    except OSError:
        raise WindowsServicePlanError() from None


def build_service_plan(python_exe: Path, bootstrap_yaml: Path) -> dict:
    """Emit runnable fixed-role plans only; never a clearance or mutation."""
    if sys.platform != "win32":
        raise WindowsServicePlanError()
    interpreter = _regular_absolute_file(python_exe, names=("python.exe",))
    bootstrap = _regular_absolute_file(bootstrap_yaml)
    if bootstrap.suffix.lower() not in (".yaml", ".yml"):
        raise WindowsServicePlanError()
    try:
        settings = load_bootstrap_settings(bootstrap)
        if (not ipaddress.ip_address(settings.bind_host).is_loopback
                or not settings.data_root.is_dir()
                or settings.data_root.is_symlink()
                or settings.parser_ocr_model_fingerprint is None
                or any(value is None or not value.is_dir() or value.is_symlink()
                       for value in (settings.parser_ocr_detection_model_dir,
                                     settings.parser_ocr_recognition_model_dir))):
            raise WindowsServicePlanError()
        if settings.ai_probe_policies:
            create_deployment_ai_probe_registry(settings)
        has_tasks = bool(settings.ai_task_policies)
        has_execution = bool(settings.ai_execution_policies)
        if has_tasks != has_execution:
            raise WindowsServicePlanError()
        if has_tasks:
            create_deployment_ai_task_policies(settings)
            create_deployment_ai_execution_registry(settings)
    except Exception:
        raise WindowsServicePlanError() from None
    return {
        "status": "PLAN_ONLY",
        "scm_installed": False,
        "runtime_and_account_verified": False,
        "backup_or_migration_authorized": False,
        "service_commands": [
            {"role": role, "service_name": name,
             "binary_path": subprocess.list2cmdline((
                 str(interpreter), "-m",
                 "plm_assistant.entrypoints.service_windows", role,
                 str(bootstrap)))}
            for role, name in SERVICE_NAMES.items()
            if (role != "AI_PROVIDER_WORKER" or settings.ai_probe_policies
                or settings.ai_task_policies)
        ],
    }


def main() -> int:
    if sys.platform != "win32" or len(sys.argv) != 3:
        print("Usage: python -m plm_assistant.entrypoints.service_plan_windows "
              "<absolute-python.exe> <absolute-bootstrap.yaml>", file=sys.stderr)
        return 2
    try:
        plan = build_service_plan(Path(sys.argv[1]), Path(sys.argv[2]))
    except WindowsServicePlanError:
        print("Windows service plan unavailable; paths/configuration rejected.",
              file=sys.stderr)
        return 1
    print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
