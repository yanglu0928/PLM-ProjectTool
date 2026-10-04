"""Read-only local Windows diagnostic; cannot authorize backup or migration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import PureWindowsPath

from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
    WindowsProcessInventoryError, assess_processes, collect_windows_processes,
)


def main() -> int:
    if sys.platform != "win32" or len(sys.argv) != 3:
        print("Usage: python -m plm_assistant.entrypoints.process_inventory_windows "
              "<deployment-account-SID> <absolute-runtime-root>", file=sys.stderr)
        return 2
    try:
        assessment = assess_processes(
            collect_windows_processes(), deployment_sid=sys.argv[1],
            runtime_root=PureWindowsPath(sys.argv[2]), observer_pid=os.getpid())
        print(json.dumps({
            "classification": assessment.classification,
            "checked_processes": assessment.checked_processes,
            "unreadable_processes": assessment.unreadable_processes,
            "candidate_processes": [
                {"pid": item.pid, "reasons": item.reasons}
                for item in assessment.findings
            ],
            "backup_or_migration_authorized": False,
        }, separators=(",", ":")))
        return 0
    except (WindowsProcessInventoryError, ValueError):
        print("Windows process inventory unavailable; no maintenance clearance.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
