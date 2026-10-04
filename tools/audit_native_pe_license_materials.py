"""Map 34 native OCR PE bytes and source-license evidence into fixed candidate.

Identical generic text elsewhere in the candidate is not component attribution.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from audit_ghostscript_source_release_gaps import audit as audit_release


LEGAL_NAME = re.compile(r"(?:^|/)(?:license|licence|copying|notice)(?:[._/-]|$)", re.I)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NATIVE_PREFIX = "payload/ocr/tesseract/"
DEDICATED_NOTICE_PREFIX = "payload/third-party-licenses/native-ocr/"


def map_native(rows: list[dict], archive: zipfile.ZipFile) -> dict:
    names = set(archive.namelist())
    if any(name.startswith(DEDICATED_NOTICE_PREFIX) for name in names):
        raise ValueError("dedicated native OCR notice namespace changed")
    legal_paths = sorted(name for name in names if LEGAL_NAME.search(name) and not name.endswith("/"))
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in legal_paths:
        by_hash[hashlib.sha256(archive.read(path)).hexdigest()].append(path)
    mapped = []
    all_evidence = 0
    matching_text = 0
    for row in rows:
        binary = row["binary"]
        if "/" in binary or "\\" in binary or row["release_obligations_reviewed"] != "NO":
            raise ValueError(f"native PE review boundary differs: {binary}")
        package_path = NATIVE_PREFIX + binary
        if package_path not in names or hashlib.sha256(archive.read(package_path)).hexdigest() != row["binary_sha256"]:
            raise ValueError(f"native PE candidate byte identity differs: {binary}")
        paths = [value.strip() for value in row["license_evidence_path"].split(" | ")]
        hashes = [value.strip() for value in row["license_evidence_sha256"].split(" | ")]
        if not paths or len(paths) != len(hashes) or any(not HEX64.fullmatch(value) for value in hashes):
            raise ValueError(f"native PE license evidence list differs: {binary}")
        evidence = [{"matrix_source_path": path, "sha256": sha,
                     "same_text_candidate_paths": by_hash.get(sha, [])}
                    for path, sha in zip(paths, hashes)]
        all_evidence += len(evidence)
        matching_text += sum(bool(item["same_text_candidate_paths"]) for item in evidence)
        mapped.append({"binary": binary, "candidate_path": package_path,
                       "binary_sha256": row["binary_sha256"],
                       "source_kind": row["source_kind"], "source_name": row["source_name"],
                       "source_version": row["source_version"],
                       "package_declared_license": row["package_declared_license"],
                       "license_evidence_status": row["license_evidence_status"],
                       "evidence": evidence, "dedicated_notice_present": False,
                       "release_obligations_reviewed": "NO"})
    if len(mapped) != 34 or len({row["binary"].casefold() for row in mapped}) != 34:
        raise ValueError("34 native PE binary identities differ")
    return {"native_pe_count": len(mapped), "candidate_legal_path_count": len(legal_paths),
            "matrix_evidence_count": all_evidence,
            "same_text_evidence_count": matching_text,
            "dedicated_native_notice_count": 0,
            "evidence_status_counts": dict(sorted(Counter(
                row["license_evidence_status"] for row in mapped).items())),
            "rows": sorted(mapped, key=lambda item: item["binary"].casefold())}


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path) -> dict:
    release = audit_release(candidate, parent, ancestor, native_matrix)
    with native_matrix.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with zipfile.ZipFile(candidate) as archive:
        summary = map_native(rows, archive)
    return {"status": "NATIVE_PE_BYTES_VERIFIED_NOTICE_REVIEW_OPEN",
            "candidate_sha256": release["candidate_sha256"],
            "native_matrix_sha256": release["native_matrix_sha256"],
            "release_eligible": False, "legal_clearance": False, **summary}


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
