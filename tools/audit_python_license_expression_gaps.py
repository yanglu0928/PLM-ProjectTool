"""Map Python distributions with blank license expressions to exact candidate evidence.

Presence of a license text or legacy metadata is not legal clearance.
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


def map_gaps(rows: list[dict], archive: zipfile.ZipFile) -> list[dict]:
    names = set(archive.namelist())
    metadata_by_identity: dict[tuple[str, str], list[tuple[str, bytes]]] = {}
    for path in sorted(names):
        if not (path.startswith(EMBEDDED_PREFIX) and path.endswith(".dist-info/METADATA")):
            continue
        body = archive.read(path)
        meta = email.message_from_bytes(body)
        identity = (normalized(meta.get("Name", "")), meta.get("Version", ""))
        metadata_by_identity.setdefault(identity, []).append((path, body))

    result = []
    for row in rows:
        if normalized(row["name"]) == normalized("plm-project-tool-backend"):
            continue
        if row.get("license_expression", "").strip():
            continue
        identity = (normalized(row["name"]), row["version"])
        metadata = metadata_by_identity.get(identity, [])
        if len(metadata) != 1:
            raise ValueError(f"ambiguous or missing exact METADATA: {row['name']}")
        metadata_path, body = metadata[0]
        meta = email.message_from_bytes(body)
        if (meta.get("License-Expression", "").strip()
                or len(row.get("notice_files", [])) != row.get("notice_file_count")
                or row.get("review_status") != "REVIEW_REQUIRED"):
            raise ValueError(f"inventory/metadata review boundary differs: {row['name']}")
        embedded = sorted(EMBEDDED_PREFIX + path for path in row["notice_files"])
        if any(path not in names for path in embedded):
            raise ValueError(f"declared embedded notice missing: {row['name']}")
        sidecar_key = normalized(row["name"]) + "_" + normalized(row["version"]) + "_"
        sidecars = sorted(path for path in names if path.startswith(SIDECAR_PREFIX)
                          and normalized(path.split("/")[3]).startswith(sidecar_key))
        material_class = ("EMBEDDED" if embedded else
                          "SIDECAR_ONLY" if sidecars else "NO_DISTRIBUTION_NOTICE")
        result.append({"name": row["name"], "version": row["version"],
                       "metadata_path": metadata_path,
                       "legacy_license_field_present": bool(meta.get("License", "").strip()),
                       "license_classifier_count": len(row.get("license_classifiers", [])),
                       "embedded_notice_paths": embedded, "sidecar_paths": sidecars,
                       "material_class": material_class,
                       "review_status": "REVIEW_REQUIRED"})
    return sorted(result, key=lambda item: (item["name"].casefold(), item["version"]))


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path) -> dict:
    notice = audit_notice(candidate, parent, ancestor, native_matrix)
    with zipfile.ZipFile(candidate) as archive:
        inventory = json.loads(archive.read("third-party-inventory.json"))
        rows = map_gaps(inventory["base"]["unified"]["distributions"], archive)
    expected = notice["third_party_missing_license_expression_names"]
    if len(rows) != 60 or [row["name"] for row in rows] != expected:
        raise ValueError("60-item blank-expression inventory differs")
    counts = Counter(row["material_class"] for row in rows)
    if counts["NO_DISTRIBUTION_NOTICE"] != 1 or next(
            row["name"] for row in rows if row["material_class"] == "NO_DISTRIBUTION_NOTICE") != "bce-python-sdk":
        raise ValueError("bce sole missing-notice boundary differs")
    return {"status": "PYTHON_LICENSE_EXPRESSION_GAPS_MAPPED_REVIEW_REQUIRED",
            "candidate_sha256": notice["candidate_sha256"],
            "release_eligible": False, "legal_clearance": False,
            "blank_expression_count": len(rows),
            "material_classes": dict(sorted(counts.items())), "rows": rows}


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
