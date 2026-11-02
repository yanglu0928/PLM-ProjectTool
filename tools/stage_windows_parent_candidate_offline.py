"""Stage a hash-verified non-release Windows parent ZIP under non-C RUNNER_TEMP."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from stage_windows_parent_candidate_cloud import stage_candidate
from verify_windows_authenticode import verify as verify_authenticode

HOSTED_RECEIPT_STATUS = "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--expected-thumbprint")
    parser.add_argument("--target", type=Path, required=True,
                        help="new direct child of the existing non-C RUNNER_TEMP directory")
    args = parser.parse_args()
    if bool(args.installer) != bool(args.expected_thumbprint):
        print(json.dumps({"status":"HOSTED_WINDOWS_CANDIDATE_STAGING_REJECTED","reason_code":"INSTALLER_PIN_PAIR_REQUIRED","installation_performed":False}, separators=(",",":")))
        return 2
    signature_result = None
    if args.installer:
        signature_result = verify_authenticode(args.installer, args.expected_thumbprint)
        if not signature_result["signature_verified"]:
            print(json.dumps({"status":"HOSTED_WINDOWS_CANDIDATE_STAGING_REJECTED","reason_code":"INSTALLER_AUTHENTICODE_REJECTED","installation_performed":False,"services_started":False}, separators=(",",":")))
            return 2
    try:
        receipt = stage_candidate(args.candidate, args.verification_summary, args.target,
                                  receipt_status=HOSTED_RECEIPT_STATUS)
    except Exception as exc:
        print(json.dumps({
            "status": "HOSTED_WINDOWS_CANDIDATE_STAGING_REJECTED",
            "reason_code": type(exc).__name__,
            "installation_performed": False,
            "services_started": False,
        }, separators=(",", ":")))
        return 2
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    sys.exit(main())
