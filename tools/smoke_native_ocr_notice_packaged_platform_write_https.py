"""Exercise fixed native OCR notice package behind synthetic HTTPS and temporary PG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rehearse_windows_unified_native_ocr_notice_layout import rehearse as place_layout
from smoke_native_ocr_notice_layout_https import verify_layout
from smoke_packaged_platform_write_https import smoke as original_smoke
from verify_windows_unified_native_ocr_notice_candidate import ARCHIVE_SHA256


def smoke(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
          native_matrix: Path, stage: Path, pristine: Path, target: Path) -> dict:
    def check_fixed(archive: Path, source: Path, source_stage: Path, layout: Path) -> dict:
        if source != parent:
            raise ValueError("native OCR notice parent differs")
        return verify_layout(archive, parent, ancestor, grandparent,
                             native_matrix, source_stage, layout)

    def place_fixed(archive: Path, source: Path, source_stage: Path, layout: Path) -> dict:
        if source != parent:
            raise ValueError("native OCR notice parent differs")
        return place_layout(archive, parent, ancestor, grandparent,
                            native_matrix, source_stage, layout)

    result = original_smoke(candidate, parent, stage, pristine, target,
                            layout_verifier=check_fixed, layout_rehearser=place_fixed)
    if (result.get("synthetic_layout_file_count_before_injection") != 21161
            or result.get("fixed_candidate_unmodified") is not True
            or result.get("synthetic_vault_targets_absent") is not True
            or result.get("temporary_processes_stopped") is not True
            or result.get("temporary_files_removed") is not True
            or result.get("formal_trust_provisioned") is not False
            or result.get("release_eligible") is not False):
        raise ValueError("native OCR notice packaged login boundary differs")
    return {**result, "status": "SYNTHETIC_NATIVE_OCR_NOTICE_PACKAGED_PLATFORM_WRITE_HTTPS_PASS",
            "candidate_sha256": ARCHIVE_SHA256, "legal_clearance": False,
            "license_text_count": 42, "evidence_record_count": 61}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix",
                 "stage", "pristine", "target"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.parent, args.ancestor,
                           args.grandparent, args.native_matrix, args.stage,
                           args.pristine, args.target), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
