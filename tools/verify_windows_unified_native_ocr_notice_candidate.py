"""Independently verify fixed NON-RELEASE native OCR notice ZIP lineage."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from build_windows_unified_native_ocr_notice_candidate import KIND, INDEX, PREFIX, README
from package_windows_unified_candidate import NO_JBIG_CSV_SHA256
from plan_windows_unified_pg18_composition import inspect
from verify_windows_unified_ghostscript_source_candidate import (
    ARCHIVE_SHA256 as P43_SHA256, verify as verify_parent,
)


ARCHIVE_SHA256 = "30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98"
ARCHIVE_BYTES = 652122261


def check_lineage(manifest: dict, inventory: dict, index: dict,
                  hashes: dict[str, str], parent_hashes: dict[str, str],
                  matrix_rows: list[dict]) -> None:
    additions = {name: sha for name, sha in hashes.items() if name not in parent_hashes}
    text_paths = {name for name in additions if name.startswith(PREFIX + "texts/")}
    if (len(parent_hashes) != 21114 or len(hashes) != 21158
            or any(hashes.get(name) != sha for name, sha in parent_hashes.items())
            or set(additions) != text_paths | {INDEX.casefold(), README.casefold()}
            or len(text_paths) != 42
            or any(name != PREFIX + "texts/" + sha + ".txt" for name, sha in
                   ((name, additions[name]) for name in text_paths))):
        raise ValueError("native OCR candidate payload lineage differs")
    mapping_sha = hashes[INDEX.casefold()]
    native = inventory.get("native_ocr_license_evidence", {})
    if (manifest.get("source_p43_sha256") != P43_SHA256
            or manifest.get("native_ocr_license_evidence_added") is not True
            or manifest.get("native_ocr_review_map_sha256") != mapping_sha
            or any(manifest.get(key) is not False for key in (
                "release_eligible", "legal_clearance", "installation_performed",
                "service_registration_performed", "formal_tls_material_included"))
            or inventory.get("review_status") != "REVIEW_REQUIRED"
            or native.get("binary_count") != 34
            or native.get("evidence_record_count") != 61
            or native.get("unique_text_count") != 42
            or native.get("mapping_path") != INDEX
            or native.get("mapping_sha256") != mapping_sha
            or native.get("review_status") != "REVIEW_REQUIRED"
            or native.get("legal_clearance") is not False):
        raise ValueError("native OCR candidate non-release metadata differs")
    if (index.get("source_p43_sha256") != P43_SHA256
            or index.get("source_matrix_sha256") != NO_JBIG_CSV_SHA256
            or index.get("binary_count") != 34
            or index.get("evidence_record_count") != 61
            or index.get("unique_text_count") != 42
            or index.get("review_status") != "REVIEW_REQUIRED"
            or index.get("legal_clearance") is not False
            or index.get("release_eligible") is not False):
        raise ValueError("native OCR review map boundary differs")
    evidence = index.get("evidence", [])
    matrix = {row["binary"]: row for row in matrix_rows}
    if len(matrix) != 34 or len(evidence) != 61:
        raise ValueError("native OCR review map population differs")
    seen = set()
    for item in evidence:
        binary = matrix.get(item.get("binary"))
        path = item.get("text_path")
        sha = item.get("text_sha256")
        if (binary is None or item.get("binary_sha256") != binary["binary_sha256"]
                or item.get("source_name") != binary["source_name"]
                or item.get("source_version") != binary["source_version"]
                or item.get("package_declared_license") != binary["package_declared_license"]
                or item.get("release_obligations_reviewed") != "NO"
                or path not in text_paths or hashes.get(path) != sha
                or path != PREFIX + "texts/" + sha + ".txt"):
            raise ValueError("native OCR review map evidence differs")
        key = item["binary"], item.get("source_member"), sha
        if key in seen:
            raise ValueError("native OCR review map duplicate evidence")
        seen.add(key)
    if {item["binary"] for item in evidence} != set(matrix):
        raise ValueError("native OCR review map binary coverage differs")
    for binary, row in matrix.items():
        expected = sorted(zip(
            (value.strip() for value in row["license_evidence_path"].split(" | ")),
            (value.strip() for value in row["license_evidence_sha256"].split(" | "))))
        actual = []
        for item in evidence:
            if item["binary"] != binary:
                continue
            member = item["source_member"]
            if item["evidence_kind"] == "UPSTREAM_FALLBACK_MEMBER":
                member = item["source_archive_name"].removeprefix("msys2-source-") + "/" + member
            elif (item["evidence_kind"] not in {"PACKAGE_MEMBER", "UPSTREAM_BUILD_MEMBER"}
                  or item["source_archive_sha256"] != row["source_sha256"]):
                raise ValueError(f"native OCR source archive attribution differs: {binary}")
            actual.append((member, item["text_sha256"]))
        actual.sort()
        if expected != actual:
            raise ValueError(f"native OCR matrix text coverage differs: {binary}")


def verify(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
           native_matrix: Path) -> dict:
    if not candidate.is_file() or candidate.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("native OCR candidate archive size differs")
    manifest, hashes = inspect(candidate, ARCHIVE_SHA256, KIND, 21158)
    parent_identity = verify_parent(parent, ancestor, grandparent)
    with zipfile.ZipFile(parent) as original:
        parent_hashes = {}
        for line in original.read("payload-sha256sums.txt").decode("ascii").splitlines():
            sha, _, name = line.partition("  ")
            parent_hashes[name.casefold()] = sha
    if parent_identity["payload_file_count"] != len(parent_hashes):
        raise ValueError("P43 parent hash count differs")
    with zipfile.ZipFile(candidate) as archive:
        inventory = json.loads(archive.read("third-party-inventory.json"))
        index = json.loads(archive.read(INDEX))
        if not archive.read(README).startswith(b"Native OCR third-party license-text review inputs."):
            raise ValueError("native OCR review README differs")
    if hashlib.sha256(native_matrix.read_bytes()).hexdigest() != NO_JBIG_CSV_SHA256:
        raise ValueError("native OCR matrix identity differs")
    with native_matrix.open("r", encoding="utf-8", newline="") as stream:
        matrix_rows = list(csv.DictReader(stream))
    check_lineage(manifest, inventory, index, hashes, parent_hashes, matrix_rows)
    return {"status": "NON_RELEASE_NATIVE_OCR_NOTICE_INDEPENDENT_VERIFY_PASS",
            "archive_sha256": ARCHIVE_SHA256, "archive_bytes": ARCHIVE_BYTES,
            "payload_file_count": len(hashes),
            "unchanged_parent_payload_count": len(parent_hashes),
            "added_license_text_count": 42, "added_mapping_and_readme_count": 2,
            "source_p43_sha256": parent_identity["archive_sha256"],
            "release_eligible": False, "legal_clearance": False,
            "installation_performed": False, "service_registration_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate, args.parent, args.ancestor,
                            args.grandparent, args.native_matrix),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
