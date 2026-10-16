"""Assemble a non-release Windows candidate from already verified local inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
import zipfile
from email.parser import Parser
from pathlib import Path


EXPECTED_PYTHON_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
REQUIRED_RUNTIME_FILES = {"python.exe", "python313.dll", "python313.zip", "python313._pth", "LICENSE.txt"}
BLOCKED_SUFFIXES = {".env", ".log", ".pfx", ".p12", ".key"}


def digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve()) and path.resolve() != root.resolve()


def _source_files(runtime: Path, frontend: Path, config: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in runtime.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(runtime)
        if "__pycache__" in relative.parts or relative.parts[:2] == ("packages", "bin"):
            continue
        if path.is_symlink() or not path.is_file() or not _inside(path, runtime):
            raise ValueError("runtime source entry rejected")
        if path.suffix.lower() in BLOCKED_SUFFIXES or path.name.lower().startswith(".env"):
            raise ValueError("runtime source private file rejected")
        files.append((path, "payload/runtime/" + relative.as_posix()))
    for path in frontend.rglob("*"):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file() or not _inside(path, frontend):
            raise ValueError("frontend source entry rejected")
        files.append((path, "payload/frontend/dist/" + path.relative_to(frontend).as_posix()))
    if config.is_symlink() or not config.is_file():
        raise ValueError("bootstrap config rejected")
    files.append((config, "payload/config/bootstrap.example.yaml"))
    names = [name for _, name in files]
    if len(names) != len(set(name.casefold() for name in names)):
        raise ValueError("duplicate payload path")
    return sorted(files, key=lambda item: item[1])


def _license_inventory(packages: Path) -> dict:
    entries = []
    for dist in sorted(packages.glob("*.dist-info")):
        metadata_path = dist / "METADATA"
        if not metadata_path.is_file() or metadata_path.is_symlink():
            raise ValueError("distribution metadata missing")
        metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8", errors="replace"))
        name = metadata.get("Name", "").strip()
        version = metadata.get("Version", "").strip()
        if not name or not version:
            raise ValueError("distribution identity missing")
        notices = sorted(
            path.relative_to(packages).as_posix()
            for path in dist.rglob("*")
            if path.is_file()
            and ("licenses" in path.parts or path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")))
        )
        expression = metadata.get("License-Expression", "").strip()
        classifiers = [
            value for value in metadata.get_all("Classifier", [])
            if value.startswith("License ::")
        ]
        entries.append({
            "name": name,
            "version": version,
            "license_expression": expression[:200],
            "license_classifiers": classifiers[:12],
            "notice_file_count": len(notices),
            "notice_files": notices,
            "review_status": "REVIEW_REQUIRED",
        })
    names = [entry["name"].casefold().replace("_", "-") for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("duplicate distribution identity")
    return {
        "schema_version": "plm.third-party-inventory.v1",
        "status": "REVIEW_REQUIRED",
        "python_notice": "payload/runtime/LICENSE.txt",
        "frontend_bundled_dependency_review": "REVIEW_REQUIRED",
        "distribution_count": len(entries),
        "distributions": entries,
    }


def _verify_archive(archive: Path, expected: dict[str, str]) -> None:
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(name.casefold() for name in names)) or set(names) != set(expected):
            raise ValueError("candidate ZIP inventory mismatch")
        for name, expected_hash in expected.items():
            actual = hashlib.sha256()
            with bundle.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    actual.update(block)
            if actual.hexdigest() != expected_hash:
                raise ValueError("candidate ZIP payload hash mismatch")


def build_candidate(runtime: Path, frontend_run: Path, output_parent: Path, config: Path, backend_summary: Path) -> dict:
    runtime = runtime.resolve(strict=True)
    frontend_run = frontend_run.resolve(strict=True)
    output_parent = output_parent.resolve(strict=True)
    frontend = frontend_run / "offline-source" / "apps" / "frontend" / "dist"
    if not runtime.is_dir() or not (runtime / "packages").is_dir():
        raise ValueError("embedded runtime source missing")
    if not REQUIRED_RUNTIME_FILES.issubset({path.name for path in runtime.iterdir() if path.is_file()}):
        raise ValueError("embedded runtime mandatory files missing")
    if not runtime.parent.name.startswith("embedded-backend-") or not frontend_run.name.startswith("frontend-"):
        raise ValueError("unverified package-prep source")
    if not _inside(runtime, output_parent) or not _inside(frontend_run, output_parent):
        raise ValueError("source outside package-prep root")
    source_summary = json.loads((frontend_run / "summary.json").read_text(encoding="utf-8"))
    if source_summary.get("status") != "WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS" or source_summary.get("dist_file_count") != 3:
        raise ValueError("frontend source summary rejected")
    backend = json.loads(backend_summary.read_text(encoding="utf-8"))
    if backend.get("status") != "WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS" or backend.get("wheel_count") != 93:
        raise ValueError("backend source summary rejected")
    packages = runtime / "packages"
    inventory = _license_inventory(packages)
    if inventory["distribution_count"] != 93:
        raise ValueError("vendored distribution count mismatch")
    expected_dist = {}
    for line in (frontend_run / "dist-sha256sums.txt").read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        if not match or ".." in match.group(2).split("/"):
            raise ValueError("frontend hash manifest rejected")
        expected_dist[match.group(2)] = match.group(1)
    if len(expected_dist) != 3 or any(digest_path(frontend / name) != value for name, value in expected_dist.items()):
        raise ValueError("frontend source hash mismatch")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(runtime) + os.pathsep + str(Path(os.environ["WINDIR"]) / "System32") + os.pathsep + os.environ["WINDIR"]
    check = subprocess.run(
        [str(runtime / "python.exe"), "-I", "-c", "import plm_assistant,fastapi,psycopg,paddle,paddleocr,paddlex; import plm_assistant.entrypoints.service_windows; print(plm_assistant.__version__)"],
        capture_output=True, text=True, env=env, timeout=120, check=False,
    )
    if check.returncode or "0.1.0.dev0" not in check.stdout.splitlines():
        raise ValueError("embedded runtime clean-path import failed")
    files = _source_files(runtime, frontend, config)
    if len([name for _, name in files if name.startswith("payload/frontend/dist/")]) != 3:
        raise ValueError("frontend payload count mismatch")
    run_root = output_parent / ("embedded-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    archive = run_root / "NOT-FOR-RELEASE-windows11-embedded-candidate.zip"
    payload_hashes: dict[str, str] = {}
    inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as bundle:
        for source, name in files:
            payload_hashes[name] = digest_path(source)
            bundle.write(source, name)
        hashes_bytes = "".join(f"{value}  {name}\n" for name, value in sorted(payload_hashes.items())).encode("ascii")
        bundle.writestr("payload-sha256sums.txt", hashes_bytes)
        bundle.writestr("third-party-inventory.json", inventory_bytes)
        manifest = {
            "kind": "WINDOWS11_EMBEDDED_DEVELOPMENT_CANDIDATE",
            "release_eligible": False,
            "runtime_python": "3.13.15 AMD64 official embed",
            "official_runtime_sha256": EXPECTED_PYTHON_SHA256,
            "backend_wheel": backend["backend_wheel"],
            "frontend_source_commit": source_summary["source_commit"],
            "mixed_source_checkpoints": True,
            "payload_file_count": len(files),
            "vendored_distribution_count": inventory["distribution_count"],
            "third_party_license_status": "REVIEW_REQUIRED",
            "missing_release_components": [
                "PostgreSQL 18 and pgvector", "OCR system components and approved models",
                "Formal License public key and customer license", "HTTPS and service account provisioning",
                "Plugin and installer/upgrade tools", "Physical air-gap and Server2025/Debian13 acceptance",
                "Gate3-Gate7 and UAT evidence", "Third-party license and SBOM review",
            ],
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("manifest.json", manifest_bytes)
    expected = {**payload_hashes, "payload-sha256sums.txt": hashlib.sha256(hashes_bytes).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    _verify_archive(archive, expected)
    result = {
        "status": "WINDOWS11_EMBEDDED_CANDIDATE_INTEGRITY_PASS",
        "release_eligible": False,
        "archive_sha256": digest_path(archive),
        "archive_bytes": archive.stat().st_size,
        "payload_file_count": len(files),
        "vendored_distribution_count": inventory["distribution_count"],
        "third_party_license_status": "REVIEW_REQUIRED",
        "archive": str(archive),
    }
    (run_root / "verification-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a Windows11 embedded NON-RELEASE candidate")
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--frontend-run", required=True, type=Path)
    parser.add_argument("--backend-summary", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.runtime, args.frontend_run, args.output_parent, args.config, args.backend_summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
