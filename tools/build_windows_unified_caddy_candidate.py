"""Build a NEW non-release Windows unified+PG18+Caddy archive from pinned inputs.

Never overwrites P15, installs, registers services, or includes TLS private keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import (
    ASSETS, EXE_SHA256, LICENSE_SHA256, PREFIX, VERSION, audit as audit_caddy,
    digest,
)
from build_windows_unified_pg18_candidate import KIND as SOURCE_KIND
from package_windows_embedded_candidate import _verify_archive
from package_windows_unified_candidate import _copy_stream, safe_name, zip_members
from plan_windows_unified_pg18_composition import inspect
from plan_windows_unified_pg18_install import CANDIDATE_SHA256


KIND = "WINDOWS11_UNIFIED_PG18_CADDY_DEVELOPMENT_CANDIDATE"
EXTRA_COUNT = 7
TEMPLATE_NAME = "payload/config/Caddyfile.template"
TEMPLATE_SHA256 = "b1a6e6032ee95d401c24b8565d6f719ec6f8f84445fb5d43ef409fd52462b117"


def _extra_inputs(caddy_root: Path, template: Path) -> dict[str, Path | tuple[zipfile.ZipFile, str]]:
    expected_template = Path(__file__).resolve().parents[1] / "deploy/windows/Caddyfile.template"
    if (not template.is_file() or template.resolve() != expected_template.resolve()
            or digest(template) != TEMPLATE_SHA256):
        raise ValueError("Caddyfile template input missing")
    body = template.read_text(encoding="ascii")
    placeholders = {"__PUBLIC_HOST__", "__TLS_CERT_PATH__", "__TLS_KEY_PATH__",
                    "__API_PORT__", "__FRONTEND_ROOT__"}
    if any(body.count(token) < 1 for token in placeholders) or "respond \"Misdirected Request\" 421" not in body:
        raise ValueError("Caddyfile template contract changed")
    source = caddy_root / (PREFIX + "windows_amd64.zip")
    archive = zipfile.ZipFile(source)
    if set(zip_members(archive)) != {"caddy.exe", "LICENSE", "README.md"}:
        archive.close()
        raise ValueError("pinned Caddy ZIP member set changed")
    return {
        "payload/web/caddy.exe": (archive, "caddy.exe"),
        "payload/web/caddy-README.md": (archive, "README.md"),
        "payload/third-party-licenses/caddy/LICENSE": (archive, "LICENSE"),
        "payload/third-party-licenses/caddy/windows_amd64.sbom": caddy_root / (PREFIX + "windows_amd64.sbom"),
        "payload/third-party-licenses/caddy/checksums.txt": caddy_root / (PREFIX + "checksums.txt"),
        "payload/third-party-sources/caddy/buildable-artifact.tar.gz": caddy_root / (PREFIX + "buildable-artifact.tar.gz"),
        TEMPLATE_NAME: template,
    }


def build(source: Path, caddy_root: Path, template: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    caddy_evidence = audit_caddy(caddy_root)
    old_manifest, old_hashes = inspect(source, CANDIDATE_SHA256, SOURCE_KIND, 21103)
    if old_manifest.get("release_eligible") is not False:
        raise ValueError("source release state changed")
    extras = _extra_inputs(caddy_root, template)
    if len(extras) != EXTRA_COUNT or any(safe_name(name) != name for name in extras):
        raise ValueError("Caddy payload entry set invalid")
    if set(name.casefold() for name in extras) & set(name.casefold() for name in old_hashes):
        raise ValueError("Caddy payload collides with source")
    run = output_parent / ("unified-caddy-candidate-" + uuid.uuid4().hex[:12])
    run.mkdir()
    output = run / "NOT-FOR-RELEASE-windows11-unified-pg18-caddy.zip"
    hashes: dict[str, str] = {}
    caddy_archive = extras["payload/web/caddy.exe"][0]
    try:
        with zipfile.ZipFile(source) as old, zipfile.ZipFile(
                output, "w", compression=zipfile.ZIP_DEFLATED,
                compresslevel=1, allowZip64=True) as target:
            members = zip_members(old)
            source_hashes: dict[str, str] = {}
            source_seen: set[str] = set()
            for line in old.read("payload-sha256sums.txt").decode("ascii").splitlines():
                value, separator, name = line.partition("  ")
                if separator != "  " or name.casefold() in source_seen:
                    raise ValueError("P15 hash manifest line rejected")
                source_hashes[name] = value
                source_seen.add(name.casefold())
            if ({name.casefold(): value for name, value in source_hashes.items()} != old_hashes
                    or set(members) != set(source_hashes) | {
                        "manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}):
                raise ValueError("P15 file set differs from manifest")
            for name in sorted(source_hashes):
                with old.open(name) as inp, target.open(name, "w", force_zip64=True) as out:
                    actual = _copy_stream(inp, out)
                if actual != source_hashes[name]:
                    raise ValueError(f"P15 payload changed during copy: {name}")
                hashes[name] = actual
            for name, item in sorted(extras.items()):
                if isinstance(item, tuple):
                    with item[0].open(item[1]) as inp, target.open(name, "w", force_zip64=True) as out:
                        actual = _copy_stream(inp, out)
                else:
                    with item.open("rb") as inp, target.open(name, "w", force_zip64=True) as out:
                        actual = _copy_stream(inp, out)
                hashes[name] = actual
            if hashes["payload/web/caddy.exe"] != EXE_SHA256 or hashes["payload/third-party-licenses/caddy/LICENSE"] != LICENSE_SHA256:
                raise ValueError("Caddy executable/license changed during copy")
            for name, suffix in (
                ("payload/third-party-licenses/caddy/windows_amd64.sbom", "windows_amd64.sbom"),
                ("payload/third-party-licenses/caddy/checksums.txt", "checksums.txt"),
                ("payload/third-party-sources/caddy/buildable-artifact.tar.gz", "buildable-artifact.tar.gz"),
            ):
                if hashes[name] != ASSETS[suffix][1]:
                    raise ValueError(f"Caddy official sidecar changed: {name}")
            sums = "".join(f"{value}  {name}\n" for name, value in sorted(hashes.items())).encode("ascii")
            inventory = {
                "schema_version": "plm.windows-unified-caddy-inventory.v1",
                "review_status": "REVIEW_REQUIRED", "base": json.loads(old.read("third-party-inventory.json")),
                "caddy": {"version": VERSION, "license": "Apache-2.0",
                          "windows_amd64_exe_sha256": EXE_SHA256,
                          "bundled_license_sha256": LICENSE_SHA256,
                          "source_archive_sha256": ASSETS["buildable-artifact.tar.gz"][1],
                          "sbom_component_count": caddy_evidence["sbom_component_count"],
                          "downstream_notice_review_complete": False},
            }
            inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            manifest = {
                "kind": KIND, "version": "0.1.0.dev0", "release_eligible": False,
                "installation_performed": False, "service_registration_performed": False,
                "source_p15_sha256": CANDIDATE_SHA256, "caddy_version": VERSION,
                "caddy_exe_sha256": EXE_SHA256, "payload_file_count": len(hashes),
                "legal_clearance": False, "product_sse_verified": False,
                "formal_tls_material_included": False,
                "known_gaps": ["formal License/public key/signing provenance",
                               "complete third-party NOTICE/corresponding-source/legal review",
                               "installer/service account ACL/certificate supply and recovery",
                               "Windows Server 2025 and Debian 13 release acceptance",
                               "business UAT, AI quality and Gate 3-7 evidence"],
            }
            manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            target.writestr("payload-sha256sums.txt", sums)
            target.writestr("third-party-inventory.json", inventory_bytes)
            target.writestr("manifest.json", manifest_bytes)
    finally:
        caddy_archive.close()
    if digest(source) != CANDIDATE_SHA256 or audit_caddy(caddy_root) != caddy_evidence:
        raise ValueError("pinned source changed after assembly")
    expected = {**hashes, "payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    _verify_archive(output, expected)
    result = {"status": "NON_RELEASE_UNIFIED_CADDY_INTEGRITY_PASS", "release_eligible": False,
              "archive": str(output), "archive_sha256": digest(output),
              "archive_bytes": output.stat().st_size, "payload_file_count": len(hashes),
              "caddy_version": VERSION, "caddy_source_included": True,
              "formal_tls_material_included": False}
    (run / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--caddy-inputs", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.caddy_inputs, args.template,
                           args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
