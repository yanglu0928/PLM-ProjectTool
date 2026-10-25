"""Create a new non-release candidate including exact wheel license notices."""

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


def inspect_sidecar(sidecar: Path, candidate_hash: str) -> list[tuple[str, str]]:
    with zipfile.ZipFile(sidecar) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS11_WHEEL_LICENSE_SIDECAR_NOT_FOR_RELEASE"
                or manifest.get("release_eligible") is not False
                or manifest.get("review_status") != "REVIEW_REQUIRED"
                or manifest.get("candidate_sha256") != candidate_hash
                or manifest.get("wheel_count") != 93):
            raise ValueError("sidecar source or release gate rejected")
        files = manifest.get("files", [])
        paths = [item["path"] for item in files]
        if len(paths) != manifest.get("notice_file_count") or len(paths) != 152:
            raise ValueError("sidecar file count rejected")
        if len({path.casefold() for path in paths}) != len(paths) or set(archive.namelist()) != {"manifest.json", *paths}:
            raise ValueError("sidecar member inventory rejected")
        for item in files:
            path = item["path"]
            if (not path.startswith("notices/") or "\\" in path or ":" in path
                    or any(part in ("", ".", "..") for part in path.split("/"))):
                raise ValueError("sidecar path rejected")
            digest = hashlib.sha256()
            with archive.open(path) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != item["sha256"]:
                raise ValueError("sidecar notice hash mismatch")
        return [(item["path"], item["sha256"]) for item in files]


def augment_candidate(source: Path, sidecar: Path, output_parent: Path) -> dict:
    source = source.resolve(strict=True)
    sidecar = sidecar.resolve(strict=True)
    output_parent = output_parent.resolve(strict=True)
    if source.name != "NOT-FOR-RELEASE-windows11-embedded-candidate.zip" or not output_parent.is_dir():
        raise ValueError("candidate source rejected")
    source_manifest, _, source_hashes = inspect_archive(source)
    source_digest = digest_file(source)
    notice_entries = inspect_sidecar(sidecar, source_digest)
    run_root = output_parent / ("embedded-licensed-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    output = run_root / source.name
    target_hashes = dict(source_hashes)
    manifest = dict(source_manifest)
    manifest.update({
        "release_eligible": False,
        "third_party_license_status": "REVIEW_REQUIRED",
        "source_candidate_sha256": source_digest,
        "wheel_license_sidecar_sha256": digest_file(sidecar),
        "wheel_license_notice_file_count": len(notice_entries),
        "license_payload_is_legal_clearance": False,
        "payload_file_count": len(source_hashes) + len(notice_entries),
    })
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(sidecar) as notices, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
    ) as new:
        for name in sorted(source_hashes):
            with old.open(name) as input_stream, new.open(name, "w", force_zip64=True) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
        for path, expected in notice_entries:
            target = "payload/third-party-licenses/" + path
            if target in target_hashes:
                raise ValueError("duplicate notice payload")
            with notices.open(path) as input_stream, new.open(target, "w", force_zip64=True) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)
            target_hashes[target] = expected
        new.writestr("payload-sha256sums.txt", "".join(
            f"{sha}  {name}\n" for name, sha in sorted(target_hashes.items())
        ).encode("ascii"))
        new.writestr("third-party-inventory.json", old.read("third-party-inventory.json"))
        new.writestr("manifest.json", (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    verified_manifest, _, verified_hashes = inspect_archive(output)
    if verified_manifest != manifest or verified_hashes != target_hashes:
        raise ValueError("augmented candidate verification mismatch")
    return {
        "status": "WINDOWS11_LICENSE_AUGMENTED_CANDIDATE_INTEGRITY_PASS",
        "release_eligible": False,
        "archive": str(output),
        "archive_sha256": digest_file(output),
        "payload_file_count": len(target_hashes),
        "wheel_license_notice_file_count": len(notice_entries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Augment a non-release Windows candidate with wheel notices")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(augment_candidate(args.candidate, args.sidecar, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
