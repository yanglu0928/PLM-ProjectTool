"""Preserve the 13 new OCR distributions' exact notice bytes separately.

This is a NON-RELEASE evidence sidecar, not corresponding source or clearance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import digest_path
from package_windows_unified_candidate import safe_name, zip_members
from plan_windows_unified_install import CANDIDATE_SHA256


GAPS_SHA256 = "b0deecb9cd6c422ded0a5aa95cd08a93f488199a3025b2cb09f6ec08fd54f717"
SOURCE_PREFIX = "payload/runtime/packages/"


def expected_entries(report: dict) -> list[dict]:
    if (report.get("status") != "EVIDENCE_GAPS_IDENTIFIED_NOT_LEGAL_CLEARANCE"
            or report.get("release_eligible") is not False
            or report.get("candidate_sha256") != CANDIDATE_SHA256):
        raise ValueError("license-gap report identity rejected")
    distributions = report.get("new_python_distributions", [])
    if len(distributions) != 13:
        raise ValueError("expected 13 new OCR distributions")
    entries = []
    for item in distributions:
        if item.get("review_status") != "REVIEW_REQUIRED" or item.get("standalone_notice_sidecar_present") is not False:
            raise ValueError("distribution review/sidecar status changed")
        for notice in item.get("embedded_notice_files", []):
            source = safe_name(notice["path"])
            if not source.startswith(SOURCE_PREFIX):
                raise ValueError("OCR notice source path rejected")
            target = safe_name("notices/" + source[len(SOURCE_PREFIX):])
            digest = notice["sha256"]
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("OCR notice source digest rejected")
            entries.append({"path": target, "source_member": source, "sha256": digest,
                            "distribution": item["name"], "version": item["version"]})
    if len(entries) != 25 or len({row["path"].casefold() for row in entries}) != 25:
        raise ValueError("OCR notice source inventory changed")
    return sorted(entries, key=lambda row: row["path"])


def build_sidecar(candidate: Path, gaps: Path, output: Path) -> dict:
    if output.exists() or not output.parent.is_dir():
        raise ValueError("output already exists or parent missing")
    if digest_path(candidate) != CANDIDATE_SHA256 or digest_path(gaps) != GAPS_SHA256:
        raise ValueError("fixed source identity mismatch")
    report = json.loads(gaps.read_text(encoding="utf-8"))
    entries = expected_entries(report)
    with zipfile.ZipFile(candidate) as source:
        members = zip_members(source)
        prepared = []
        for row in entries:
            if row["source_member"] not in members:
                raise ValueError("OCR notice missing from candidate")
            data = source.read(row["source_member"])
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("OCR notice bytes differ from gap report")
            prepared.append((row, data))
    manifest = {
        "kind": "WINDOWS11_OCR_PYTHON_NOTICES_NON_RELEASE",
        "release_eligible": False,
        "review_status": "REVIEW_REQUIRED",
        "candidate_sha256": CANDIDATE_SHA256,
        "gap_report_sha256": GAPS_SHA256,
        "distribution_count": 13,
        "notice_file_count": len(prepared),
        "corresponding_source_included": False,
        "legal_clearance": False,
        "files": [row for row, _ in prepared],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for row, data in prepared:
            bundle.writestr(row["path"], data)
        bundle.writestr("manifest.json", manifest_bytes)
    with zipfile.ZipFile(output) as bundle:
        actual = zip_members(bundle)
        if set(actual) != {"manifest.json", *(row["path"] for row, _ in prepared)}:
            raise ValueError("OCR notice sidecar member set changed")
        if bundle.read("manifest.json") != manifest_bytes:
            raise ValueError("OCR notice sidecar manifest changed")
        for row, _ in prepared:
            if hashlib.sha256(bundle.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("OCR notice sidecar bytes changed")
    return {"status": "OCR_PYTHON_NOTICE_SIDECAR_INTEGRITY_PASS", "release_eligible": False,
            "archive_sha256": digest_path(output), "distribution_count": 13,
            "notice_file_count": 25, "archive_bytes": output.stat().st_size,
            "archive": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--gaps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_sidecar(args.candidate, args.gaps, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
