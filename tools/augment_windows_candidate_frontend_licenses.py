"""Add exact frontend notices to a new NON-RELEASE Windows candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
import zipfile
from pathlib import Path

from audit_windows_candidate_licenses import digest_file
from verify_windows11_embedded_candidate import inspect_archive


def inspect_frontend_sidecar(sidecar: Path, candidate: Path) -> tuple[dict, list[dict]]:
    with zipfile.ZipFile(sidecar) as notices, zipfile.ZipFile(candidate) as bundle:
        manifest = json.loads(notices.read("manifest.json"))
        if (manifest.get("kind") != "FRONTEND_LICENSE_SIDECAR_NOT_FOR_RELEASE"
                or manifest.get("release_eligible") is not False
                or manifest.get("review_status") != "REVIEW_REQUIRED"
                or manifest.get("package_count") != 6
                or manifest.get("license_file_count") != 6):
            raise ValueError("frontend sidecar release gate rejected")
        for name, expected in manifest.get("frozen_dist_hashes", {}).items():
            if not name or name.startswith("/") or "\\" in name or ".." in name.split("/"):
                raise ValueError("frontend dist path rejected")
            target = "payload/frontend/dist/" + name
            if hashlib.sha256(bundle.read(target)).hexdigest() != expected:
                raise ValueError("frontend candidate dist mismatch")
        if len(manifest.get("frozen_dist_hashes", {})) != 3:
            raise ValueError("frontend dist count rejected")
        files = manifest.get("files", [])
        paths = [item["path"] for item in files]
        if len(files) != 6 or len({path.casefold() for path in paths}) != 6 or set(notices.namelist()) != {"manifest.json", *paths}:
            raise ValueError("frontend sidecar inventory rejected")
        for item in files:
            path = item["path"]
            if (not path.startswith("notices/") or "\\" in path or ":" in path
                    or any(part in ("", ".", "..") for part in path.split("/"))):
                raise ValueError("frontend sidecar path rejected")
            if hashlib.sha256(notices.read(path)).hexdigest() != item["sha256"]:
                raise ValueError("frontend notice hash mismatch")
    return manifest, files


def augment_candidate(source: Path, sidecar: Path, output_parent: Path) -> dict:
    source = source.resolve(strict=True)
    sidecar = sidecar.resolve(strict=True)
    output_parent = output_parent.resolve(strict=True)
    if source.name != "NOT-FOR-RELEASE-windows11-embedded-candidate.zip" or not output_parent.is_dir():
        raise ValueError("candidate source rejected")
    source_manifest, _, source_hashes = inspect_archive(source)
    if source_manifest.get("wheel_license_notice_file_count") != 152:
        raise ValueError("wheel notice predecessor missing")
    frontend_manifest, files = inspect_frontend_sidecar(sidecar, source)
    run_root = output_parent / ("embedded-full-notice-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    output = run_root / source.name
    target_hashes = dict(source_hashes)
    manifest = dict(source_manifest)
    manifest.update({
        "release_eligible": False,
        "third_party_license_status": "REVIEW_REQUIRED",
        "source_candidate_sha256": digest_file(source),
        "frontend_license_sidecar_sha256": digest_file(sidecar),
        "frontend_license_notice_file_count": len(files),
        "frontend_license_source_commit": frontend_manifest["source_commit"],
        "license_payload_is_legal_clearance": False,
        "payload_file_count": len(source_hashes) + len(files),
    })
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(sidecar) as notices, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
    ) as new:
        for name in sorted(source_hashes):
            with old.open(name) as input_stream, new.open(name, "w", force_zip64=True) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
        for item in files:
            target = "payload/third-party-licenses/frontend/" + item["path"]
            if target in target_hashes:
                raise ValueError("duplicate frontend notice payload")
            with notices.open(item["path"]) as input_stream, new.open(target, "w", force_zip64=True) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
            target_hashes[target] = item["sha256"]
        new.writestr("payload-sha256sums.txt", "".join(
            f"{sha}  {name}\n" for name, sha in sorted(target_hashes.items())
        ).encode("ascii"))
        new.writestr("third-party-inventory.json", old.read("third-party-inventory.json"))
        new.writestr("manifest.json", (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    actual_manifest, _, actual_hashes = inspect_archive(output)
    if actual_manifest != manifest or actual_hashes != target_hashes:
        raise ValueError("frontend-augmented candidate mismatch")
    return {
        "status": "WINDOWS11_FRONTEND_NOTICE_CANDIDATE_INTEGRITY_PASS",
        "release_eligible": False,
        "archive": str(output),
        "archive_sha256": digest_file(output),
        "payload_file_count": len(target_hashes),
        "frontend_license_notice_file_count": len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Augment Windows candidate with frontend notices (non-release)")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(augment_candidate(args.candidate, args.sidecar, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
