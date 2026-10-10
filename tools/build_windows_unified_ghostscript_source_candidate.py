"""Build a new NON-RELEASE P33-derived ZIP with official Ghostscript source.

Preserves P33 exactly; never installs, provisions secrets, or grants legal clearance.
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

from audit_ghostscript_source_input import SOURCE_SHA256, audit as audit_source, digest
from package_windows_embedded_candidate import _verify_archive
from package_windows_unified_candidate import _copy_stream, safe_name, zip_members
from verify_windows_unified_caddy_go_source_candidate import ARCHIVE_SHA256, verify


KIND = "WINDOWS11_UNIFIED_PG18_CADDY_GO_GHOSTSCRIPT_SOURCE_DEVELOPMENT_CANDIDATE"
SOURCE_MEMBER = "payload/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz"
LICENSE_MEMBER = "payload/third-party-licenses/ghostscript/source-LICENSE"
LICENSE_SOURCE_MEMBER = "ghostscript-10.08.0/LICENSE"
LICENSE_SHA256 = "8ce064f423b7c24a011b6ebf9431b8bf9861a5255e47c84bfb23fc526d030a8b"
META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}


def updated_metadata(manifest: dict, inventory: dict, count: int) -> tuple[bytes, bytes]:
    if (manifest.get("payload_file_count") != 21112
            or manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False
            or inventory.get("review_status") != "REVIEW_REQUIRED"
            or "ghostscript_source" in inventory):
        raise ValueError("P33 non-release metadata boundary changed")
    next_manifest = {**manifest, "kind": KIND, "source_p33_sha256": ARCHIVE_SHA256,
                     "payload_file_count": count, "ghostscript_source_included": True,
                     "ghostscript_source_sha256": SOURCE_SHA256,
                     "release_eligible": False, "legal_clearance": False,
                     "installation_performed": False, "service_registration_performed": False}
    next_inventory = {**inventory, "review_status": "REVIEW_REQUIRED",
                      "ghostscript_source": {
                          "version": "10.08.0", "source_path": SOURCE_MEMBER,
                          "source_sha256": SOURCE_SHA256,
                          "license_path": LICENSE_MEMBER,
                          "license_sha256": LICENSE_SHA256,
                          "review_status": "REVIEW_REQUIRED", "legal_clearance": False,
                          "reproducible_windows_binary_build_verified": False}}
    return tuple((json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
                 for item in (next_manifest, next_inventory))


def build(parent: Path, ancestor: Path, source: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    identity = verify(parent, ancestor)
    audited = audit_source(parent, ancestor, source)
    if (identity["payload_file_count"] != 21112
            or audited["source_sha256"] != SOURCE_SHA256
            or audited["source_in_fixed_candidate"] is not False):
        raise ValueError("pinned Ghostscript source inputs rejected")
    with tarfile.open(source, "r:xz") as source_archive:
        license_file = source_archive.extractfile(LICENSE_SOURCE_MEMBER)
        if license_file is None:
            raise ValueError("Ghostscript source LICENSE unreadable")
        license_bytes = license_file.read()
    if hashlib.sha256(license_bytes).hexdigest() != LICENSE_SHA256:
        raise ValueError("Ghostscript source LICENSE differs")
    with zipfile.ZipFile(parent) as old:
        members = zip_members(old)
        manifest = json.loads(old.read("manifest.json"))
        inventory = json.loads(old.read("third-party-inventory.json"))
        hashes: dict[str, str] = {}
        folded: set[str] = set()
        for line in old.read("payload-sha256sums.txt").decode("ascii").splitlines():
            value, separator, name = line.partition("  ")
            safe_name(name)
            if separator != "  " or name.casefold() in folded:
                raise ValueError("P33 payload hash manifest rejected")
            hashes[name] = value
            folded.add(name.casefold())
        if (len(hashes) != 21112 or set(members) != set(hashes) | META
                or {SOURCE_MEMBER.casefold(), LICENSE_MEMBER.casefold()} & folded):
            raise ValueError("P33 payload set or new source collision")
        run = output_parent / ("unified-ghostscript-source-candidate-" + uuid.uuid4().hex[:12])
        run.mkdir(mode=0o700, exist_ok=False)
        output = run / "NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-ghostscript-source.zip"
        expected = dict(hashes)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as target:
            for name in sorted(hashes):
                with old.open(name) as inp, target.open(name, "w", force_zip64=True) as out:
                    if _copy_stream(inp, out) != hashes[name]:
                        raise ValueError("P33 payload changed during copy")
            with source.open("rb") as inp, target.open(SOURCE_MEMBER, "w", force_zip64=True) as out:
                if _copy_stream(inp, out) != SOURCE_SHA256:
                    raise ValueError("Ghostscript source changed during copy")
            target.writestr(LICENSE_MEMBER, license_bytes)
            expected[SOURCE_MEMBER] = SOURCE_SHA256
            expected[LICENSE_MEMBER] = LICENSE_SHA256
            sums = "".join(f"{value}  {name}\n" for name, value in sorted(expected.items())).encode("ascii")
            manifest_bytes, inventory_bytes = updated_metadata(manifest, inventory, len(expected))
            target.writestr("payload-sha256sums.txt", sums)
            target.writestr("manifest.json", manifest_bytes)
            target.writestr("third-party-inventory.json", inventory_bytes)
        expected.update({"payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                         "manifest.json": hashlib.sha256(manifest_bytes).hexdigest(),
                         "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest()})
    if digest(parent) != ARCHIVE_SHA256 or digest(source) != SOURCE_SHA256:
        raise ValueError("pinned inputs changed after assembly")
    _verify_archive(output, expected)
    result = {"status": "NON_RELEASE_GHOSTSCRIPT_SOURCE_CANDIDATE_INTEGRITY_PASS",
              "release_eligible": False, "legal_clearance": False,
              "archive": str(output), "archive_sha256": digest(output),
              "archive_bytes": output.stat().st_size,
              "payload_file_count": len(expected) - len(META),
              "source_p33_sha256": ARCHIVE_SHA256,
              "ghostscript_source_included": True,
              "installation_performed": False, "service_registration_performed": False}
    (run / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--ancestor", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.parent, args.ancestor, args.source, args.output_parent),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
