"""Reconcile four fixed non-vendor Caddy SBOM entries against bundled bytes.

Evidence classification only; no legal interpretation or release clearance.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import ASSETS, EXE_SHA256, LICENSE_SHA256
from build_caddy_sbom_review_queue import SBOM, rows_from_sbom
from map_caddy_vendor_license_sources import QUEUE_SHA256, SOURCE, SPECIAL_NAMES
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify


EVIDENCE_SHA256 = "1a771e5056c96c1d66b979765fefdbb6c5d55c6cf82fb210dc2daec0e78e7abb"
LICENSE_PATH = "payload/third-party-licenses/caddy/LICENSE"
EXE_PATH = "payload/web/caddy.exe"


def special_evidence(candidate: Path, queue: Path, vendor_evidence: Path) -> dict:
    identity = verify(candidate)
    for path, expected in ((queue, QUEUE_SHA256), (vendor_evidence, EVIDENCE_SHA256)):
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("fixed previous evidence identity differs")
    with zipfile.ZipFile(candidate) as archive:
        sbom_raw = archive.read(SBOM)
        source_raw = archive.read(SOURCE)
        bundled_license = archive.read(LICENSE_PATH)
        bundled_exe = archive.read(EXE_PATH)
    if (hashlib.sha256(sbom_raw).hexdigest() != ASSETS["windows_amd64.sbom"][1]
            or hashlib.sha256(source_raw).hexdigest() != ASSETS["buildable-artifact.tar.gz"][1]
            or hashlib.sha256(bundled_license).hexdigest() != LICENSE_SHA256
            or hashlib.sha256(bundled_exe).hexdigest() != EXE_SHA256):
        raise ValueError("fixed Caddy evidence bytes differ")
    sbom = json.loads(sbom_raw)
    rows_from_sbom(sbom)  # Validate full fixed SBOM structure before classifying.
    specials = {entry["name"]: entry for entry in sbom["components"]
                if entry["name"] in SPECIAL_NAMES}
    if set(specials) != SPECIAL_NAMES:
        raise ValueError("special SBOM component set differs")
    with tarfile.open(fileobj=io.BytesIO(source_raw), mode="r:gz") as source:
        root_license = source.extractfile("LICENSE")
        root_mod = source.extractfile("go.mod")
        if root_license is None or root_mod is None:
            raise ValueError("root source evidence missing")
        license_bytes = root_license.read()
        go_mod_bytes = root_mod.read()
    go_mod = go_mod_bytes.decode("utf-8")
    if license_bytes != bundled_license:
        raise ValueError("root source and bundled Caddy LICENSE differ")
    if (not re.search(r"^module caddy$", go_mod, flags=re.M)
            or not re.search(r"^go 1\.26\.3$", go_mod, flags=re.M)
            or not re.search(r"^require github\.com/caddyserver/caddy/v2 v2\.11\.4$", go_mod, flags=re.M)):
        raise ValueError("root Go module/toolchain/Caddy requirement differs")
    app = specials["Caddy"]
    main = specials["caddy"]
    stdlib = specials["stdlib"]
    binary = specials[next(name for name in SPECIAL_NAMES if name.startswith("/home/runner/"))]
    if (app.get("version") != "2.11.4" or app.get("type") != "application"
            or main.get("purl") != "pkg:golang/caddy@v0.0.0-20260601193502-e2eee6a7fce3"
            or stdlib.get("version") != "go1.26.3"
            or stdlib.get("purl") != "pkg:golang/stdlib@1.26.3"
            or stdlib.get("licenses") != [{"license": {"id": "BSD-3-Clause"}}]
            or binary.get("type") != "file"
            or {entry.get("alg"): entry.get("content") for entry in binary.get("hashes", [])}.get("SHA-256") != EXE_SHA256):
        raise ValueError("special SBOM metadata differs")
    return {"status": "NON_RELEASE_CADDY_SPECIAL_SOURCE_EVIDENCE",
            "release_eligible": False, "legal_clearance": False,
            "candidate_sha256": ARCHIVE_SHA256,
            "payload_file_count": identity["payload_file_count"],
            "special_component_count": 4,
            "root_license_matches_bundled": True,
            "root_license_sha256": LICENSE_SHA256,
            "go_mod_sha256": hashlib.sha256(go_mod_bytes).hexdigest(),
            "root_module_name_matches_main_sbom_name": True,
            "main_pseudo_version_proven_by_root_source": False,
            "caddy_required_version_matches_application_sbom": True,
            "toolchain_go_version_matches_stdlib_sbom": True,
            "stdlib_license_only_declared_in_sbom": "BSD-3-Clause",
            "stdlib_source_in_candidate": False,
            "sbom_binary_sha256_matches_packaged_exe": True,
            "exe_sha256": EXE_SHA256,
            "remaining_review": [
                "main pseudo-version/provenance outside root go.mod",
                "Go 1.26.3 standard-library source and license text not in candidate",
                "applicable notices and legal assessment for all four entries",
            ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--vendor-evidence", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(special_evidence(args.candidate, args.queue, args.vendor_evidence),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
