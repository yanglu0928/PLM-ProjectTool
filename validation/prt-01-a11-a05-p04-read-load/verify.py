"""Measure 20 simultaneous Prototype qualification GETs on real PG/file."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

from resource_observer import ResourceObserver


ROOT = Path(__file__).resolve().parents[2]
approved = runpy.run_path(str(
    ROOT / "validation/prt-01-a11-a05-p03-approved-prototype/verify.py"
))


def run(*, reuse_postgres: tuple[str, int, str],
        host_resource_diagnostic: bool = True) -> dict:
    observer = ResourceObserver() if host_resource_diagnostic else None
    if observer is not None:
        observer.start()
    try:
        approved["main"](
            read_load=True,
            network_load=True,
            external_client=True,
            external_pool_comparison=True,
            reuse_postgres=reuse_postgres,
        )
    finally:
        metrics = observer.stop() if observer is not None else {"status": "NOT_REQUESTED"}
        if observer is not None:
            print(
                "PRT_HOST_RESOURCE_SUMMARY="
                + json.dumps(metrics, sort_keys=True, separators=(",", ":"))
            )
    return {"status": "PASS_LIMITED", "resource_summary": metrics,
            "release_eligible": False, "performance_gate_passed": False}


if __name__ == "__main__":
    allowed = {
        (), ("--sql-diagnostic",), ("--network",), ("--phase-diagnostic",),
        ("--timeline-diagnostic",), ("--external-client",),
        ("--external-pool-comparison",), ("--host-resource-diagnostic",),
    }
    if tuple(sys.argv[1:]) not in allowed:
        raise SystemExit(
            "usage: verify.py [--sql-diagnostic|--network|--phase-diagnostic|"
            "--timeline-diagnostic|--external-client|--external-pool-comparison|"
            "--host-resource-diagnostic]"
        )

    resource_diagnostic = sys.argv[1:] == ["--host-resource-diagnostic"]
    observer = ResourceObserver() if resource_diagnostic else None
    if observer is not None:
        observer.start()
    try:
        approved["main"](
            read_load=True,
            read_load_sql_diagnostic=(sys.argv[1:] == ["--sql-diagnostic"]),
            network_load=(sys.argv[1:] in (
                ["--network"], ["--phase-diagnostic"], ["--timeline-diagnostic"],
                ["--external-client"], ["--external-pool-comparison"],
                ["--host-resource-diagnostic"],
            )),
            phase_diagnostic=(sys.argv[1:] == ["--phase-diagnostic"]),
            timeline_diagnostic=(sys.argv[1:] == ["--timeline-diagnostic"]),
            external_client=(sys.argv[1:] in (
                ["--external-client"], ["--external-pool-comparison"],
                ["--host-resource-diagnostic"],
            )),
            external_pool_comparison=(sys.argv[1:] in (
                ["--external-pool-comparison"], ["--host-resource-diagnostic"],
            )),
        )
    finally:
        if observer is not None:
            print(
                "PRT_HOST_RESOURCE_SUMMARY="
                + json.dumps(observer.stop(), sort_keys=True, separators=(",", ":"))
            )
