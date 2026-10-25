"""Build a deterministic review queue from the fixed P22 CycloneDX SBOM.

SBOM metadata is evidence, not a conclusion about applicable license obligations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import ASSETS
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify


SBOM = "payload/third-party-licenses/caddy/windows_amd64.sbom"
FIELDS = ("bom_ref", "name", "version", "purl", "sbom_license", "review_status")


def _license_field(component: dict) -> str:
    values = []
    for entry in component.get("licenses", []):
        if not isinstance(entry, dict):
            raise ValueError("SBOM license entry invalid")
        value = entry.get("expression")
        if value is None:
            license_value = entry.get("license", {})
            if not isinstance(license_value, dict):
                raise ValueError("SBOM license item invalid")
            value = license_value.get("id") or license_value.get("name")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("SBOM license value invalid")
        values.append(value)
    return "; ".join(values) if values else "UNDECLARED_IN_SBOM"


def rows_from_sbom(sbom: dict) -> list[dict[str, str]]:
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6":
        raise ValueError("SBOM format/version rejected")
    components = sbom.get("components")
    if not isinstance(components, list) or len(components) != 149:
        raise ValueError("fixed Caddy SBOM component count changed")
    rows = []
    refs = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("SBOM component invalid")
        ref, name, version = (component.get(key) for key in ("bom-ref", "name", "version"))
        if (not all(isinstance(value, str) and value for value in (ref, name))
                or version is not None and (not isinstance(version, str) or not version)
                or ref in refs):
            raise ValueError("SBOM identity missing or duplicate")
        refs.add(ref)
        purl = component.get("purl", "")
        if not isinstance(purl, str):
            raise ValueError("SBOM purl invalid")
        rows.append({"bom_ref": ref, "name": name, "version": version or "",
                     "purl": purl, "sbom_license": _license_field(component),
                     "review_status": "REVIEW_REQUIRED"})
    return sorted(rows, key=lambda row: row["bom_ref"].casefold())


def serialize_csv(rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def build(candidate: Path) -> tuple[bytes, dict]:
    identity = verify(candidate)
    with zipfile.ZipFile(candidate) as archive:
        raw = archive.read(SBOM)
    if hashlib.sha256(raw).hexdigest() != ASSETS["windows_amd64.sbom"][1]:
        raise ValueError("fixed Caddy SBOM identity differs")
    rows = rows_from_sbom(json.loads(raw))
    csv_bytes = serialize_csv(rows)
    summary = {"status": "NON_RELEASE_CADDY_SBOM_REVIEW_QUEUE",
               "release_eligible": False, "candidate_sha256": ARCHIVE_SHA256,
               "payload_file_count": identity["payload_file_count"],
               "sbom_sha256": hashlib.sha256(raw).hexdigest(),
               "component_count": len(rows),
               "sbom_license_undeclared_count": sum(
                   row["sbom_license"] == "UNDECLARED_IN_SBOM" for row in rows),
               "purl_missing_count": sum(not row["purl"] for row in rows),
               "version_missing_count": sum(not row["version"] for row in rows),
               "review_required_count": len(rows),
               "queue_sha256": hashlib.sha256(csv_bytes).hexdigest(),
               "legal_clearance": False}
    return csv_bytes, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body, summary = build(args.candidate)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("queue output must be a new file in an existing directory")
    with args.output.open("xb") as stream:
        stream.write(body)
    if args.output.read_bytes() != body:
        raise ValueError("queue output readback differs")
    print(json.dumps({**summary, "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
