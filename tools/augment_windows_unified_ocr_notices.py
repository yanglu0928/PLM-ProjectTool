"""Build a new NON-RELEASE unified ZIP containing 13 OCR notice sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path

from build_unified_ocr_license_sidecar import GAPS_SHA256
from package_windows_embedded_candidate import _verify_archive, digest_path
from package_windows_unified_candidate import _copy_stream, safe_name, zip_members
from plan_windows_unified_install import CANDIDATE_SHA256, inspect_candidate


SIDECAR_SHA256 = "a9a2ef6f295ac01d14561a64f6b0b5fe3f83d1535dc899b2893576ca0282e71e"
TARGET_PREFIX = "payload/third-party-licenses/ocr-python-notices/"
NEW_KIND = "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE"


def inspect_sidecar(path: Path) -> list[dict]:
    if digest_path(path) != SIDECAR_SHA256:
        raise ValueError("OCR notice sidecar identity mismatch")
    with zipfile.ZipFile(path) as bundle:
        members = zip_members(bundle)
        manifest = json.loads(bundle.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS11_OCR_PYTHON_NOTICES_NON_RELEASE"
                or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False
                or manifest.get("corresponding_source_included") is not False
                or manifest.get("candidate_sha256") != CANDIDATE_SHA256
                or manifest.get("gap_report_sha256") != GAPS_SHA256
                or manifest.get("distribution_count") != 13
                or manifest.get("notice_file_count") != 25):
            raise ValueError("OCR notice sidecar manifest rejected")
        files = manifest["files"]
        if len(files) != 25 or set(members) != {"manifest.json", *(item["path"] for item in files)}:
            raise ValueError("OCR notice sidecar file set rejected")
        result = []
        for item in files:
            source = safe_name(item["path"])
            if not source.startswith("notices/"):
                raise ValueError("OCR notice path rejected")
            target = safe_name(TARGET_PREFIX + source[len("notices/"):])
            digest = hashlib.sha256(bundle.read(source)).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("OCR notice sidecar hash mismatch")
            result.append({"source": source, "target": target, "sha256": digest})
        if len({item["target"].casefold() for item in result}) != 25:
            raise ValueError("OCR notice target collision")
        return result


def augment(source_path: Path, sidecar_path: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir():
        raise ValueError("output parent missing")
    source_report = inspect_candidate(source_path)
    notices = inspect_sidecar(sidecar_path)
    run_root = output_parent / ("unified-noticed-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    output_path = run_root / "NOT-FOR-RELEASE-windows11-unified-noticed-candidate.zip"
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(sidecar_path) as sidecar:
        source_members = zip_members(source)
        source_hashes: dict[str, str] = {}
        for line in source.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            if name in source_hashes:
                raise ValueError("duplicate source payload path")
            source_hashes[name] = digest
        if len(source_hashes) != source_report["payload_file_count"]:
            raise ValueError("source payload manifest count changed")
        hashes: dict[str, str] = {}
        used_names = {name.casefold() for name in source_hashes}
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as output:
            for name in sorted(source_hashes):
                if name not in source_members:
                    raise ValueError("source payload member missing")
                with source.open(name) as inp, output.open(name, "w", force_zip64=True) as out:
                    digest = _copy_stream(inp, out)
                if digest != source_hashes[name]:
                    raise ValueError("source payload changed while copying")
                hashes[name] = digest
            for item in notices:
                target = item["target"]
                if target.casefold() in used_names:
                    raise ValueError("OCR notice target already exists")
                with sidecar.open(item["source"]) as inp, output.open(target, "w", force_zip64=True) as out:
                    digest = _copy_stream(inp, out)
                if digest != item["sha256"]:
                    raise ValueError("OCR notice bytes changed while copying")
                hashes[target] = digest
                used_names.add(target.casefold())
            hashes_bytes = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode("ascii")
            output.writestr("payload-sha256sums.txt", hashes_bytes)
            inventory_bytes = source.read("third-party-inventory.json")
            output.writestr("third-party-inventory.json", inventory_bytes)
            manifest = json.loads(source.read("manifest.json"))
            manifest.update({
                "kind": NEW_KIND, "release_eligible": False,
                "source_candidate_sha256": CANDIDATE_SHA256,
                "ocr_python_notice_sidecar_sha256": SIDECAR_SHA256,
                "ocr_python_notice_file_count": 25,
                "corresponding_source_included": False,
                "legal_clearance": False,
                "payload_file_count": len(hashes),
            })
            manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            output.writestr("manifest.json", manifest_bytes)
    expected = {**hashes, "payload-sha256sums.txt": hashlib.sha256(hashes_bytes).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    _verify_archive(output_path, expected)
    return {"status": "WINDOWS11_UNIFIED_NOTICED_CANDIDATE_INTEGRITY_PASS",
            "release_eligible": False, "archive": str(output_path),
            "archive_sha256": digest_path(output_path), "archive_bytes": output_path.stat().st_size,
            "payload_file_count": len(hashes), "new_notice_file_count": 25}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(augment(args.source, args.sidecar, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
