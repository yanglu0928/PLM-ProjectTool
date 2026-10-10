"""Compare fixed parent/current non-release ZIP license evidence without legal approval."""

from __future__ import annotations

import argparse
import email
import json
import sys
import zipfile
from pathlib import Path

from package_windows_current_app_candidate import (
    APP_PREFIX, DIST_PREFIX, FRONTEND_PREFIX, PARENT_SHA256, SIDE_CARS, _checksums,
)
from package_windows_unified_candidate import digest_path, zip_members


CURRENT_SHA256 = "eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7"
KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
PRODUCT_LICENSE = {"LICENSE", "LICENSE.txt", "payload/LICENSE", "payload/LICENSE.txt"}
PRODUCT_NOTICE = {"NOTICE", "NOTICE.txt", "payload/NOTICE", "payload/NOTICE.txt"}


def audit(parent_path: Path, current_path: Path, *, parent_sha: str = PARENT_SHA256,
          current_sha: str = CURRENT_SHA256) -> dict[str, object]:
    if digest_path(parent_path) != parent_sha or digest_path(current_path) != current_sha:
        raise ValueError("candidate SHA-256 identity differs")
    with zipfile.ZipFile(parent_path) as parent, zipfile.ZipFile(current_path) as current:
        old_names, new_names = set(zip_members(parent)), set(zip_members(current))
        if SIDE_CARS - old_names or SIDE_CARS - new_names:
            raise ValueError("candidate sidecars missing")
        old_hashes = _checksums(parent.read("payload-sha256sums.txt"))
        new_hashes = _checksums(current.read("payload-sha256sums.txt"))
        if (set(old_hashes) != old_names - SIDE_CARS or
                set(new_hashes) != new_names - SIDE_CARS):
            raise ValueError("candidate payload inventory differs")
        old_manifest = json.loads(parent.read("manifest.json"))
        new_manifest = json.loads(current.read("manifest.json"))
        if (new_manifest.get("kind") != KIND or
                new_manifest.get("parent_candidate_sha256") != parent_sha or
                new_manifest.get("release_eligible") is not False or
                new_manifest.get("legal_clearance") is not False or
                new_manifest.get("formal_tls_material_included") is not False or
                old_manifest.get("release_eligible") is not False or
                old_manifest.get("legal_clearance") is not False or
                old_manifest.get("payload_file_count") != len(old_hashes) or
                new_manifest.get("payload_file_count") != len(new_hashes)):
            raise ValueError("candidate provenance or release boundary differs")
        if parent.read("third-party-inventory.json") != current.read("third-party-inventory.json"):
            raise ValueError("third-party inventory bytes changed")
        replaced = (APP_PREFIX, DIST_PREFIX, FRONTEND_PREFIX)
        retained = {name for name in old_hashes if not name.startswith(replaced)}
        current_retained = {name for name in new_hashes if not name.startswith(replaced)}
        if retained != current_retained or any(old_hashes[name] != new_hashes[name]
                                                for name in retained):
            raise ValueError("third-party/runtime payload changed")
        metadata_path = DIST_PREFIX + "METADATA"
        if metadata_path not in old_hashes or metadata_path not in new_hashes:
            raise ValueError("own backend metadata missing")
        old_metadata = email.message_from_bytes(parent.read(metadata_path))
        new_metadata = email.message_from_bytes(current.read(metadata_path))
        old_requirements = old_metadata.get_all("Requires-Dist") or []
        new_requirements = new_metadata.get_all("Requires-Dist") or []
        if (old_metadata.get("Version") != new_metadata.get("Version") or
                sorted(old_requirements) != sorted(new_requirements)):
            raise ValueError("backend third-party requirement declaration changed")
        inventory = json.loads(current.read("third-party-inventory.json"))
        unified = inventory["base"]["unified"]
        distributions = unified["distributions"]
        own = [item for item in distributions if item["name"] == "plm-project-tool-backend"]
        if (unified["distribution_count"] != len(distributions) or len(own) != 1 or
                len({item["name"].casefold() for item in distributions}) != len(distributions) or
                any(item["review_status"] != "REVIEW_REQUIRED" for item in distributions) or
                inventory.get("review_status") != "REVIEW_REQUIRED"):
            raise ValueError("third-party distribution review population differs")
        native = inventory["native_ocr_license_evidence"]
        mapping = native["mapping_path"]
        if (mapping not in retained or old_hashes[mapping] != new_hashes[mapping] or
                native.get("legal_clearance") is not False or
                native.get("review_status") != "REVIEW_REQUIRED"):
            raise ValueError("native OCR review mapping differs")
        review = json.loads(current.read(mapping))
        texts = {item["text_path"]: item["text_sha256"] for item in review["evidence"]}
        if (len(review["evidence"]) != native["evidence_record_count"] or
                len(texts) != native["unique_text_count"] or
                any(name not in retained or new_hashes[name] != sha for name, sha in texts.items())):
            raise ValueError("native OCR review text identity differs")
        if PRODUCT_LICENSE & new_names or PRODUCT_NOTICE & new_names:
            raise ValueError("unexpected product-level declaration requires separate review")
        return {
            "status": "CURRENT_APP_LICENSE_EVIDENCE_INHERITANCE_PASS_LEGAL_OPEN",
            "parent_sha256": parent_sha, "current_sha256": current_sha,
            "source_git_commit": new_manifest.get("source_git_commit"),
            "retained_non_app_file_count": len(retained),
            "third_party_python_distribution_count": len(distributions) - len(own),
            "backend_declared_requirement_count": len(new_requirements),
            "native_ocr_evidence_record_count": len(review["evidence"]),
            "native_ocr_unique_text_count": len(texts),
            "product_license_present": False, "product_notice_present": False,
            "legal_clearance": False, "release_eligible": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.parent, args.current), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
