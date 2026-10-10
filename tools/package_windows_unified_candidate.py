"""Build a hash-pinned Windows 11 NON-RELEASE candidate from local inputs.

This is an assembly/integrity tool, not an installer or a release approval.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from package_windows_embedded_candidate import _license_inventory, digest_path


BASE_SHA256 = "6b42945167c4d93330a058f0550a4f8dfd26277287c7a7cf07c536ce400fd77a"
NATIVE_SHA256 = "b1dadde7993cd7dca7d1a26d58b7322cca5e59f03bdb11a4a3712213a73ad24b"
MODELS_SHA256 = "944ec7f8f7b7815ec9c35443afe980ad5207a5ed653c55cde573fd5e20c06c69"
NO_JBIG_CSV_SHA256 = "a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc"
EXPECTED_SOURCE_COUNTS = {"frontend": 3, "ghostscript": 654, "tessdata": 41, "models": 10, "no_jbig_pe": 34}
BLOCKED_RUNTIME_SUFFIXES = {".env", ".log", ".key", ".pfx", ".p12"}


def safe_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or "//" in name or "/./" in name or name.startswith("./")
            or any(part in {"", ".", ".."} for part in parts)):
        raise ValueError(f"unsafe archive name: {name!r}")
    return name


def zip_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result: dict[str, zipfile.ZipInfo] = {}
    seen: set[str] = set()
    for info in archive.infolist():
        name = safe_name(info.filename)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("symlink ZIP entry rejected")
        key = name.casefold()
        if key in seen:
            raise ValueError("case-insensitive duplicate ZIP entry")
        seen.add(key)
        if not info.is_dir():
            result[name] = info
    return result


def select_entries(base: set[str], native: set[str], models: set[str]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    base_selected = {
        name: name for name in base
        if name.startswith(("payload/frontend/dist/", "payload/third-party-licenses/"))
        or name == "payload/config/bootstrap.example.yaml"
    }
    native_selected = {
        name: name for name in native
        if name.startswith("payload/ocr/ghostscript/")
        or name.startswith("payload/ocr/tesseract/tessdata/")
    }
    model_selected = {
        name: "payload/ocr/" + name for name in models if name.startswith("models/")
    }
    counts = {
        "frontend": sum(name.startswith("payload/frontend/dist/") for name in base_selected),
        "ghostscript": sum(name.startswith("payload/ocr/ghostscript/") for name in native_selected),
        "tessdata": sum(name.startswith("payload/ocr/tesseract/tessdata/") for name in native_selected),
        "models": len(model_selected),
    }
    if any(counts[key] != expected for key, expected in EXPECTED_SOURCE_COUNTS.items() if key in counts):
        raise ValueError(f"pinned input counts changed: {counts}")
    if any(name.startswith("payload/ocr/tesseract/") and not name.startswith("payload/ocr/tesseract/tessdata/")
           for name in native_selected):
        raise ValueError("old Tesseract selected")
    return base_selected, native_selected, model_selected


def no_jbig_sources(candidate_dir: Path, matrix_csv: Path) -> dict[str, Path]:
    if digest_path(matrix_csv) != NO_JBIG_CSV_SHA256:
        raise ValueError("no-JBIG source matrix hash mismatch")
    with matrix_csv.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != EXPECTED_SOURCE_COUNTS["no_jbig_pe"]:
        raise ValueError("no-JBIG candidate count mismatch")
    names = {row["binary"] for row in rows}
    if len(names) != len(rows) or "libjbig-0.dll" in names or not {"tesseract.exe", "libtiff-6.dll"} <= names:
        raise ValueError("no-JBIG candidate names rejected")
    actual_names = {path.name for path in candidate_dir.iterdir() if path.is_file()}
    if actual_names != names:
        raise ValueError("no-JBIG candidate directory differs from matrix")
    result = {}
    for row in rows:
        name = safe_name(row["binary"])
        if "/" in name or not name.lower().endswith((".dll", ".exe")):
            raise ValueError("invalid no-JBIG binary name")
        path = candidate_dir / name
        if path.is_symlink() or not path.is_file() or digest_path(path) != row["binary_sha256"]:
            raise ValueError(f"no-JBIG candidate hash mismatch: {name}")
        result["payload/ocr/tesseract/" + name] = path
    return result


def runtime_sources(runtime: Path) -> dict[str, Path]:
    if runtime.name != "runtime" or not runtime.parent.name.startswith("embedded-backend-"):
        raise ValueError("unverified runtime directory")
    mandatory = {"python.exe", "python313.dll", "python313.zip", "python313._pth", "LICENSE.txt"}
    if not all((runtime / name).is_file() for name in mandatory):
        raise ValueError("incomplete embedded Python runtime")
    if len(list((runtime / "packages").glob("*.dist-info"))) != 106:
        raise ValueError("expected 106 Python distributions")
    result: dict[str, Path] = {}
    for path in runtime.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(runtime)
        if "__pycache__" in relative.parts or relative.parts[:2] == ("packages", "bin"):
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(runtime.resolve()):
            raise ValueError("runtime entry rejected")
        if path.suffix.lower() in BLOCKED_RUNTIME_SUFFIXES or path.name.lower().startswith(".env"):
            raise ValueError("runtime private file rejected")
        result["payload/runtime/" + relative.as_posix()] = path
    if len(result) < 18000:
        raise ValueError("runtime unexpectedly incomplete")
    return result


def _copy_stream(source, destination) -> str:
    digest = hashlib.sha256()
    while chunk := source.read(1024 * 1024):
        destination.write(chunk)
        digest.update(chunk)
    return digest.hexdigest()


def build_candidate(base_path: Path, runtime: Path, native_path: Path, models_path: Path,
                    candidate_dir: Path, matrix_csv: Path, output_parent: Path) -> dict:
    paths = [(base_path, BASE_SHA256), (native_path, NATIVE_SHA256),
             (models_path, MODELS_SHA256)]
    for path, expected in paths:
        if digest_path(path) != expected:
            raise ValueError(f"pinned archive hash mismatch: {path.name}")
    if not output_parent.is_dir():
        raise ValueError("output parent must exist")
    inventory = _license_inventory(runtime / "packages")
    if inventory["distribution_count"] != 106:
        raise ValueError("Python license inventory incomplete")
    local = runtime_sources(runtime)
    local.update(no_jbig_sources(candidate_dir, matrix_csv))
    with (zipfile.ZipFile(base_path) as base, zipfile.ZipFile(native_path) as native,
          zipfile.ZipFile(models_path) as models):
        base_names = zip_members(base)
        native_names = zip_members(native)
        model_names = zip_members(models)
        selections = select_entries(set(base_names), set(native_names), set(model_names))
        sources = [(base, selections[0]), (native, selections[1]), (models, selections[2])]
        all_names = list(local) + [target for _, selected in sources for target in selected.values()]
        if len(all_names) != len(set(name.casefold() for name in all_names)):
            raise ValueError("output path collision")
        output_dir = output_parent / ("unified-candidate-" + uuid.uuid4().hex[:12])
        output_dir.mkdir()
        archive_path = output_dir / "NOT-FOR-RELEASE-windows11-unified-candidate.zip"
        hashes: dict[str, str] = {}
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as output:
            for name, path in sorted(local.items()):
                with path.open("rb") as inp, output.open(name, "w", force_zip64=True) as out:
                    hashes[name] = _copy_stream(inp, out)
            for source, selected in sources:
                for source_name, target in sorted(selected.items()):
                    with source.open(source_name) as inp, output.open(target, "w", force_zip64=True) as out:
                        hashes[target] = _copy_stream(inp, out)
            hashes_text = "".join(f"{value}  {name}\n" for name, value in sorted(hashes.items()))
            output.writestr("payload-sha256sums.txt", hashes_text.encode("ascii"))
            output.writestr("third-party-inventory.json", json.dumps(inventory, ensure_ascii=False,
                                                                       sort_keys=True, indent=2) + "\n")
            manifest = {
                "kind": "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE",
                "release_eligible": False,
                "version": "0.1.0.dev0",
                "source_archive_sha256": {"base": BASE_SHA256, "ocr_native": NATIVE_SHA256,
                                          "paddle_models": MODELS_SHA256, "no_jbig_matrix": NO_JBIG_CSV_SHA256},
                "vendored_python_distributions": 106,
                "no_jbig_pe_count": 34,
                "old_tesseract_included": False,
                "payload_file_count": len(hashes),
                "third_party_license_status": "REVIEW_REQUIRED",
                "known_blockers": ["NOT AN INSTALLER OR RELEASE", "third-party NOTICE/source obligations",
                                   "formal product License and signing", "PostgreSQL 18/pgvector offline install",
                                   "target account and Windows Server 2025 acceptance", "AI quality and release gates"],
            }
            output.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        with zipfile.ZipFile(archive_path) as output:
            members = zip_members(output)
            if set(members) != set(hashes) | {"payload-sha256sums.txt", "third-party-inventory.json", "manifest.json"}:
                raise ValueError("output inventory mismatch")
            for name, expected in hashes.items():
                with output.open(name) as inp:
                    digest = hashlib.sha256()
                    for block in iter(lambda: inp.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != expected:
                    raise ValueError(f"output payload hash mismatch: {name}")
        result = {"status": "WINDOWS11_UNIFIED_CANDIDATE_INTEGRITY_PASS", "release_eligible": False,
                  "archive": str(archive_path), "archive_sha256": digest_path(archive_path),
                  "archive_bytes": archive_path.stat().st_size, "payload_file_count": len(hashes),
                  "vendored_python_distributions": 106, "no_jbig_pe_count": 34}
        (output_dir / "verification-summary.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "runtime", "native", "models", "no-jbig-dir", "no-jbig-csv", "output-parent"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = build_candidate(args.base, args.runtime, args.native, args.models,
                             args.no_jbig_dir, args.no_jbig_csv, args.output_parent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
