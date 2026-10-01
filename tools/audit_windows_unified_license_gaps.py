"""Inventory license/source evidence gaps in the pinned NON-RELEASE ZIP.

This is byte and metadata reconciliation, not a legal opinion or release gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import digest_path
from package_windows_unified_candidate import BASE_SHA256, NO_JBIG_CSV_SHA256, zip_members
from plan_windows_unified_install import CANDIDATE_SHA256


GHOSTSCRIPT_COPYING = "payload/ocr/ghostscript/doc/COPYING"
MODEL_READMES = (
    "payload/ocr/models/PP-OCRv5_mobile_det/README.md",
    "payload/ocr/models/PP-OCRv5_mobile_rec/README.md",
)


def _identity(row: dict) -> str:
    return row["name"].casefold().replace("_", "-")


def distribution_delta(old: dict, new: dict) -> list[dict]:
    if old.get("distribution_count") != 93 or new.get("distribution_count") != 106:
        raise ValueError("Python distribution counts differ from pinned inputs")
    prior = {_identity(row): row for row in old["distributions"]}
    current = {_identity(row): row for row in new["distributions"]}
    if len(prior) != 93 or len(current) != 106:
        raise ValueError("duplicate Python distribution identity")
    if any(name not in current or current[name]["version"] != row["version"]
           for name, row in prior.items()):
        raise ValueError("one of the original 93 Python distributions changed")
    extra = [current[name] for name in sorted(set(current) - set(prior))]
    if len(extra) != 13:
        raise ValueError("expected exactly 13 new OCR distributions")
    return extra


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit(base_path: Path, unified_path: Path, native_csv: Path, repo_root: Path) -> dict:
    if digest_path(base_path) != BASE_SHA256 or digest_path(unified_path) != CANDIDATE_SHA256:
        raise ValueError("candidate archive identity mismatch")
    if digest_path(native_csv) != NO_JBIG_CSV_SHA256:
        raise ValueError("34-PE evidence matrix identity mismatch")
    with native_csv.open("r", encoding="utf-8", newline="") as stream:
        native_rows = list(csv.DictReader(stream))
    if len(native_rows) != 34 or any(row["release_obligations_reviewed"] != "NO" for row in native_rows):
        raise ValueError("native evidence review status differs")
    with zipfile.ZipFile(base_path) as base, zipfile.ZipFile(unified_path) as unified:
        old_members = zip_members(base)
        new_members = zip_members(unified)
        old_inventory = json.loads(base.read("third-party-inventory.json"))
        new_inventory = json.loads(unified.read("third-party-inventory.json"))
        extra = distribution_delta(old_inventory, new_inventory)
        added = []
        for row in extra:
            notices = row["notice_files"]
            if not notices or len(notices) != row["notice_file_count"]:
                raise ValueError("new OCR distribution notice metadata incomplete")
            embedded = []
            for path in notices:
                member = "payload/runtime/packages/" + path
                if member not in new_members:
                    raise ValueError("embedded OCR notice missing from unified ZIP")
                embedded.append({"path": member, "sha256": _sha256(unified.read(member))})
            sidecar_prefix = "payload/third-party-licenses/notices/"
            wheel_prefix = row["name"].casefold().replace("-", "_") + "-" + row["version"].casefold()
            standalone = any(
                path.startswith(sidecar_prefix)
                and path[len(sidecar_prefix):].casefold().replace("-", "_").startswith(wheel_prefix)
                for path in new_members
            )
            added.append({
                "name": row["name"], "version": row["version"],
                "metadata_license_expression": row["license_expression"],
                "embedded_notice_files": embedded,
                "standalone_notice_sidecar_present": standalone,
                "corresponding_source_in_candidate": False,
                "review_status": "REVIEW_REQUIRED",
            })
        for row in native_rows:
            member = "payload/ocr/tesseract/" + row["binary"]
            if member not in new_members or _sha256(unified.read(member)) != row["binary_sha256"]:
                raise ValueError("native PE bytes differ from 34-row source matrix")
        if GHOSTSCRIPT_COPYING not in new_members:
            raise ValueError("Ghostscript AGPL text missing")
        models = []
        for member in MODEL_READMES:
            if member not in new_members:
                raise ValueError("Paddle model README missing")
            data = unified.read(member)
            if b"license: apache-2.0" not in data[:256].lower():
                raise ValueError("Paddle model README license metadata changed")
            models.append({"path": member, "sha256": _sha256(data),
                           "metadata_license": "apache-2.0", "separate_model_license_text_in_candidate": False})
        old_notice_files = sum(name.startswith("payload/third-party-licenses/notices/") for name in old_members)
        new_notice_files = sum(name.startswith("payload/third-party-licenses/notices/") for name in new_members)
        if new_notice_files != old_notice_files:
            raise ValueError("historical standalone license sidecar changed")
        source_payload_paths = [name for name in new_members if name.startswith("payload/third-party-sources/")]
        return {
            "schema_version": "plm.windows-unified-license-gaps.v1",
            "status": "EVIDENCE_GAPS_IDENTIFIED_NOT_LEGAL_CLEARANCE",
            "release_eligible": False,
            "candidate_sha256": CANDIDATE_SHA256,
            "baseline_sha256": BASE_SHA256,
            "native_matrix_sha256": NO_JBIG_CSV_SHA256,
            "existing_python_distributions_unchanged": 93,
            "new_python_distributions": added,
            "historical_standalone_notice_file_count": old_notice_files,
            "native_pe_count": 34,
            "native_release_obligations_reviewed_count": 0,
            "ghostscript_agpl_text": {"path": GHOSTSCRIPT_COPYING,
                                       "sha256": _sha256(unified.read(GHOSTSCRIPT_COPYING))},
            "paddle_model_readmes": models,
            "corresponding_source_payload_file_count": len(source_payload_paths),
            "product_license_file_present": (repo_root / "LICENSE").is_file(),
            "product_notice_file_present": (repo_root / "NOTICE").is_file(),
            "open_actions": [
                "approve product license and provide root LICENSE/NOTICE",
                "reconcile exact applicable terms, copyright notices and source for 34 native PE files",
                "materialize standalone notices and source-delivery method for 13 added Python distributions",
                "supply exact Ghostscript corresponding source/build-install materials and confirm public source access",
                "verify model license text/provenance and final combined-work obligations",
                "obtain qualified legal review before any external release",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--unified", required=True, type=Path)
    parser.add_argument("--native-csv", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; historical evidence cannot be overwritten")
    report = audit(args.base, args.unified, args.native_csv, args.repo_root)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "added_python": len(report["new_python_distributions"]),
                      "native_open": 34, "release_eligible": False,
                      "output_sha256": digest_path(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
