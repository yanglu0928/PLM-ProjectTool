"""Measure 20 simultaneous Prototype qualification GETs on real PG/file."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
approved = runpy.run_path(str(
    ROOT / "validation/prt-01-a11-a05-p03-approved-prototype/verify.py"
))


if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--sql-diagnostic"], ["--network"],
                            ["--phase-diagnostic"], ["--timeline-diagnostic"],
                            ["--external-client"], ["--external-pool-comparison"]):
        raise SystemExit("usage: verify.py [--sql-diagnostic|--network|--phase-diagnostic|--timeline-diagnostic|--external-client|--external-pool-comparison]")
    approved["main"](
        read_load=True,
        read_load_sql_diagnostic=(sys.argv[1:] == ["--sql-diagnostic"]),
        network_load=(sys.argv[1:] in (["--network"], ["--phase-diagnostic"],
                                        ["--timeline-diagnostic"],
                                        ["--external-client"],
                                        ["--external-pool-comparison"])),
        phase_diagnostic=(sys.argv[1:] == ["--phase-diagnostic"]),
        timeline_diagnostic=(sys.argv[1:] == ["--timeline-diagnostic"]),
        external_client=(sys.argv[1:] in (["--external-client"],
                                            ["--external-pool-comparison"])),
        external_pool_comparison=(sys.argv[1:] == ["--external-pool-comparison"]),
    )
