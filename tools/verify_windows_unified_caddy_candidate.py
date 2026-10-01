"""Independent read-only verifier for the fixed P22 NON-RELEASE Windows ZIP."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import ASSETS, EXE_SHA256, LICENSE_SHA256
from build_windows_unified_caddy_candidate import KIND, TEMPLATE_NAME, TEMPLATE_SHA256
from plan_windows_unified_pg18_composition import inspect
from plan_windows_unified_pg18_install import CANDIDATE_SHA256 as SOURCE_SHA256


ARCHIVE_SHA256 = "2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5"
ARCHIVE_BYTES = 639617127
EXPECTED_ADDITIONS = {
    "payload/web/caddy.exe": EXE_SHA256,
    "payload/third-party-licenses/caddy/LICENSE": LICENSE_SHA256,
    "payload/third-party-licenses/caddy/windows_amd64.sbom": ASSETS["windows_amd64.sbom"][1],
    "payload/third-party-licenses/caddy/checksums.txt": ASSETS["checksums.txt"][1],
    "payload/third-party-sources/caddy/buildable-artifact.tar.gz": ASSETS["buildable-artifact.tar.gz"][1],
    TEMPLATE_NAME: TEMPLATE_SHA256,
}


def verify(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("P22 archive size mismatch")
    manifest, hashes = inspect(path, ARCHIVE_SHA256, KIND, 21110)
    if (manifest.get("source_p15_sha256") != SOURCE_SHA256
            or manifest.get("caddy_exe_sha256") != EXE_SHA256
            or manifest.get("caddy_version") != "2.11.4"
            or manifest.get("legal_clearance") is not False
            or manifest.get("formal_tls_material_included") is not False
            or manifest.get("installation_performed") is not False
            or manifest.get("service_registration_performed") is not False):
        raise ValueError("P22 release boundary/lineage rejected")
    if any(hashes.get(name.casefold()) != value for name, value in EXPECTED_ADDITIONS.items()):
        raise ValueError("P22 Caddy payload identity mismatch")
    additions = {name for name in hashes if name.startswith(("payload/web/caddy", "payload/third-party-licenses/caddy/",
                                                                "payload/third-party-sources/caddy/")) or name == TEMPLATE_NAME.casefold()}
    if len(additions) != 7 or any(name.endswith((".key", ".pem", ".p12", ".pfx")) for name in additions):
        raise ValueError("P22 Caddy payload set or private material rejected")
    with zipfile.ZipFile(path) as archive:
        inventory = json.loads(archive.read("third-party-inventory.json"))
        if (inventory.get("review_status") != "REVIEW_REQUIRED"
                or inventory.get("caddy", {}).get("downstream_notice_review_complete") is not False
                or inventory.get("caddy", {}).get("source_archive_sha256") != ASSETS["buildable-artifact.tar.gz"][1]):
            raise ValueError("P22 third-party review status rejected")
    return {"status": "NON_RELEASE_UNIFIED_CADDY_INDEPENDENT_VERIFY_PASS",
            "release_eligible": False, "archive_sha256": ARCHIVE_SHA256,
            "archive_bytes": ARCHIVE_BYTES, "payload_file_count": 21110,
            "caddy_addition_count": 7, "formal_tls_material_included": False,
            "third_party_review_complete": False, "installation_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
