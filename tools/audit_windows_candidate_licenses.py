"""Reconcile a non-release candidate's Python inventory with exact source wheels.

This is evidence collection, not a legal clearance or release approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from email.parser import BytesParser
from pathlib import Path


HASH_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(name: str, version: str) -> tuple[str, str]:
    return re.sub(r"[-_.]+", "-", name).lower(), version


def _notice(name: str) -> bool:
    if ".dist-info/licenses/" in name.lower():
        return True
    leaf = name.rsplit("/", 1)[-1].upper()
    return bool(re.match(r"^(?:LICENSE|LICENCE|COPYING|NOTICE)(?:$|[.-])", leaf))


def _wheel_evidence(wheel: Path, expected_hash: str) -> dict:
    if digest_file(wheel) != expected_hash:
        raise ValueError(f"wheel hash mismatch: {wheel.name}")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError(f"duplicate wheel member: {wheel.name}")
        if any(name.startswith("/") or "\\" in name or ".." in name.split("/") for name in names):
            raise ValueError(f"unsafe wheel member: {wheel.name}")
        metadata_names = [name for name in names if name.count("/") == 1 and name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"wheel metadata not unique: {wheel.name}")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        package_name, version = metadata.get("Name", "").strip(), metadata.get("Version", "").strip()
        if not package_name or not version:
            raise ValueError(f"wheel identity missing: {wheel.name}")
        notices = [
            {"path": name, "sha256": digest_bytes(archive.read(name))}
            for name in sorted(names)
            if not name.endswith("/") and _notice(name)
        ]
        return {
            "name": package_name,
            "version": version,
            "wheel": wheel.name,
            "wheel_sha256": expected_hash,
            "license_expression": metadata.get("License-Expression", "").strip(),
            "legacy_license": metadata.get("License", "").strip()[:200],
            "license_classifiers": [value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")],
            "notice_files": notices,
            "review_status": "REVIEW_REQUIRED",
        }


def audit(candidate: Path, wheelhouse: Path, hash_manifest: Path) -> dict:
    with zipfile.ZipFile(candidate) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        inventory = json.loads(archive.read("third-party-inventory.json"))
    if manifest.get("release_eligible") is not False or inventory.get("status") != "REVIEW_REQUIRED":
        raise ValueError("candidate release gate rejected")
    raw_lines = hash_manifest.read_text(encoding="ascii").splitlines()
    matches = [HASH_LINE.fullmatch(line) for line in raw_lines]
    if not raw_lines or any(match is None for match in matches):
        raise ValueError("wheel hash manifest malformed")
    wheel_hashes = {match.group(2): match.group(1) for match in matches if match}
    if len(wheel_hashes) != len(raw_lines):
        raise ValueError("duplicate wheel hash entry")
    if {path.name for path in wheelhouse.glob("*.whl")} != set(wheel_hashes):
        raise ValueError("wheelhouse inventory mismatch")
    wheels = [_wheel_evidence(wheelhouse / name, sha) for name, sha in sorted(wheel_hashes.items())]
    by_identity = {identity(item["name"], item["version"]): item for item in wheels}
    if len(by_identity) != len(wheels):
        raise ValueError("duplicate wheel identity")
    candidate_ids = [identity(item["name"], item["version"]) for item in inventory["distributions"]]
    if len(set(candidate_ids)) != len(candidate_ids) or set(candidate_ids) != set(by_identity):
        raise ValueError("candidate and source wheel identities differ")
    if len(wheels) != inventory.get("distribution_count") or len(wheels) != manifest.get("vendored_distribution_count"):
        raise ValueError("distribution count mismatch")
    packages = [by_identity[key] for key in sorted(by_identity)]
    return {
        "schema_version": "plm.python-wheel-license-evidence.v1",
        "status": "REVIEW_REQUIRED",
        "release_eligible": False,
        "candidate_sha256": digest_file(candidate),
        "wheel_count": len(packages),
        "notice_file_package_count": sum(bool(item["notice_files"]) for item in packages),
        "no_notice_packages": [item["name"] for item in packages if not item["notice_files"]],
        "packages": packages,
        "scope_limits": ["Python wheels only", "No frontend, native OS components or model audit", "No legal approval"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exact Python wheel license evidence (non-release)")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--wheelhouse", required=True, type=Path)
    parser.add_argument("--hash-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.candidate, args.wheelhouse, args.hash_manifest)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "release_eligible", "wheel_count", "notice_file_package_count", "no_notice_packages")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
