"""Read-only audit of the pinned Caddy 2.11.4 Windows AMD64 PoC inputs.

No installation, service change, certificate creation, or release approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path


VERSION = "2.11.4"
PREFIX = f"caddy_{VERSION}_"
ASSETS = {
    "windows_amd64.zip": (17559418, "1708333f79e274c7697285afe6d592ab39314e0b131e9ec6bea08ad27df62ebf"),
    "windows_amd64.sbom": (143666, "ecc0c7270380760e6ab62521dcc6baee8a4e7324319bfdaf0874cd5ec74f7e88"),
    "buildable-artifact.tar.gz": (11306896, "33777097f666d60d78bfb74df06978c933f32aa5a0d4ce0b0c5d028489984187"),
    "checksums.txt": (6769, "7bfa272f3ece3ac987c1e06cd3c0acf126749d88110c20d7b83dcea3caaf0080"),
}
ZIP_MEMBERS = {"caddy.exe", "LICENSE", "README.md"}
EXE_SHA256 = "5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b"
LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def checksum_entries(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in content.splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 128 or not all(c in "0123456789abcdef" for c in parts[0]):
            raise ValueError("malformed published SHA-512 checksum entry")
        if parts[1] in result:
            raise ValueError("duplicate published checksum entry")
        result[parts[1]] = parts[0]
    return result


def audit(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("offline input directory missing")
    assets = []
    for suffix, (size, expected) in ASSETS.items():
        path = root / (PREFIX + suffix)
        if not path.is_file() or path.stat().st_size != size or digest(path) != expected:
            raise ValueError(f"official release asset identity mismatch: {path.name}")
        assets.append({"name": path.name, "size_bytes": size, "sha256": expected})

    published = checksum_entries((root / (PREFIX + "checksums.txt")).read_text(encoding="utf-8"))
    for suffix in ASSETS:
        if suffix == "checksums.txt":
            continue
        path = root / (PREFIX + suffix)
        if published.get(path.name) != digest(path, "sha512"):
            raise ValueError(f"published SHA-512 mismatch: {path.name}")

    with zipfile.ZipFile(root / (PREFIX + "windows_amd64.zip")) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(ZIP_MEMBERS) or set(names) != ZIP_MEMBERS:
            raise ValueError("unexpected Windows ZIP layout")
        if hashlib.sha256(archive.read("caddy.exe")).hexdigest() != EXE_SHA256:
            raise ValueError("Caddy executable identity mismatch")
        license_bytes = archive.read("LICENSE")
        if hashlib.sha256(license_bytes).hexdigest() != LICENSE_SHA256:
            raise ValueError("bundled license identity mismatch")
        if b"Apache License" not in license_bytes or b"Version 2.0" not in license_bytes:
            raise ValueError("bundled license text mismatch")

    with tarfile.open(root / (PREFIX + "buildable-artifact.tar.gz"), "r:gz") as archive:
        source_names = {item.name for item in archive.getmembers()}
        if not {"LICENSE", "go.mod", "go.sum", "main.go"}.issubset(source_names):
            raise ValueError("buildable source archive lacks expected material")
        source_license = archive.extractfile("LICENSE")
        if source_license is None or hashlib.sha256(source_license.read()).hexdigest() != LICENSE_SHA256:
            raise ValueError("buildable source license mismatch")

    sbom = json.loads((root / (PREFIX + "windows_amd64.sbom")).read_text(encoding="utf-8"))
    metadata = sbom.get("metadata", {}).get("component", {})
    if (sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6"
            or metadata.get("version") != "sha256:" + EXE_SHA256
            or not any(item.get("name") == "Caddy" and item.get("version") == VERSION
                       for item in sbom.get("components", []))):
        raise ValueError("official Windows SBOM identity mismatch")

    return {
        "schema_version": "plm.caddy-windows-offline-input.v1",
        "status": "PINNED_OFFICIAL_INPUT_PASS_NOT_RELEASE_READY",
        "release_eligible": False,
        "version": VERSION,
        "platform": "Windows AMD64",
        "official_release": f"https://github.com/caddyserver/caddy/releases/tag/v{VERSION}",
        "assets": assets,
        "exe_sha256": EXE_SHA256,
        "license_sha256": LICENSE_SHA256,
        "published_sha512_verified": True,
        "source_archive_present": True,
        "sbom_component_count": len(sbom["components"]),
        "installation_performed": False,
        "https_route_verified": False,
        "third_party_license_review_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; preserve historical audit")
    report = audit(args.input_root)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "release_eligible": False,
                      "assets": len(report["assets"]), "output_sha256": digest(args.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
