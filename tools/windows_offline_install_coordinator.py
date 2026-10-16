"""Coordinate pinned Windows non-release install assessment and isolated rehearsal.

Formal install mode is fail-closed until separately evidenced release conditions
and a genuine target installer exist. Rehearsal never writes the formal root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from install_windows_caddy_go_atomic_rehearsal import rehearse
from preflight_windows_caddy_go_formal_install import preflight
from smoke_caddy_go_layout_https import verify_layout


def coordinate(mode: str, candidate: Path, source: Path, stage: Path,
               verified_layout: Path, *, target: Path | None = None,
               install_root: str = r"C:\PLMTool", target_account: str | None = None,
               public_host: str | None = None, tls_cert: Path | None = None,
               tls_key: Path | None = None) -> dict:
    if mode not in {"assess", "rehearse", "install"}:
        raise ValueError("unknown coordinator mode")
    if (mode == "rehearse") != (target is not None):
        raise ValueError("only isolated rehearsal accepts a target")
    readiness = preflight(candidate, source, stage, verified_layout,
                          install_root=install_root, target_account=target_account,
                          public_host=public_host, tls_cert=tls_cert, tls_key=tls_key)
    if readiness["release_eligible"] is not False or readiness["install_authorized"] is not False:
        raise ValueError("formal clearance cannot be inferred from this coordinator")
    if mode == "assess":
        return {"status": "FORMAL_INSTALL_ASSESSMENT_BLOCKED", "mode": mode,
                "release_eligible": False, "formal_root_written": False,
                "blocker_codes": readiness["blocker_codes"],
                "verified_input_file_count": readiness["verified_layout_file_count"]}
    if mode == "install":
        return {"status": "FORMAL_INSTALL_REFUSED", "mode": mode,
                "release_eligible": False, "formal_root_written": False,
                "services_changed": False, "database_connected": False,
                "blocker_codes": readiness["blocker_codes"]}
    # Only the independent, non-release ASCII Temp path may continue while
    # formal account/certificate/License/legal gates remain blocked.
    if target is None:
        raise ValueError("isolated target required")
    placed = rehearse(candidate, source, stage, target)
    checked = verify_layout(candidate, source, stage, target)
    if (checked["file_count"] != placed["target_file_count"]
            or checked["mapping_sha256"] != placed["mapping_sha256"]):
        raise ValueError("independent post-publication verification differs")
    return {"status": "NON_RELEASE_REHEARSAL_PASS_FORMAL_INSTALL_BLOCKED",
            "mode": mode, "release_eligible": False,
            "formal_root_written": False, "services_changed": False,
            "database_connected": False,
            "target_file_count": checked["file_count"],
            "mapping_sha256": checked["mapping_sha256"],
            "candidate_sha256": placed["candidate_sha256"],
            "formal_blocker_codes": readiness["blocker_codes"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("assess", "rehearse", "install"))
    for name in ("candidate", "source", "stage", "verified-layout"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--install-root", default=r"C:\PLMTool")
    parser.add_argument("--target-account")
    parser.add_argument("--public-host")
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args()
    try:
        result = coordinate(args.mode, args.candidate, args.source, args.stage,
                            args.verified_layout, target=args.target,
                            install_root=args.install_root,
                            target_account=args.target_account,
                            public_host=args.public_host,
                            tls_cert=args.tls_cert, tls_key=args.tls_key)
    except (OSError, ValueError):
        print(json.dumps({"status": "COORDINATOR_INPUT_OR_VERIFICATION_REJECTED",
                          "release_eligible": False}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.mode == "rehearse" else 1


if __name__ == "__main__":
    raise SystemExit(main())
