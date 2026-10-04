"""Check bce-python-sdk 0.9.79 license-text evidence without legal clearance."""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

from audit_ghostscript_source_input import digest
from verify_windows_unified_ghostscript_source_candidate import (
    ARCHIVE_SHA256, verify,
)


WHEEL_SHA256 = "71799ac8740505e0759d30873f6f1a478fa8f83aedf425d511f1419a5f30082e"
SDIST_SHA256 = "cd77476b43347ed28d0211d5ad557e524e1ec648bd093d57c6a6d3de075a7508"
APACHE_TEXT_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
METADATA = "payload/runtime/packages/bce_python_sdk-0.9.79.dist-info/METADATA"
CANDIDATE_LICENSE = "payload/third-party-licenses/caddy/LICENSE"
NOTICE_NAME = re.compile(r"(?:^|/)(?:license|licence|copying|notice)(?:[._-]|$)", re.IGNORECASE)


def check_metadata(body: bytes) -> None:
    message = email.message_from_bytes(body)
    if (message.get("Name") != "bce-python-sdk"
            or message.get("Version") != "0.9.79"
            or message.get("License") != "Apache License 2.0"
            or message.get("License-Expression") is not None
            or message.get_all("License-File")):
        raise ValueError("bce 0.9.79 exact metadata declaration differs")


def audit(candidate: Path, parent: Path, ancestor: Path, wheel: Path,
          sdist: Path, official_apache_text: Path) -> dict:
    identity = verify(candidate, parent, ancestor)
    if (digest(wheel) != WHEEL_SHA256 or digest(sdist) != SDIST_SHA256
            or digest(official_apache_text) != APACHE_TEXT_SHA256):
        raise ValueError("bce release or official Apache text identity differs")
    with zipfile.ZipFile(wheel) as source_wheel:
        wheel_names = source_wheel.namelist()
        wheel_metadata = next((name for name in wheel_names
                               if name.endswith("bce_python_sdk-0.9.79.dist-info/METADATA")), None)
        if wheel_metadata is None or any(NOTICE_NAME.search(name) for name in wheel_names):
            raise ValueError("bce wheel notice boundary differs")
        check_metadata(source_wheel.read(wheel_metadata))
    with tarfile.open(sdist, "r:gz") as source_sdist:
        source_names = source_sdist.getnames()
        if len(source_names) != 285 or any(NOTICE_NAME.search(name) for name in source_names):
            raise ValueError("bce sdist notice boundary differs")
    with zipfile.ZipFile(candidate) as archive:
        names = set(archive.namelist())
        if METADATA not in names or CANDIDATE_LICENSE not in names:
            raise ValueError("bce or Apache candidate evidence missing")
        check_metadata(archive.read(METADATA))
        license_body = archive.read(CANDIDATE_LICENSE)
        inventory = json.loads(archive.read("third-party-inventory.json"))
        distributions = inventory["base"]["unified"]["distributions"]
        matching = [row for row in distributions if row.get("name") == "bce-python-sdk"]
        if (len(matching) != 1 or matching[0].get("version") != "0.9.79"
                or matching[0].get("review_status") != "REVIEW_REQUIRED"
                or matching[0].get("notice_files")
                or any("bce_python_sdk-0.9.79" in name.casefold()
                       for name in names if name.startswith("payload/third-party-licenses/notices/"))):
            raise ValueError("candidate bce review boundary differs")
    if (hashlib.sha256(license_body).hexdigest() != APACHE_TEXT_SHA256
            or license_body != official_apache_text.read_bytes()):
        raise ValueError("candidate shared Apache text differs from official text")
    return {"status": "BCE_DECLARED_APACHE_TEXT_REUSE_REVIEW_CANDIDATE",
            "release_eligible": False, "legal_clearance": False,
            "candidate_sha256": identity["archive_sha256"],
            "wheel_sha256": WHEEL_SHA256, "sdist_sha256": SDIST_SHA256,
            "declared_license": "Apache License 2.0",
            "official_apache_text_sha256": APACHE_TEXT_SHA256,
            "existing_candidate_apache_text_path": CANDIDATE_LICENSE,
            "official_text_matches_existing_candidate": True,
            "bce_distribution_specific_notice_present": False,
            "source_release_contains_standalone_license": False,
            "formal_notice_approved": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "wheel", "sdist", "official-apache-text"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.ancestor, args.wheel,
                           args.sdist, args.official_apache_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
