"""Build an embedded Windows backend runtime from same-run wheel artifacts.

All downloads, installs, probes, and archives are intended for hosted CI runners.
The resulting artifact is a NON-RELEASE candidate, not an installer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


PYTHON_SOURCE_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
BASE_NAME = "NOT-FOR-RELEASE-windows-python-3.13.15-embed-base.zip"
BLOCKED = {".env", ".log", ".key", ".pfx", ".p12", ".pyc", ".pem"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in parts)):
        raise ValueError(f"unsafe archive path: {name!r}")
    return name


def unzip_verified_runtime(archive_path: Path, target: Path) -> dict:
    with zipfile.ZipFile(archive_path) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("duplicate runtime archive path")
        manifest = json.loads(bundle.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS_PYTHON_EMBED_BASE_NON_RELEASE_REBUILT"
                or manifest.get("release_eligible") is not False
                or manifest.get("official_archive_sha256") != PYTHON_SOURCE_SHA256):
            raise ValueError("embedded base manifest identity mismatch")
        checksums = {}
        for line in bundle.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest_value, name = line.split("  ", 1)
            safe_name(name)
            checksums[name] = digest_value
        if checksums != manifest.get("payload_hashes"):
            raise ValueError("embedded base hash listing differs from manifest")
        if set(names) != set(checksums) | {
                "manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}:
            raise ValueError("embedded base file inventory mismatch")
        for name, expected in checksums.items():
            safe_name(name)
            info = bundle.getinfo(name)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("runtime symlink rejected")
            path = target.joinpath(*PurePosixPath(name.removeprefix("payload/runtime/")).parts)
            if not name.startswith("payload/runtime/"):
                raise ValueError("unexpected runtime payload path")
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as src, path.open("xb") as dst:
                actual = hashlib.sha256()
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(chunk)
                    actual.update(chunk)
            if actual.hexdigest() != expected:
                raise ValueError(f"runtime base payload hash mismatch: {name}")
    return manifest


def wheel_metadata(wheel_path: Path) -> tuple[str, str, str]:
    with zipfile.ZipFile(wheel_path) as wheel:
        infos = wheel.infolist()
        metas = [info for info in infos if info.filename.endswith(".dist-info/METADATA")]
        if len(metas) != 1:
            raise ValueError("backend wheel must contain exactly one METADATA")
        metadata = Parser().parsestr(wheel.read(metas[0]).decode("utf-8"))
        if metadata.get("Name", "").lower().replace("_", "-") != "plm-project-tool-backend":
            raise ValueError("unexpected backend wheel project")
        if metadata.get("Version") != "0.1.0.dev0":
            raise ValueError("backend wheel version mismatch")
        return metadata["Name"], metadata["Version"], digest(wheel_path)


def distribution_inventory(packages: Path) -> dict:
    entries = []
    for dist in sorted(packages.glob("*.dist-info")):
        metadata_path = dist / "METADATA"
        if dist.is_symlink() or metadata_path.is_symlink() or not metadata_path.is_file():
            raise ValueError("distribution metadata missing or linked")
        metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8", errors="replace"))
        name, version = (metadata.get("Name") or "").strip(), (metadata.get("Version") or "").strip()
        if not name or not version:
            raise ValueError("distribution name/version missing")
        notices = sorted(
            path.relative_to(packages).as_posix()
            for path in dist.rglob("*")
            if path.is_file()
            and ("licenses" in path.parts or path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")))
        )
        entries.append({
            "name": name, "version": version,
            "license_expression": (metadata.get("License-Expression") or "")[:200],
            "license_classifiers": [
                v for v in metadata.get_all("Classifier", []) if v.startswith("License ::")
            ][:12],
            "notice_files": notices, "review_status": "REVIEW_REQUIRED",
        })
    normalized = [item["name"].casefold().replace("_", "-") for item in entries]
    if not entries or len(normalized) != len(set(normalized)):
        raise ValueError("empty or duplicate Python distribution inventory")
    return {
        "schema_version": "plm.third-party-inventory.v1",
        "status": "REVIEW_REQUIRED",
        "python_runtime_license": "payload/runtime/LICENSE.txt",
        "distribution_count": len(entries),
        "distributions": entries,
    }


def build(work_root: Path, output_root: Path, backend_artifact: Path, runtime_artifact: Path,
          source_commit: str) -> dict:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("invalid source commit")
    if work_root.exists():
        raise ValueError("work root must be a fresh runner-owned directory")
    if not backend_artifact.is_dir() or not runtime_artifact.is_dir():
        raise ValueError("same-run backend/runtime artifacts are required")
    output_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True)
    if shutil.disk_usage(work_root.anchor).free < 5 * 1024**3:
        raise ValueError("less than 5 GiB free on hosted runner")

    wheels = list(backend_artifact.glob("*.whl"))
    bases = list(runtime_artifact.glob(BASE_NAME))
    summaries = list(runtime_artifact.glob("python-embed-summary.json"))
    if len(wheels) != 1 or len(bases) != 1 or len(summaries) != 1:
        raise ValueError("expected exactly one same-run backend wheel and Python base")
    backend_wheel = wheels[0]
    name, version, backend_sha = wheel_metadata(backend_wheel)
    runtime = work_root / "runtime"
    base_manifest = unzip_verified_runtime(bases[0], runtime)
    python = runtime / "python.exe"
    packages = runtime / "packages"
    packages.mkdir(exist_ok=True)
    if not python.is_file() or not packages.is_dir():
        raise ValueError("embedded runtime base is incomplete")

    wheelhouse = work_root / "wheelhouse"
    wheelhouse.mkdir()
    # Resolve the exact direct versions recorded in the same-commit backend wheel.
    # The produced per-file SHA manifest freezes all transitive selections for this artifact.
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--only-binary=:all:",
         "--dest", str(wheelhouse), str(backend_wheel)],
        check=True, timeout=1200,
    )
    wheel_files = sorted(wheelhouse.glob("*.whl"))
    if not wheel_files or any(path.suffix != ".whl" for path in wheelhouse.iterdir()):
        raise ValueError("wheelhouse is empty or contains a non-wheel artifact")
    wheel_hashes = {path.name: digest(path) for path in wheel_files}
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
         "--no-warn-script-location", "--target", str(packages),
         *[str(path) for path in wheel_files]],
        check=True, timeout=1200,
    )
    inventory = distribution_inventory(packages)
    if inventory["distribution_count"] != 106:
        raise ValueError(f"distribution count differs from package contract: {inventory['distribution_count']}")

    system_root = os.environ.get("SystemRoot", r"C:\\Windows")
    env = {"SystemRoot": system_root, "WINDIR": system_root,
           "PATH": str(runtime) + os.pathsep + str(Path(system_root) / "System32")}
    probe = (
        "import sys,ssl,sqlite3,ctypes,plm_assistant,fastapi,sqlalchemy,alembic,"
        "psycopg,pgvector,paddle,paddleocr,paddlex,numpy,fitz,openpyxl,docx,pptx;"
        "from plm_assistant.entrypoints import service_windows;"
        "assert sys.version_info[:3] == (3,13,15); print(plm_assistant.__version__)"
    )
    check = subprocess.run([str(python), "-I", "-c", probe], capture_output=True,
                           text=True, env=env, timeout=240, check=False)
    if check.returncode or "0.1.0.dev0" not in check.stdout:
        raise ValueError("embedded backend clean-path import failed: " + check.stderr[-4000:])

    file_hashes: dict[str, str] = {}
    runtime_root = runtime.resolve()
    for path in sorted(runtime.rglob("*")):
        if path.is_dir():
            continue
        rel_parts = path.relative_to(runtime).parts
        if rel_parts[:2] == ("packages", "bin") or "__pycache__" in rel_parts:
            continue
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(runtime_root)):
            raise ValueError("runtime candidate contains linked/out-of-root file")
        if path.suffix.lower() in BLOCKED or path.name.lower().startswith(".env"):
            raise ValueError("runtime candidate contains blocked/private-looking file")
        name_in_zip = safe_name("payload/runtime/" + path.relative_to(runtime).as_posix())
        file_hashes[name_in_zip] = digest(path)
    if len(file_hashes) < 18000:
        raise ValueError("runtime package is unexpectedly incomplete")

    output_dir = output_root / ("embedded-backend-" + uuid.uuid4().hex[:12])
    output_dir.mkdir()
    archive = output_dir / "NOT-FOR-RELEASE-windows-embedded-backend.zip"
    checksum_bytes = "".join(
        f"{value}  {path}\n" for path, value in sorted(file_hashes.items())
    ).encode("ascii")
    inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    manifest = {
        "kind": "WINDOWS_EMBEDDED_BACKEND_NON_RELEASE_CANDIDATE",
        "schema_version": "plm.windows-embedded-backend.v1",
        "release_eligible": False, "legal_clearance": False,
        "source_commit": source_commit,
        "backend_wheel": {"name": backend_wheel.name, "version": version, "sha256": backend_sha},
        "python_base_archive_sha256": digest(bases[0]),
        "python_official_archive_sha256": PYTHON_SOURCE_SHA256,
        "resolved_wheel_count": len(wheel_files),
        "wheel_hashes": wheel_hashes,
        "distribution_count": inventory["distribution_count"],
        "embedded_import_probe": "PASS",
        "payload_file_count": len(file_hashes),
        "known_gaps": ["third-party legal review remains open",
                       "no PostgreSQL/OCR native runtime/models are integrated",
                       "not an installer and not a complete Pilot package"],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    expected = {**file_hashes,
                "payload-sha256sums.txt": hashlib.sha256(checksum_bytes).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as bundle:
        for name_in_zip in sorted(file_hashes):
            path = runtime.joinpath(*PurePosixPath(
                name_in_zip.removeprefix("payload/runtime/")).parts)
            bundle.write(path, name_in_zip)
        bundle.writestr("payload-sha256sums.txt", checksum_bytes)
        bundle.writestr("third-party-inventory.json", inventory_bytes)
        bundle.writestr("manifest.json", manifest_bytes)
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(expected) or len(bundle.namelist()) != len(expected):
            raise ValueError("embedded backend archive inventory mismatch")
        for name_in_zip, expected_hash in expected.items():
            h = hashlib.sha256()
            with bundle.open(name_in_zip) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected_hash:
                raise ValueError("embedded backend archive readback failed: " + name_in_zip)
    summary = {
        "status": "NON_RELEASE_EMBEDDED_BACKEND_INTEGRITY_PASS",
        "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size,
        "source_commit": source_commit, "backend_wheel_sha256": backend_sha,
        "wheel_count": len(wheel_files), "distribution_count": inventory["distribution_count"],
        "payload_file_count": len(file_hashes), "embedded_import_probe": "PASS",
        "release_eligible": False, "legal_clearance": False,
    }
    (output_dir / "verification-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output_root / "embedded-backend-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(archive, output_root / archive.name)
    (output_root / "wheelhouse-sha256sums.json").write_text(
        json.dumps(wheel_hashes, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--backend-artifact", type=Path, required=True)
    parser.add_argument("--runtime-artifact", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.work_root, args.output_root, args.backend_artifact,
                           args.runtime_artifact, args.source_commit),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
