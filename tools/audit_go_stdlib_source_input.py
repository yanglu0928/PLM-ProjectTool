"""Verify official Go 1.26.3 source as a possible offline Caddy evidence input.

Does not add it to a candidate or decide legal obligations.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import ASSETS
from build_caddy_sbom_review_queue import SBOM
from map_caddy_vendor_license_sources import SOURCE
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify


GO_SOURCE_SHA256 = "1c646875d0aa8799133184ed57cf79ff24bdefe8c8820470602a9d3d6d9192b8"
GO_SOURCE_BYTES = 34119059
GO_LICENSE_SHA256 = "911f8f5782931320f5b8d1160a76365b83aea6447ee6c04fa6d5591467db9dad"


def inspect_source(source: Path) -> dict:
    if not source.is_file() or source.stat().st_size != GO_SOURCE_BYTES:
        raise ValueError("official Go source input size differs")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != GO_SOURCE_SHA256:
        raise ValueError("official Go source input SHA-256 differs")
    with tarfile.open(source, "r:gz") as archive:
        names = archive.getnames()
        if len(names) != len(set(names)) or "go/LICENSE" not in names or "go/VERSION" not in names:
            raise ValueError("official Go source member set rejected")
        version = archive.extractfile("go/VERSION")
        license_file = archive.extractfile("go/LICENSE")
        if version is None or license_file is None:
            raise ValueError("official Go source metadata unreadable")
        if version.read().splitlines()[0] != b"go1.26.3":
            raise ValueError("official Go source version differs")
        license_body = license_file.read()
        if hashlib.sha256(license_body).hexdigest() != GO_LICENSE_SHA256:
            raise ValueError("official Go source LICENSE differs")
        source_members = [entry for entry in archive.getmembers()
                          if entry.isfile() and entry.name.startswith("go/src/")]
        if len(source_members) < 10000:
            raise ValueError("official Go standard library source set too small")
    return {"source_sha256": GO_SOURCE_SHA256, "source_bytes": GO_SOURCE_BYTES,
            "go_license_sha256": GO_LICENSE_SHA256,
            "go_src_regular_file_count": len(source_members)}


def audit(candidate: Path, source: Path) -> dict:
    identity = verify(candidate)
    inspected = inspect_source(source)
    with zipfile.ZipFile(candidate) as archive:
        sbom = json.loads(archive.read(SBOM))
        built_source = archive.read(SOURCE)
        has_go_source = any(name.startswith("payload/third-party-sources/go/")
                            for name in archive.namelist())
    if has_go_source or hashlib.sha256(built_source).hexdigest() != ASSETS["buildable-artifact.tar.gz"][1]:
        raise ValueError("historical Caddy candidate source boundary differs")
    components = [item for item in sbom["components"] if item.get("name") == "stdlib"]
    with tarfile.open(fileobj=io.BytesIO(built_source), mode="r:gz") as tar:
        go_mod = tar.extractfile("go.mod")
        if go_mod is None:
            raise ValueError("Caddy root go.mod missing")
        module_text = go_mod.read().decode("utf-8")
    if (len(components) != 1 or components[0].get("version") != "go1.26.3"
            or components[0].get("purl") != "pkg:golang/stdlib@1.26.3"
            or "\ngo 1.26.3\n" not in module_text):
        raise ValueError("Go source version does not match fixed Caddy toolchain evidence")
    return {"status": "NON_RELEASE_GO_STDLIB_OFFLINE_SOURCE_INPUT_VERIFIED",
            "release_eligible": False, "legal_clearance": False,
            "candidate_sha256": ARCHIVE_SHA256,
            "payload_file_count": identity["payload_file_count"],
            **inspected, "matches_caddy_go_mod_and_sbom_version": True,
            "source_in_historical_candidate": False,
            "source_bundled_for_release": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--go-source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.go_source), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
