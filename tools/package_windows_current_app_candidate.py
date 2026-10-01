"""Derive a hash-checked NON-RELEASE Windows candidate with current app bytes.

The immutable parent supplies third-party/runtime/OCR payloads. Only the backend
wheel's package/dist-info and frontend dist are replaced. This is not an installer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

from package_windows_unified_candidate import safe_name, zip_members, digest_path


PARENT_SHA256 = "30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98"
VERSION = "0.1.0.dev0"
APP_PREFIX = "payload/runtime/packages/plm_assistant/"
DIST_PREFIX = f"payload/runtime/packages/plm_project_tool_backend-{VERSION}.dist-info/"
FRONTEND_PREFIX = "payload/frontend/dist/"
SIDE_CARS = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _hash_stream(source, target=None) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(block)
        if target is not None:
            target.write(block)
    return digest.hexdigest()


def _checksums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("non-ASCII parent checksums") from error
    result: dict[str, str] = {}
    for line in lines:
        if "  " not in line:
            raise ValueError("malformed parent checksum line")
        digest, name = line.split("  ", 1)
        name = safe_name(name)
        if not SHA.fullmatch(digest) or not name.startswith("payload/") or name in result:
            raise ValueError("invalid parent checksum entry")
        result[name] = digest
    if not result:
        raise ValueError("empty parent checksums")
    return result


def _frontend_sources(root: Path) -> dict[str, Path]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("frontend dist directory required")
    resolved = root.resolve()
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("frontend symlink rejected")
        if path.is_dir():
            continue
        if not path.is_file() or not path.resolve().is_relative_to(resolved):
            raise ValueError("frontend file rejected")
        name = FRONTEND_PREFIX + safe_name(path.relative_to(root).as_posix())
        if path.suffix.lower() in {".key", ".pfx", ".p12", ".log", ".env"}:
            raise ValueError("private frontend file rejected")
        result[name] = path
    names = set(result)
    js = [name for name in names if re.fullmatch(r"payload/frontend/dist/assets/index-[\w-]+\.js", name)]
    css = [name for name in names if re.fullmatch(r"payload/frontend/dist/assets/index-[\w-]+\.css", name)]
    if names != {FRONTEND_PREFIX + "index.html", *js, *css} or len(js) != 1 or len(css) != 1:
        raise ValueError("unexpected frontend dist layout")
    html = result[FRONTEND_PREFIX + "index.html"].read_text(encoding="utf-8")
    if "/assets/" + js[0].split("/")[-1] not in html \
            or "/assets/" + css[0].split("/")[-1] not in html:
        raise ValueError("frontend assets not referenced by index")
    return result


def _wheel_members(wheel: zipfile.ZipFile) -> dict[str, str]:
    names = zip_members(wheel)
    result: dict[str, str] = {}
    for name in names:
        if not name.startswith(("plm_assistant/", f"plm_project_tool_backend-{VERSION}.dist-info/")):
            raise ValueError("wheel contains unexpected path")
        if "__pycache__" in name.split("/") or name.lower().endswith((".key", ".env", ".log")):
            raise ValueError("wheel contains private/generated file")
        target = "payload/runtime/packages/" + name
        result[target] = name
    required = {
        APP_PREFIX + "__init__.py",
        APP_PREFIX + "modules/evidence/api/lookup_eligibility_operation.py",
        APP_PREFIX + "migrations/versions/20261001_0052_evidence_parse_provenance.py",
        DIST_PREFIX + "METADATA", DIST_PREFIX + "WHEEL", DIST_PREFIX + "RECORD",
    }
    if not required <= set(result):
        raise ValueError("wheel lacks current application or migration")
    metadata = wheel.read(result[DIST_PREFIX + "METADATA"]).decode("utf-8")
    if f"Version: {VERSION}\n" not in metadata.replace("\r\n", "\n"):
        raise ValueError("wheel version mismatch")
    return result


def build_candidate(parent_path: Path, wheel_path: Path, frontend_dist: Path,
                    output_parent: Path, source_commit: str,
                    *, expected_parent_sha256: str = PARENT_SHA256) -> dict[str, object]:
    if not COMMIT.fullmatch(source_commit) or not SHA.fullmatch(expected_parent_sha256):
        raise ValueError("source commit or parent digest malformed")
    if not output_parent.is_dir() or output_parent.is_symlink():
        raise ValueError("output parent must be an existing real directory")
    if digest_path(parent_path) != expected_parent_sha256:
        raise ValueError("parent candidate SHA-256 mismatch")
    wheel_sha = digest_path(wheel_path)
    frontend = _frontend_sources(frontend_dist)
    with zipfile.ZipFile(parent_path) as parent, zipfile.ZipFile(wheel_path) as wheel:
        old_entries = zip_members(parent)
        if set(old_entries) - {name for name in old_entries if name.startswith("payload/")} != SIDE_CARS:
            raise ValueError("unexpected parent sidecars")
        parent_hashes = _checksums(parent.read("payload-sha256sums.txt"))
        if set(parent_hashes) != set(old_entries) - SIDE_CARS:
            raise ValueError("parent checksums do not match payload")
        old_manifest = json.loads(parent.read("manifest.json"))
        if (old_manifest.get("version") != VERSION
                or old_manifest.get("release_eligible") is not False
                or old_manifest.get("legal_clearance") is not False
                or old_manifest.get("formal_tls_material_included") is not False
                or old_manifest.get("payload_file_count") != len(parent_hashes)):
            raise ValueError("parent is not the expected non-release candidate")
        replacement = _wheel_members(wheel)
        if set(replacement) & set(frontend):
            raise ValueError("replacement collision")
        retained = {name for name in parent_hashes if not name.startswith(
            (APP_PREFIX, DIST_PREFIX, FRONTEND_PREFIX))}
        all_names = retained | set(replacement) | set(frontend)
        if len(all_names) != len(retained) + len(replacement) + len(frontend) \
                or len({name.casefold() for name in all_names}) != len(all_names):
            raise ValueError("output path collision")
        output_dir = output_parent / ("current-app-candidate-" + uuid.uuid4().hex[:12])
        output_dir.mkdir()
        archive_path = output_dir / "NOT-FOR-RELEASE-windows11-current-app.zip"
        new_hashes: dict[str, str] = {}
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as output:
            for name in sorted(retained):
                with parent.open(name) as source, output.open(name, "w", force_zip64=True) as target:
                    actual = _hash_stream(source, target)
                if actual != parent_hashes[name]:
                    raise ValueError("parent payload hash mismatch: " + name)
                new_hashes[name] = actual
            for target_name, source_name in sorted(replacement.items()):
                with wheel.open(source_name) as source, output.open(target_name, "w", force_zip64=True) as target:
                    new_hashes[target_name] = _hash_stream(source, target)
            for name, path in sorted(frontend.items()):
                with path.open("rb") as source, output.open(name, "w", force_zip64=True) as target:
                    new_hashes[name] = _hash_stream(source, target)
            output.writestr("payload-sha256sums.txt", "".join(
                f"{digest}  {name}\n" for name, digest in sorted(new_hashes.items())).encode("ascii"))
            output.writestr("third-party-inventory.json", parent.read("third-party-inventory.json"))
            manifest = {
                **old_manifest,
                "kind": "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE",
                "candidate_id": output_dir.name,
                "parent_candidate_sha256": expected_parent_sha256,
                "source_git_commit": source_commit,
                "backend_wheel_sha256": wheel_sha,
                "frontend_sha256": {name: new_hashes[name] for name in sorted(frontend)},
                "payload_file_count": len(new_hashes),
                "release_eligible": False, "legal_clearance": False,
                "formal_tls_material_included": False,
            }
            output.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False,
                                                        sort_keys=True, indent=2) + "\n")
        with zipfile.ZipFile(archive_path) as output:
            members = zip_members(output)
            if set(members) != set(new_hashes) | SIDE_CARS:
                raise ValueError("output inventory mismatch")
            for name, expected in new_hashes.items():
                with output.open(name) as source:
                    if _hash_stream(source) != expected:
                        raise ValueError("output payload hash mismatch: " + name)
            if output.read("third-party-inventory.json") != parent.read("third-party-inventory.json"):
                raise ValueError("third-party inventory changed")
        result: dict[str, object] = {
            "status": "WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS",
            "archive": str(archive_path), "archive_sha256": digest_path(archive_path),
            "archive_bytes": archive_path.stat().st_size,
            "parent_candidate_sha256": expected_parent_sha256,
            "source_git_commit": source_commit,
            "backend_wheel_sha256": wheel_sha,
            "payload_file_count": len(new_hashes),
            "retained_file_count": len(retained),
            "release_eligible": False, "legal_clearance": False,
        }
        (output_dir / "verification-summary.json").write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--frontend-dist", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    if head != args.source_commit or dirty:
        raise ValueError("source commit must be clean HEAD")
    result = build_candidate(args.parent, args.wheel, args.frontend_dist,
                             args.output_parent, args.source_commit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
