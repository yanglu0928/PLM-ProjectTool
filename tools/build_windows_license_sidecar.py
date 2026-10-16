"""Preserve exact wheel notice bytes in a NON-RELEASE supplemental archive."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from audit_windows_candidate_licenses import audit, digest_bytes, digest_file


def build_sidecar(candidate: Path, wheelhouse: Path, hash_manifest: Path, output: Path) -> dict:
    evidence = audit(candidate, wheelhouse, hash_manifest)
    if evidence["release_eligible"] is not False or evidence["status"] != "REVIEW_REQUIRED":
        raise ValueError("source evidence release gate rejected")
    if output.exists():
        raise ValueError("refuse to overwrite existing sidecar")
    if not output.parent.is_dir():
        raise ValueError("output parent missing")
    members: list[tuple[str, bytes, str]] = []
    for package in evidence["packages"]:
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", package["wheel"]):
            raise ValueError("unsafe wheel filename")
        with zipfile.ZipFile(wheelhouse / package["wheel"]) as wheel:
            for notice in package["notice_files"]:
                source = notice["path"]
                if source.startswith("/") or "\\" in source or ".." in source.split("/"):
                    raise ValueError("unsafe notice path")
                data = wheel.read(source)
                if digest_bytes(data) != notice["sha256"]:
                    raise ValueError("notice digest mismatch")
                target = "notices/" + package["wheel"] + "/" + source
                members.append((target, data, package["wheel_sha256"]))
    if len({name.casefold() for name, _, _ in members}) != len(members):
        raise ValueError("duplicate notice target")
    manifest = {
        "kind": "WINDOWS11_WHEEL_LICENSE_SIDECAR_NOT_FOR_RELEASE",
        "release_eligible": False,
        "candidate_sha256": evidence["candidate_sha256"],
        "wheel_count": evidence["wheel_count"],
        "notice_file_count": len(members),
        "no_notice_packages": evidence["no_notice_packages"],
        "review_status": "REVIEW_REQUIRED",
        "limits": evidence["scope_limits"],
        "files": [
            {"path": name, "sha256": digest_bytes(data), "source_wheel_sha256": wheel_sha}
            for name, data, wheel_sha in members
        ],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data, _ in members:
            archive.writestr(name, data)
        archive.writestr("manifest.json", manifest_bytes)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != len(set(name.casefold() for name in names)) or set(names) != {"manifest.json", *(name for name, _, _ in members)}:
            raise ValueError("sidecar inventory mismatch")
        if archive.read("manifest.json") != manifest_bytes:
            raise ValueError("sidecar manifest mismatch")
        for name, data, _ in members:
            if digest_bytes(archive.read(name)) != digest_bytes(data):
                raise ValueError("sidecar notice mismatch")
    return {
        "status": "WHEEL_NOTICE_SIDECAR_INTEGRITY_PASS",
        "release_eligible": False,
        "sidecar_sha256": digest_file(output),
        "notice_file_count": len(members),
        "wheel_count": evidence["wheel_count"],
        "no_notice_packages": evidence["no_notice_packages"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a non-release wheel notice sidecar")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--wheelhouse", required=True, type=Path)
    parser.add_argument("--hash-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_sidecar(args.candidate, args.wheelhouse, args.hash_manifest, args.output)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
