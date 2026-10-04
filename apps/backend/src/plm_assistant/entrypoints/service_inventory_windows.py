"""Redacted, read-only fixed-service SCM diagnostics."""

from __future__ import annotations

import json
import sys

from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    RUNNING, SERVICE_NAMES, START_PENDING, STOP_PENDING, STOPPED,
)
from plm_assistant.modules.platform.infrastructure.windows_service_inventory import (
    WindowsServiceInventoryError, read_service_observation,
)


_STATE_NAMES = {
    STOPPED: "STOPPED", START_PENDING: "START_PENDING",
    STOP_PENDING: "STOP_PENDING", RUNNING: "RUNNING",
}


def build_inventory(roles: tuple[str, ...] = tuple(SERVICE_NAMES)) -> dict:
    if (sys.platform != "win32" or not roles
            or any(role not in SERVICE_NAMES for role in roles)
            or len(set(roles)) != len(roles)):
        raise WindowsServiceInventoryError()
    items = []
    for role in roles:
        observation = read_service_observation(role)
        if observation is None:
            items.append({"role": role, "service_name": SERVICE_NAMES[role],
                          "installed": False})
        else:
            items.append({
                "role": role, "service_name": observation.service_name,
                "installed": True, "service_type": observation.service_type,
                "start_type": observation.start_type,
                "error_control": observation.error_control,
                "state": _STATE_NAMES.get(observation.state, "OTHER"),
                "state_code": observation.state,
                "running_pid": observation.running_pid,
            })
    return {"classification": "DIAGNOSTIC_ONLY",
            "backup_or_migration_authorized": False,
            "services": items}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in (*SERVICE_NAMES, "ALL"):
        print("Usage: python -m plm_assistant.entrypoints.service_inventory_windows "
              "{API|AUDIT_WORKER|PARSER_WORKER|AI_PROVIDER_WORKER|ALL}", file=sys.stderr)
        return 2
    try:
        roles = tuple(SERVICE_NAMES) if sys.argv[1] == "ALL" else (sys.argv[1],)
        report = build_inventory(roles)
    except WindowsServiceInventoryError:
        print("Windows service inventory unavailable; no clearance granted.",
              file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
