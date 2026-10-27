"""Rebuild a pinned Python 3.13.15 embeddable runtime on a hosted Windows runner.

This creates only a NON-RELEASE base runtime input. It does not install app wheels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

URL = "https://www.python.org/ftp/python/3.13.15/python-3.13.15-embed-amd64.zip"
SOURCE_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
SOURCE_NAME = "python-3.13.15-embed-amd64.zip"
REQUIRED = {"python.exe", "python313.dll", "python313.zip", "python313._pth", "LICENSE.txt"}
BLOCKED = {".env", ".log", ".key", ".pfx", ".p12"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def archive_inventory(bundle: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    found: dict[str, zipfile.ZipInfo] = {}
    folded: set[str] = set()
    for info in bundle.infolist():
        name = info.filename
        parts = PurePosixPath(name).parts
        mode = info.external_attr >> 16
        if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
                or any(part in ("", ".", "..") for part in parts)
                or stat.S_ISLNK(mode)):
            raise ValueError(f"unsafe official ZIP path: {name!r}")
        key = name.casefold()
        if key in folded:
            raise ValueError(f"duplicate case-insensitive official ZIP entry: {name}")
        folded.add(key)
        if not info.is_dir():
            if Path(name).suffix.lower() in BLOCKED or Path(name).name.lower().startswith(".env"):
                raise ValueError(f"private-looking runtime entry rejected: {name}")
            found[name] = info
    if not REQUIRED <= set(found):
        raise ValueError("official embedded distribution lacks required runtime files")
    return found


def build(work_root: Path, output_root: Path) -> dict:
    work_root = work_root.resolve()
    output_root = output_root.resolve()
    work_root.mkdir(parents=True, exist_ok=False)
    output_root.mkdir(parents=True, exist_ok=True)
    drive = Path(work_root.anchor)
    if shutil.disk_usage(drive).free < 2 * 1024**3:
        raise ValueError("insufficient hosted-runner disk space for Python runtime build")

    source = work_root / SOURCE_NAME
    request = urllib.request.Request(URL, headers={"User-Agent": "PLM-ProjectTool-cloud-builder/1"})
    with urllib.request.urlopen(request, timeout=60) as response, source.open("wb") as dst:
        while chunk := response.read(1024 * 1024):
            dst.write(chunk)
    if source.stat().st_size == 0 or digest(source) != SOURCE_SHA256:
        raise ValueError("official Python embedded archive SHA-256 mismatch")

    runtime = work_root / "runtime"
    runtime.mkdir()
    with zipfile.ZipFile(source) as bundle:
        entries = archive_inventory(bundle)
        for name, info in entries.items():
            target = runtime.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)

    pth = runtime / "python313._pth"
    lines = [line.strip() for line in pth.read_text(encoding="utf-8-sig").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if "python313.zip" not in lines or "." not in lines:
        raise ValueError("unexpected embedded Python import-path configuration")
    if "packages" not in lines:
        lines.append("packages")
    pth.write_text("\n".join(lines + ["import site", ""]), encoding="ascii")
    (runtime / "packages").mkdir()
    python = runtime / "python.exe"
    system_root = os.environ.get("SystemRoot", r"C:\\Windows")
    env = {"SystemRoot": system_root, "WINDIR": system_root,
           "PATH": str(runtime) + os.pathsep + str(Path(system_root) / "System32")}
    check = subprocess.run(
        [str(python), "-I", "-c",
         "import sys,ssl,sqlite3,ctypes,json,platform; "
         "assert sys.version_info[:3] == (3,13,15); "
         "assert platform.architecture()[0] == '64bit'; "
         "print(sys.version); print(platform.machine())"],
        capture_output=True, text=True, timeout=60, env=env, check=False)
    if check.returncode or "3.13.15" not in check.stdout or "AMD64" not in check.stdout.upper():
        raise ValueError("isolated embedded Python version/architecture/import check failed: "
                         + check.stderr[-2000:])

    file_hashes = {}
    for path in sorted(runtime.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(runtime):
            raise ValueError("runtime payload escapes verified root")
        rel = path.relative_to(runtime).as_posix()
        file_hashes["payload/runtime/" + rel] = digest(path)
    if len(file_hashes) < len(REQUIRED) + 1:
        raise ValueError("embedded Python runtime file inventory is unexpectedly small")

    run = output_root / ("python-embed-" + uuid.uuid4().hex[:12])
    run.mkdir()
    archive = run / "NOT-FOR-RELEASE-windows-python-3.13.15-embed-base.zip"
    hashes_text = "".join(f"{sha}  {name}\n" for name, sha in sorted(file_hashes.items())).encode("ascii")
    inventory = {
        "schema_version": "plm.third-party-inventory.v1",
        "status": "REVIEW_REQUIRED",
        "python_runtime": {
            "name": "Python", "version": "3.13.15", "architecture": "AMD64",
            "license_path": "payload/runtime/LICENSE.txt",
            "source_url": URL, "source_sha256": SOURCE_SHA256,
            "app_dependencies_included": False, "review_status": "REVIEW_REQUIRED",
        },
    }
    inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    manifest = {
        "kind": "WINDOWS_PYTHON_EMBED_BASE_NON_RELEASE_REBUILT",
        "schema_version": "plm.windows-python-embed.v1",
        "release_eligible": False, "legal_clearance": False,
        "python_version": "3.13.15", "architecture": "AMD64",
        "official_archive_sha256": SOURCE_SHA256, "official_archive_bytes": source.stat().st_size,
        "payload_file_count": len(file_hashes), "payload_hashes": file_hashes,
        "packages_directory_present": True, "app_dependencies_included": False,
        "isolated_standard_library_check": "PASS",
        "known_gaps": ["application wheelhouse is not included",
                       "third-party legal review remains open",
                       "no installer, service account or ACL is included",
                       "this is not an installable Pilot or release package"],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    expected = {**file_hashes,
                "payload-sha256sums.txt": hashlib.sha256(hashes_text).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as bundle:
        for name in sorted(file_hashes):
            path = runtime.joinpath(*PurePosixPath(name.removeprefix("payload/runtime/")).parts)
            bundle.write(path, name)
        bundle.writestr("payload-sha256sums.txt", hashes_text)
        bundle.writestr("third-party-inventory.json", inventory_bytes)
        bundle.writestr("manifest.json", manifest_bytes)
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != len(expected) or set(bundle.namelist()) != set(expected):
            raise ValueError("rebuilt Python archive inventory mismatch")
        for name, expected_sha in expected.items():
            h = hashlib.sha256()
            with bundle.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected_sha:
                raise ValueError("rebuilt Python archive readback mismatch: " + name)
    summary = {
        "status": "NON_RELEASE_PYTHON_EMBED_BASE_REBUILT_INTEGRITY_PASS",
        "release_eligible": False, "legal_clearance": False,
        "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size,
        "source_archive_sha256": SOURCE_SHA256, "payload_file_count": len(file_hashes),
        "runtime_probe": "Python 3.13.15 AMD64; isolated ssl/sqlite3/ctypes imports passed",
    }
    (run / "verification-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_root / "python-embed-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(archive, output_root / archive.name)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.work_root, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
