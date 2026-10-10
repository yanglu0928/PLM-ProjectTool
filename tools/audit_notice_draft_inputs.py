"""Collect factual Python notice gaps for a non-release legal review draft."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

from audit_ghostscript_source_release_gaps import audit as audit_release


FIRST_PARTY = "plm-project-tool-backend"
SIDECAR_PREFIX = "payload/third-party-licenses/notices/"
EMBEDDED_PREFIX = "payload/runtime/packages/"


def normalized(value: str) -> str:
    return re.sub(r"[-_.]+", "_", value).casefold()


def summarize_python(distributions: list[dict], names: set[str]) -> dict:
    identities = {(normalized(row["name"]), row["version"]) for row in distributions}
    if len(identities) != len(distributions):
        raise ValueError("duplicate Python distribution identity")
    first_party = [row for row in distributions if normalized(row["name"]) ==
                   normalized(FIRST_PARTY)]
    if len(first_party) != 1:
        raise ValueError("first-party backend distribution identity differs")
    external = [row for row in distributions if row is not first_party[0]]
    missing_expression = []
    no_embedded = []
    no_notice_material = []
    sidecars = [name for name in names if name.startswith(SIDECAR_PREFIX)]
    for row in external:
        notice_paths = row.get("notice_files", [])
        if len(notice_paths) != row.get("notice_file_count"):
            raise ValueError("Python notice metadata count differs")
        if any(EMBEDDED_PREFIX + path not in names for path in notice_paths):
            raise ValueError("declared embedded Python notice missing")
        if not row.get("license_expression", "").strip():
            missing_expression.append(row["name"])
        if not notice_paths:
            no_embedded.append(row["name"])
            key = normalized(row["name"]) + "_" + normalized(row["version"]) + "_"
            standalone = any(normalized(name.split("/")[3]).startswith(key)
                             for name in sidecars)
            if not standalone:
                no_notice_material.append(row["name"])
    return {"python_distribution_count": len(distributions),
            "first_party_distribution_count": 1,
            "third_party_distribution_count": len(external),
            "third_party_missing_license_expression_count": len(missing_expression),
            "third_party_missing_license_expression_names": sorted(missing_expression, key=str.casefold),
            "third_party_no_embedded_notice_names": sorted(no_embedded, key=str.casefold),
            "third_party_no_notice_material_names": sorted(no_notice_material, key=str.casefold)}


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path) -> dict:
    release = audit_release(candidate, parent, ancestor, native_matrix)
    with zipfile.ZipFile(candidate) as archive:
        names = set(archive.namelist())
        inventory = json.loads(archive.read("third-party-inventory.json"))
    rows = inventory["base"]["unified"]["distributions"]
    summary = summarize_python(rows, names)
    if (summary["python_distribution_count"] != 106
            or summary["third_party_distribution_count"] != 105
            or summary["third_party_missing_license_expression_count"] != 60
            or summary["third_party_no_notice_material_names"] != ["bce-python-sdk"]):
        raise ValueError("P43 Python notice review input differs")
    return {"status": "NOTICE_DRAFT_INPUTS_VERIFIED_REVIEW_REQUIRED",
            "candidate_sha256": release["candidate_sha256"],
            "release_eligible": False, "legal_clearance": False,
            **summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--ancestor", type=Path, required=True)
    parser.add_argument("--native-matrix", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.ancestor,
                           args.native_matrix), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
