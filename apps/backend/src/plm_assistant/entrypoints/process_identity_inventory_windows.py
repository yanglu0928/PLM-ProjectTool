"""Read-only Windows marker and OS inventory diagnostic, never clearance."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PureWindowsPath

from plm_assistant.modules.platform.infrastructure.windows_marker_reconciliation import (
    WindowsMarkerReconciliationError, reconcile_runtime_markers,
)
from plm_assistant.modules.platform.infrastructure.windows_process_inventory import (
    WindowsProcessInventoryError, assess_processes, collect_windows_processes,
)


def main() -> int:
    if sys.platform != "win32" or len(sys.argv) != 4:
        print("Usage: python -m plm_assistant.entrypoints.process_identity_inventory_windows "
              "<deployment-account-SID> <absolute-runtime-root> <absolute-data-root>",
              file=sys.stderr)
        return 2
    try:
        observations = collect_windows_processes()
        candidates = assess_processes(
            observations, deployment_sid=sys.argv[1],
            runtime_root=PureWindowsPath(sys.argv[2]), observer_pid=os.getpid())
        markers = reconcile_runtime_markers(Path(sys.argv[3]), observations, candidates)
        print(json.dumps({
            "classification": markers.classification,
            "checked_processes": candidates.checked_processes,
            "unreadable_processes": candidates.unreadable_processes,
            "candidate_processes": [
                {"pid": item.pid, "reasons": item.reasons}
                for item in candidates.findings
            ],
            "marker_findings": [
                {"pid": item.pid, "role": item.role, "status": item.status}
                for item in markers.findings
            ],
            "unmatched_candidate_pids": markers.unmatched_candidates,
            "backup_or_migration_authorized": False,
        }, separators=(",", ":")))
        return 0
    except (WindowsProcessInventoryError, WindowsMarkerReconciliationError, ValueError):
        print("Windows process identity inventory unavailable; no maintenance clearance.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
