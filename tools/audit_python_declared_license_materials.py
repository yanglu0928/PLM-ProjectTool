"""Verify declared Python license expressions and assemble 105 review inputs.

Exact metadata and file presence are technical evidence, never legal clearance.
"""

from __future__ import annotations

import argparse
import email
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from audit_notice_draft_inputs import EMBEDDED_PREFIX, SIDECAR_PREFIX, audit as audit_notice, normalized
from audit_python_license_expression_gaps import map_gaps


def map_declared(rows: list[dict], archive: zipfile.ZipFile) -> list[dict]:
    names = set(archive.namelist())
    metadata: dict[tuple[str, str], list[tuple[str, bytes]]] = {}
    for path in sorted(names):
        if not (path.startswith(EMBEDDED_PREFIX) and path.endswith(".dist-info/METADATA")):
            continue
        body = archive.read(path)
        parsed = email.message_from_bytes(body)
        metadata.setdefault((normalized(parsed.get("Name", "")), parsed.get("Version", "")), []).append((path, body))

    result = []
    for row in rows:
        if normalized(row["name"]) == normalized("plm-project-tool-backend"):
            continue
        expression = row.get("license_expression", "").strip()
        if not expression:
            continue
        identity = (normalized(row["name"]), row["version"])
        matches = metadata.get(identity, [])
        if len(matches) != 1 or row.get("review_status") != "REVIEW_REQUIRED":
            raise ValueError(f"declared distribution identity/review differs: {row['name']}")
        metadata_path, body = matches[0]
        parsed = email.message_from_bytes(body)
        if parsed.get("License-Expression") != expression:
            raise ValueError(f"declared expression differs from METADATA: {row['name']}")
        embedded = sorted(EMBEDDED_PREFIX + path for path in row.get("notice_files", []))
        if (len(embedded) != row.get("notice_file_count") or not embedded
                or any(path not in names for path in embedded)):
            raise ValueError(f"declared embedded notice inventory differs: {row['name']}")
        dist_info_prefix = metadata_path.removesuffix("METADATA")
        license_headers = parsed.get_all("License-File", [])
        if not license_headers or any(
                dist_info_prefix + "licenses/" + value not in embedded for value in license_headers):
            raise ValueError(f"declared License-File header has no exact notice: {row['name']}")
        sidecar_key = normalized(row["name"]) + "_" + normalized(row["version"]) + "_"
        sidecars = sorted(path for path in names if path.startswith(SIDECAR_PREFIX)
                          and normalized(path.split("/")[3]).startswith(sidecar_key))
        result.append({"name": row["name"], "version": row["version"],
                       "license_expression": expression, "metadata_path": metadata_path,
                       "license_file_headers": license_headers,
                       "legacy_license_field_present": bool(parsed.get("License", "").strip()),
                       "license_classifier_count": len(row.get("license_classifiers", [])),
                       "embedded_notice_paths": embedded, "sidecar_paths": sidecars,
                       "material_class": "EMBEDDED", "review_status": "REVIEW_REQUIRED"})
    return sorted(result, key=lambda item: (item["name"].casefold(), item["version"]))


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path) -> dict:
    notice = audit_notice(candidate, parent, ancestor, native_matrix)
    with zipfile.ZipFile(candidate) as archive:
        rows = json.loads(archive.read("third-party-inventory.json"))["base"]["unified"]["distributions"]
        gaps = map_gaps(rows, archive)
        declared = map_declared(rows, archive)
    if len(gaps) != 60 or len(declared) != 45:
        raise ValueError("Python 60+45 review population differs")
    identities = [(normalized(row["name"]), row["version"]) for row in gaps + declared]
    if len(set(identities)) != 105 or len(rows) != 106:
        raise ValueError("105 third-party review inputs have overlap or omission")
    combined = sorted([{**row, "license_expression": "", "license_file_headers": []}
                       for row in gaps] + declared,
                      key=lambda row: (row["name"].casefold(), row["version"]))
    return {"status": "PYTHON_105_REVIEW_INPUTS_MAPPED_LEGAL_REVIEW_REQUIRED",
            "candidate_sha256": notice["candidate_sha256"],
            "release_eligible": False, "legal_clearance": False,
            "first_party_count": 1, "third_party_count": len(combined),
            "blank_expression_count": len(gaps), "declared_expression_count": len(declared),
            "declared_expression_values": dict(sorted(Counter(row["license_expression"] for row in declared).items())),
            "material_classes": dict(sorted(Counter(row["material_class"] for row in combined).items())),
            "rows": combined}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "native-matrix"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.ancestor,
                           args.native_matrix), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
