"""Verify and reinstall a NON-RELEASE Windows embedded candidate in isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
import zipfile
from pathlib import Path


def inspect_archive(archive: Path) -> tuple[dict, dict, dict[str, str]]:
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("candidate ZIP duplicate entry")
        total = 0
        for info in infos:
            name = info.filename
            parts = name.split("/")
            if not name or "\\" in name or name.startswith("/") or ":" in name or any(ord(char) < 32 for char in name) or any(part in ("", ".", "..") for part in parts):
                raise ValueError("candidate ZIP path rejected")
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("candidate ZIP symlink rejected")
            if name not in ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json") and not name.startswith("payload/"):
                raise ValueError("candidate ZIP unexpected entry")
            total += info.file_size
            if total > 2 * 1024**3:
                raise ValueError("candidate ZIP expanded size rejected")
        manifest = json.loads(bundle.read("manifest.json"))
        inventory = json.loads(bundle.read("third-party-inventory.json"))
        if (manifest.get("kind") != "WINDOWS11_EMBEDDED_DEVELOPMENT_CANDIDATE" or
            manifest.get("release_eligible") is not False or
            manifest.get("third_party_license_status") != "REVIEW_REQUIRED" or
            manifest.get("vendored_distribution_count") != 93 or
            inventory.get("status") != "REVIEW_REQUIRED" or
            inventory.get("distribution_count") != 93):
            raise ValueError("candidate release or license gate rejected")
        lines = bundle.read("payload-sha256sums.txt").decode("ascii").splitlines()
        hashes: dict[str, str] = {}
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{64})  (payload/.+)", line)
            if not match or match.group(2) not in names or match.group(2) in hashes:
                raise ValueError("candidate hash manifest rejected")
            hashes[match.group(2)] = match.group(1)
        if len(hashes) != manifest.get("payload_file_count") or set(hashes) != (set(names) - {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}):
            raise ValueError("candidate payload count mismatch")
        required = {
            "payload/runtime/python.exe", "payload/runtime/python313.dll", "payload/runtime/LICENSE.txt",
            "payload/runtime/python313._pth", "payload/frontend/dist/index.html",
            "payload/config/bootstrap.example.yaml",
        }
        if not required.issubset(hashes):
            raise ValueError("candidate mandatory payload missing")
        for name, expected in hashes.items():
            digest = hashlib.sha256()
            with bundle.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError("candidate payload hash mismatch")
        return manifest, inventory, hashes


def verify_candidate(archive: Path, output_parent: Path) -> dict:
    archive = archive.resolve(strict=True)
    output_parent = output_parent.resolve(strict=True)
    if archive.name != "NOT-FOR-RELEASE-windows11-embedded-candidate.zip" or not archive.is_relative_to(output_parent):
        raise ValueError("only a local embedded candidate is accepted")
    manifest, inventory, hashes = inspect_archive(archive)
    run_root = output_parent / ("embedded-reinstall-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(run_root)
    runtime = run_root / "payload" / "runtime"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(runtime) + os.pathsep + str(Path(os.environ["WINDIR"]) / "System32") + os.pathsep + os.environ["WINDIR"]
    probe = subprocess.run(
        [str(runtime / "python.exe"), "-I", "-c",
         'import importlib.util,json,sys; import fastapi,sqlalchemy,psycopg,paddle,paddleocr,paddlex,plm_assistant; import plm_assistant.entrypoints.service_windows; print("PLM_PROBE:"+json.dumps({"version":plm_assistant.__version__,"paths":sys.path,"pip":importlib.util.find_spec("pip") is not None}))'],
        capture_output=True, text=True, env=env, timeout=120, check=False,
    )
    if probe.returncode:
        raise ValueError("extracted candidate backend import failed")
    markers = [line.removeprefix("PLM_PROBE:") for line in probe.stdout.splitlines() if line.startswith("PLM_PROBE:")]
    if len(markers) != 1:
        raise ValueError("extracted candidate probe marker missing")
    result = json.loads(markers[0])
    if result.get("version") != "0.1.0.dev0" or result.get("pip") is not False or not all(
        Path(path).resolve().is_relative_to(runtime.resolve()) for path in result.get("paths", [])
    ):
        raise ValueError("extracted candidate private interpreter check failed")
    dist_count = len(list((runtime / "packages").glob("*.dist-info")))
    if dist_count != 93:
        raise ValueError("extracted candidate distribution count mismatch")
    summary = {
        "status": "WINDOWS11_EMBEDDED_CANDIDATE_REINSTALL_PASS",
        "release_eligible": False,
        "payload_file_count": len(hashes),
        "vendored_distribution_count": dist_count,
        "third_party_license_status": inventory["status"],
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "run_root": str(run_root),
    }
    (run_root / "verification-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Windows11 NON-RELEASE embedded candidate")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_candidate(args.archive, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
