"""Trace candidate native files to the exact official runtime or pinned wheels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from audit_windows_candidate_licenses import digest_file
from verify_windows11_embedded_candidate import inspect_archive


PYTHON_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
NATIVE_SUFFIXES = {".exe", ".dll", ".pyd", ".so"}
HASH_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)")


def _native(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in NATIVE_SUFFIXES


def audit_native(candidate: Path, python_zip: Path, wheelhouse: Path, hash_manifest: Path) -> dict:
    manifest, _, _ = inspect_archive(candidate)
    if manifest.get("release_eligible") is not False:
        raise ValueError("candidate release gate rejected")
    if python_zip.name != "python-3.13.15-embed-amd64.zip" or digest_file(python_zip) != PYTHON_SHA256:
        raise ValueError("official Python runtime source rejected")
    lines = hash_manifest.read_text(encoding="ascii").splitlines()
    matches = [HASH_LINE.fullmatch(line) for line in lines]
    if len(lines) != 93 or any(match is None for match in matches):
        raise ValueError("wheel hash manifest rejected")
    wheel_hashes = {match.group(2): match.group(1) for match in matches if match}
    if len(wheel_hashes) != 93 or {p.name for p in wheelhouse.glob("*.whl")} != set(wheel_hashes):
        raise ValueError("wheelhouse inventory rejected")
    source_by_hash: dict[str, list[dict]] = {}
    with zipfile.ZipFile(python_zip) as archive:
        for name in archive.namelist():
            if _native(name):
                digest = hashlib.sha256(archive.read(name)).hexdigest()
                source_by_hash.setdefault(digest, []).append({
                    "kind": "OFFICIAL_PYTHON_EMBED", "source": python_zip.name,
                    "source_sha256": PYTHON_SHA256, "source_member": name,
                    "expected_candidate_path": "payload/runtime/" + name,
                })
    for wheel_name, expected in sorted(wheel_hashes.items()):
        wheel = wheelhouse / wheel_name
        if digest_file(wheel) != expected:
            raise ValueError(f"wheel source hash mismatch: {wheel_name}")
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if _native(name):
                    digest = hashlib.sha256(archive.read(name)).hexdigest()
                    installed_member = name.split(".data/platlib/", 1)[1] if ".data/platlib/" in name else name
                    source_by_hash.setdefault(digest, []).append({
                        "kind": "PINNED_WHEEL", "source": wheel_name,
                        "source_sha256": expected, "source_member": name,
                        "expected_candidate_path": "payload/runtime/packages/" + installed_member,
                    })
    entries = []
    with zipfile.ZipFile(candidate) as archive:
        for name in archive.namelist():
            if not _native(name):
                continue
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            matches = source_by_hash.get(digest, [])
            exact = [item for item in matches if item["expected_candidate_path"] == name]
            selected = exact if len(exact) == 1 else matches if len(matches) == 1 else []
            entries.append({
                "candidate_path": name,
                "sha256": digest,
                "status": "SOURCE_MATCHED" if len(selected) == 1 else "UNRESOLVED",
                "source": selected[0] if len(selected) == 1 else None,
                "possible_source_count": len(matches),
            })
    if not entries:
        raise ValueError("candidate has no native files")
    unresolved = [item["candidate_path"] for item in entries if item["status"] != "SOURCE_MATCHED"]
    kinds: dict[str, int] = {}
    for item in entries:
        if item["source"]:
            kind = item["source"]["kind"]
            kinds[kind] = kinds.get(kind, 0) + 1
    executable_names = {PurePosixPath(item["candidate_path"]).name.casefold() for item in entries}
    return {
        "schema_version": "plm.windows-native-source-evidence.v1",
        "status": "SOURCE_MATCH_PASS" if not unresolved else "SOURCE_MATCH_INCOMPLETE",
        "release_eligible": False,
        "candidate_sha256": digest_file(candidate),
        "native_file_count": len(entries),
        "source_kind_counts": kinds,
        "unresolved_count": len(unresolved),
        "unresolved_paths": unresolved,
        "external_executables_present": {
            "ghostscript": any(name.startswith("gswin") and name.endswith(".exe") for name in executable_names),
            "tesseract": "tesseract.exe" in executable_names,
        },
        "entries": entries,
        "limits": ["Exact byte provenance only", "No native transitive DLL dependency scan", "No legal or target OS clearance"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit native binary provenance in a non-release candidate")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--python-zip", required=True, type=Path)
    parser.add_argument("--wheelhouse", required=True, type=Path)
    parser.add_argument("--hash-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_native(args.candidate, args.python_zip, args.wheelhouse, args.hash_manifest)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "status", "release_eligible", "native_file_count", "source_kind_counts", "unresolved_count", "external_executables_present"
    )}, ensure_ascii=False))
    return 0 if result["unresolved_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
