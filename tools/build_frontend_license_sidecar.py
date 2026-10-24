"""Preserve exact mapped/direct frontend package licenses outside Git."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import quote

from audit_frontend_bundle_licenses import audit_frontend, sha256


def build_sidecar(frontend_run: Path, output: Path) -> dict:
    evidence = audit_frontend(frontend_run)
    if evidence["release_eligible"] is not False or evidence["status"] != "REVIEW_REQUIRED":
        raise ValueError("frontend review gate rejected")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("refuse to overwrite or create output directory")
    app = frontend_run.resolve(strict=True) / "offline-source" / "apps" / "frontend"
    packages = {}
    for item in [*evidence["packages"], *evidence["direct_dependencies"]]:
        key = (item["name"], item["version"])
        previous = packages.setdefault(key, item)
        if previous["license_files"] != item["license_files"]:
            raise ValueError("conflicting package license evidence")
    if not packages:
        raise ValueError("frontend package inventory empty")
    members = []
    for (name, version), item in sorted(packages.items()):
        if not re.fullmatch(r"[A-Za-z0-9@._/-]+", name) or not re.fullmatch(r"[A-Za-z0-9._-]+", version):
            raise ValueError("unsafe package identity")
        package_root = (app / item["local_package_path"]).resolve(strict=True)
        if not package_root.is_relative_to((app / "node_modules").resolve(strict=True)):
            raise ValueError("package path rejected")
        if not item["license_files"]:
            raise ValueError("frontend package license file missing")
        for license_file in item["license_files"]:
            basename = license_file["name"]
            if not re.fullmatch(r"(?:LICENSE|LICENCE|COPYING|NOTICE)(?:[.-][A-Za-z0-9._-]+)?", basename, re.IGNORECASE):
                raise ValueError("license filename rejected")
            data = (package_root / basename).read_bytes()
            if sha256(data) != license_file["sha256"]:
                raise ValueError("frontend license hash mismatch")
            target = f"notices/{quote(name, safe='')}/{version}/{basename}"
            members.append({"path": target, "sha256": sha256(data), "package": name, "version": version, "data": data})
    if len({item["path"].casefold() for item in members}) != len(members):
        raise ValueError("duplicate frontend notice target")
    manifest = {
        "kind": "FRONTEND_LICENSE_SIDECAR_NOT_FOR_RELEASE",
        "release_eligible": False,
        "review_status": "REVIEW_REQUIRED",
        "source_commit": evidence["source_commit"],
        "lock_sha256": evidence["lock_sha256"],
        "frozen_dist_hashes": evidence["frozen_dist_hashes"],
        "package_count": len(packages),
        "license_file_count": len(members),
        "files": [{key: item[key] for key in ("path", "sha256", "package", "version")} for item in members],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in members:
            archive.writestr(item["path"], item["data"])
        archive.writestr("manifest.json", manifest_bytes)
    with zipfile.ZipFile(output) as archive:
        if set(archive.namelist()) != {"manifest.json", *(item["path"] for item in members)}:
            raise ValueError("frontend sidecar inventory mismatch")
        if archive.read("manifest.json") != manifest_bytes:
            raise ValueError("frontend sidecar manifest mismatch")
        for item in members:
            if sha256(archive.read(item["path"])) != item["sha256"]:
                raise ValueError("frontend sidecar notice mismatch")
    return {
        "status": "FRONTEND_LICENSE_SIDECAR_INTEGRITY_PASS",
        "release_eligible": False,
        "sidecar_sha256": sha256(output.read_bytes()),
        "package_count": len(packages),
        "license_file_count": len(members),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-release frontend license sidecar")
    parser.add_argument("--frontend-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_sidecar(args.frontend_run, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
