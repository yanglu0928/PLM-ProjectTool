"""Build a NEW NON-RELEASE P22-derived ZIP with pinned Go source evidence.

Never overwrites P22, provisions License/TLS, installs, or registers SCM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import uuid
import zipfile
from pathlib import Path

from audit_go_stdlib_source_input import (
    GO_LICENSE_SHA256, GO_SOURCE_SHA256, audit as audit_go,
)
from package_windows_embedded_candidate import _verify_archive, digest_path
from package_windows_unified_candidate import _copy_stream, safe_name, zip_members
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify as verify_source


KIND = "WINDOWS11_UNIFIED_PG18_CADDY_GO_SOURCE_DEVELOPMENT_CANDIDATE"
GO_SOURCE_MEMBER = "payload/third-party-sources/go/go1.26.3.src.tar.gz"
GO_LICENSE_MEMBER = "payload/third-party-licenses/go/LICENSE"
META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}


def updated_metadata(manifest: dict, inventory: dict, count: int) -> tuple[bytes, bytes]:
    if (manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False
            or manifest.get("payload_file_count") != 21110
            or inventory.get("review_status") != "REVIEW_REQUIRED"):
        raise ValueError("P22 legal/package metadata rejected")
    new_manifest = {**manifest, "kind": KIND, "source_p22_sha256": ARCHIVE_SHA256,
                    "payload_file_count": count, "go_stdlib_source_included": True,
                    "go_stdlib_source_sha256": GO_SOURCE_SHA256,
                    "release_eligible": False, "legal_clearance": False,
                    "installation_performed": False, "service_registration_performed": False}
    new_inventory = {**inventory, "review_status": "REVIEW_REQUIRED",
                     "go_stdlib_source": {
                         "version": "1.26.3", "source_path": GO_SOURCE_MEMBER,
                         "source_sha256": GO_SOURCE_SHA256,
                         "license_path": GO_LICENSE_MEMBER,
                         "license_sha256": GO_LICENSE_SHA256,
                         "review_status": "REVIEW_REQUIRED",
                         "legal_clearance": False}}
    return tuple((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
                 for value in (new_manifest, new_inventory))


def build(source: Path, go_source: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    source_identity = verify_source(source)
    go_identity = audit_go(source, go_source)
    if source_identity["payload_file_count"] != 21110 or go_identity["source_sha256"] != GO_SOURCE_SHA256:
        raise ValueError("fixed source identity rejected")
    with zipfile.ZipFile(source) as old:
        members = zip_members(old)
        manifest = json.loads(old.read("manifest.json"))
        inventory = json.loads(old.read("third-party-inventory.json"))
        hashes: dict[str, str] = {}
        used: set[str] = set()
        for line in old.read("payload-sha256sums.txt").decode("ascii").splitlines():
            value, separator, name = line.partition("  ")
            safe_name(name)
            if separator != "  " or name.casefold() in used:
                raise ValueError("P22 payload hash manifest rejected")
            hashes[name] = value
            used.add(name.casefold())
        if (len(hashes) != 21110 or set(members) != set(hashes) | META
                or {GO_SOURCE_MEMBER.casefold(), GO_LICENSE_MEMBER.casefold()} & used):
            raise ValueError("P22 payload file set or new source collision")
        with tarfile.open(go_source, "r:gz") as go_archive:
            license_stream = go_archive.extractfile("go/LICENSE")
            if license_stream is None:
                raise ValueError("Go LICENSE unreadable")
            license_bytes = license_stream.read()
        if hashlib.sha256(license_bytes).hexdigest() != GO_LICENSE_SHA256:
            raise ValueError("Go LICENSE identity changed")
        run = output_parent / ("unified-caddy-go-candidate-" + uuid.uuid4().hex[:12])
        run.mkdir(mode=0o700, exist_ok=False)
        output = run / "NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-source.zip"
        expected = dict(hashes)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as target:
            for name in sorted(hashes):
                with old.open(name) as inp, target.open(name, "w", force_zip64=True) as out:
                    if _copy_stream(inp, out) != hashes[name]:
                        raise ValueError("P22 payload changed during copy")
            with go_source.open("rb") as inp, target.open(GO_SOURCE_MEMBER, "w", force_zip64=True) as out:
                if _copy_stream(inp, out) != GO_SOURCE_SHA256:
                    raise ValueError("Go source changed during copy")
            target.writestr(GO_LICENSE_MEMBER, license_bytes)
            expected[GO_SOURCE_MEMBER] = GO_SOURCE_SHA256
            expected[GO_LICENSE_MEMBER] = GO_LICENSE_SHA256
            sums = "".join(f"{value}  {name}\n" for name, value in sorted(expected.items())).encode("ascii")
            manifest_bytes, inventory_bytes = updated_metadata(manifest, inventory, len(expected))
            target.writestr("payload-sha256sums.txt", sums)
            target.writestr("manifest.json", manifest_bytes)
            target.writestr("third-party-inventory.json", inventory_bytes)
        expected.update({"payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                         "manifest.json": hashlib.sha256(manifest_bytes).hexdigest(),
                         "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest()})
    if digest_path(source) != ARCHIVE_SHA256 or digest_path(go_source) != GO_SOURCE_SHA256:
        raise ValueError("fixed inputs changed after new candidate assembly")
    _verify_archive(output, expected)
    result = {"status": "NON_RELEASE_CADDY_GO_SOURCE_CANDIDATE_INTEGRITY_PASS",
              "release_eligible": False, "legal_clearance": False,
              "archive": str(output), "archive_sha256": digest_path(output),
              "archive_bytes": output.stat().st_size,
              "payload_file_count": len(expected) - len(META),
              "source_p22_sha256": ARCHIVE_SHA256,
              "go_source_included": True, "formal_tls_material_included": False,
              "installation_performed": False, "service_registration_performed": False}
    (run / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--go-source", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.go_source, args.output_parent),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
