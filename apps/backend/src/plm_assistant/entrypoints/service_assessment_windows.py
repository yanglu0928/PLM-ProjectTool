"""Read-only comparison of fixed SCM definitions with a validated command plan."""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path

from plm_assistant.entrypoints.service_install_windows import (
    SERVICE_DEMAND_START, SERVICE_ERROR_NORMAL, _ACCOUNT,
)
from plm_assistant.entrypoints.service_plan_windows import (
    WindowsServicePlanError, build_service_plan,
)
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES, SERVICE_WIN32_OWN_PROCESS,
)
from plm_assistant.modules.platform.infrastructure.windows_service_inventory import (
    WindowsServiceInventoryError, read_service_observation,
)


class WindowsServiceAssessmentError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_SERVICE_ASSESSMENT_UNAVAILABLE")


def assess_fixed_service(role: str, python_exe: Path, bootstrap_yaml: Path,
                         expected_account: str, *, reader=None) -> dict:
    """Compare saved SCM config only; never assert running identity or quiescence."""
    if (sys.platform != "win32" or type(role) is not str
            or role not in SERVICE_NAMES or type(expected_account) is not str
            or not _ACCOUNT.fullmatch(expected_account)
            or expected_account.upper().startswith(("NT AUTHORITY\\", "NT SERVICE\\"))):
        raise WindowsServiceAssessmentError()
    try:
        plan = build_service_plan(python_exe, bootstrap_yaml)
        expected_command = next(
            item["binary_path"] for item in plan["service_commands"]
            if item["role"] == role)
        observed = read_service_observation(role, reader=reader)
    except (WindowsServicePlanError, WindowsServiceInventoryError):
        raise WindowsServiceAssessmentError() from None
    if observed is None:
        mismatch_codes = ["SERVICE_NOT_INSTALLED"]
    else:
        mismatch_codes = []
        if observed.service_type != SERVICE_WIN32_OWN_PROCESS:
            mismatch_codes.append("SERVICE_TYPE_MISMATCH")
        if observed.start_type != SERVICE_DEMAND_START:
            mismatch_codes.append("START_TYPE_MISMATCH")
        if observed.error_control != SERVICE_ERROR_NORMAL:
            mismatch_codes.append("ERROR_CONTROL_MISMATCH")
        if observed.binary_path != expected_command:
            mismatch_codes.append("BINARY_PATH_MISMATCH")
        if observed.start_account != expected_account:
            mismatch_codes.append("ACCOUNT_MISMATCH")
    matches = not mismatch_codes
    return {
        "role": role, "service_name": SERVICE_NAMES[role],
        "status": ("CONFIG_MATCH_DIAGNOSTIC_ONLY" if matches
                   else "CONFIG_MISMATCH_DIAGNOSTIC_ONLY"),
        "installed": observed is not None,
        "configuration_matches": matches,
        "mismatch_codes": mismatch_codes,
        "backup_or_migration_authorized": False,
    }


def main() -> int:
    if (sys.platform != "win32" or len(sys.argv) != 5 or sys.argv[1] != "--assess"
            or sys.argv[2] not in SERVICE_NAMES or not sys.stdin.isatty()):
        print("Usage: python -m plm_assistant.entrypoints.service_assessment_windows "
              "--assess {API|AUDIT_WORKER|PARSER_WORKER} "
              "<absolute-python.exe> <absolute-bootstrap.yaml>", file=sys.stderr)
        return 2
    try:
        python_exe, bootstrap = Path(sys.argv[3]), Path(sys.argv[4])
        build_service_plan(python_exe, bootstrap)
        account = getpass.getpass("Expected service account: ")
        report = assess_fixed_service(sys.argv[2], python_exe, bootstrap, account)
    except (WindowsServicePlanError, WindowsServiceAssessmentError, EOFError):
        print("Windows service assessment unavailable; no clearance granted.",
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["configuration_matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
