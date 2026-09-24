from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

POC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_ROOT / "src"))

from poc09_license import (  # noqa: E402
    LicenseError,
    LicensePayload,
    SystemTimeGuard,
    create_license_request,
    discover_mac_candidates,
    issue_license,
    public_key_to_base64,
    verify_license,
)


UTC = timezone.utc
BASE_TIME = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)


def expected_error(code: str, operation) -> dict[str, str]:
    try:
        operation()
    except LicenseError as exc:
        if exc.code != code:
            raise AssertionError(f"Expected {code}, got {exc.code}") from exc
        return {"error_code": exc.code}
    raise AssertionError(f"Expected {code}")


def run() -> dict[str, object]:
    candidates = discover_mac_candidates()
    selected_mac = candidates[0].mac
    request = create_license_request(candidates, selected_mac)
    private_key = Ed25519PrivateKey.generate()
    public_key = public_key_to_base64(private_key.public_key())
    payload = LicensePayload.create(
        license_id="LIC-POC-VALIDATION",
        customer="Anonymous PoC",
        machine_fingerprint=request["machine_fingerprint"],
        issue_time=BASE_TIME,
        valid_from=BASE_TIME,
        valid_to=BASE_TIME + timedelta(days=30),
    )
    document = issue_license(payload, private_key).as_dict()

    scenarios: list[dict[str, object]] = []

    def add(name: str, detail: dict[str, object]) -> None:
        scenarios.append({"name": name, "status": "PASS", "detail": detail})

    add("mac_discovery_and_explicit_selection", {"candidate_count": len(candidates), "raw_mac_persisted": False})
    verified = verify_license(document, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME)
    add("valid_license", {"license_id": verified.license_id, "algorithm": "Ed25519"})
    add("mac_change", expected_error("LICENSE_MACHINE_MISMATCH", lambda: verify_license(
        document, public_key_base64=public_key, current_mac="02:AA:BB:CC:DD:EE", now=BASE_TIME
    )))
    add("expired", expected_error("LICENSE_EXPIRED", lambda: verify_license(
        document, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME + timedelta(days=31)
    )))
    tampered_payload = copy.deepcopy(document)
    tampered_payload["payload"]["customer"] = "Tampered"
    add("payload_tamper", expected_error("LICENSE_SIGNATURE_INVALID", lambda: verify_license(
        tampered_payload, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME
    )))
    wrong_public_key = public_key_to_base64(Ed25519PrivateKey.generate().public_key())
    add("wrong_public_key", expected_error("LICENSE_SIGNATURE_INVALID", lambda: verify_license(
        document, public_key_base64=wrong_public_key, current_mac=selected_mac, now=BASE_TIME
    )))
    add("system_time_before_issue", expected_error("LICENSE_SYSTEM_TIME_INVALID", lambda: verify_license(
        document, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME - timedelta(seconds=1)
    )))
    guard = SystemTimeGuard()
    verify_license(
        document, public_key_base64=public_key, current_mac=selected_mac,
        now=BASE_TIME + timedelta(days=2), time_guard=guard
    )
    add("system_time_rollback", expected_error("LICENSE_CLOCK_ROLLBACK", lambda: verify_license(
        document, public_key_base64=public_key, current_mac=selected_mac,
        now=BASE_TIME + timedelta(days=1), time_guard=guard
    )))
    malformed = copy.deepcopy(document)
    malformed["extra"] = "rejected"
    add("malformed_document", expected_error("LICENSE_DOCUMENT_INVALID", lambda: verify_license(
        malformed, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME
    )))
    tampered_signature = copy.deepcopy(document)
    replacement = "A" if tampered_signature["signature"][-1] != "A" else "B"
    tampered_signature["signature"] = tampered_signature["signature"][:-1] + replacement
    add("signature_tamper", expected_error("LICENSE_SIGNATURE_INVALID", lambda: verify_license(
        tampered_signature, public_key_base64=public_key, current_mac=selected_mac, now=BASE_TIME
    )))

    return {
        "status": "PASS",
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "python": platform.python_version(),
        "algorithm": "MAC normalization -> SHA-256 -> Ed25519",
        "passed_count": len(scenarios),
        "total_count": len(scenarios),
        "private_key_persisted": False,
        "raw_mac_persisted": False,
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run()
    except Exception as exc:
        result = {"status": "FAIL", "error_type": type(exc).__name__, "message": str(exc)}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": result.get("passed_count", 0), "total": result.get("total_count", 0)}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
