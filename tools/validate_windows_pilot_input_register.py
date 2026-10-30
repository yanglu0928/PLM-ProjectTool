"""Validate non-secret Windows Pilot input references without echoing values."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DATABASE_CREDENTIAL_TARGET = "PLMProjectTool/Database"
REFERENCE_PATTERNS = {
    "product_public_key_sha256": re.compile(r"^[0-9a-fA-F]{64}$"),
    "license_evidence_ref": re.compile(r"^LIC-[A-Z0-9][A-Z0-9-]{0,47}$"),
    "service_identity_ref": re.compile(r"^NT SERVICE\\[A-Za-z0-9._-]{1,64}$"),
    "tls_certificate_thumbprint": re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$"),
    "tls_dns_name": re.compile(
        r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}$"
    ),
}
REFERENCE_FIELDS = tuple(REFERENCE_PATTERNS) + ("database_credential_target",)
EVIDENCE_FIELDS = ("license", "service_acl", "tls_chain_renewal", "database_scope")
EVIDENCE_PATTERN = re.compile(r"^EVD-[A-Z0-9][A-Z0-9-]{0,47}$")


def _has_exact_keys(value: Any, expected: tuple[str, ...]) -> bool:
    return isinstance(value, dict) and set(value) == set(expected)


def validate_register(payload: Any) -> dict[str, Any]:
    """Return only fixed issue codes and field names; never include supplied values."""
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "references", "evidence_refs"}:
        return {"status": "INVALID", "issues": ["ROOT_SHAPE_INVALID"], "missing_fields": []}
    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        return {"status": "INVALID", "issues": ["SCHEMA_VERSION_INVALID"], "missing_fields": []}

    refs = payload.get("references")
    evidence = payload.get("evidence_refs")
    if not _has_exact_keys(refs, REFERENCE_FIELDS) or not _has_exact_keys(evidence, EVIDENCE_FIELDS):
        return {"status": "INVALID", "issues": ["REGISTER_SHAPE_INVALID"], "missing_fields": []}

    issues: list[str] = []
    missing: list[str] = []
    for field, pattern in REFERENCE_PATTERNS.items():
        value = refs[field]
        if value is None:
            missing.append(field)
        elif not isinstance(value, str) or not pattern.fullmatch(value):
            issues.append("REFERENCE_FORMAT_INVALID")

    target = refs["database_credential_target"]
    if target is None:
        missing.append("database_credential_target")
    elif target != DATABASE_CREDENTIAL_TARGET:
        issues.append("DATABASE_TARGET_INVALID")

    for field in EVIDENCE_FIELDS:
        value = evidence[field]
        if value is None:
            missing.append(f"evidence_refs.{field}")
        elif not isinstance(value, str) or not EVIDENCE_PATTERN.fullmatch(value):
            issues.append("EVIDENCE_REFERENCE_INVALID")

    if issues:
        return {"status": "INVALID", "issues": sorted(set(issues)), "missing_fields": []}
    if missing:
        return {"status": "INCOMPLETE", "issues": [], "missing_fields": sorted(missing)}
    return {"status": "COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION",
            "issues": [], "missing_fields": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        result = {"status": "INVALID", "issues": ["INPUT_UNREADABLE_OR_INVALID_JSON"],
                  "missing_fields": []}
        print(json.dumps(result, separators=(",", ":")))
        return 2
    result = validate_register(payload)
    print(json.dumps(result, separators=(",", ":")))
    return {"COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION": 0,
            "INCOMPLETE": 1, "INVALID": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
