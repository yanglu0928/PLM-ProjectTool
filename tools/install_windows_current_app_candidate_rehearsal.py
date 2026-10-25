"""Atomically place a verified current-app NON-RELEASE payload under Temp.

This is file-placement rehearsal only: no SCM, service, TLS, database or
production install-root changes are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_windows_unified_candidate import safe_name, digest_path
from stage_windows_current_app_candidate import KIND
from verify_windows_unified_extract import verify as verify_stage

META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}


def checksums(raw: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        digest, separator, name = line.partition("  ")
        safe_name(name)
        if separator != "  " or len(digest) != 64 or name in values:
            raise ValueError("candidate checksum inventory rejected")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError("candidate checksum rejected") from exc
        if not name.startswith("payload/"):
            raise ValueError("candidate payload path rejected")
        values[name] = digest
    if not values:
        raise ValueError("empty candidate payload")
    return values


def mapping_for(names: set[str]) -> dict[str, str]:
    if not names or any(not name.startswith("payload/") for name in names):
        raise ValueError("candidate payload path rejected")
    mapped = {name: safe_name("app/" + name.removeprefix("payload/")) for name in names}
    if len(mapped) != len({name.casefold() for name in mapped.values()}):
        raise ValueError("Windows install target collision")
    return mapped


def candidate_inventory(candidate: Path, expected_sha256: str, *,
                        prior_attestation: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """Verify candidate identity/inventory; optionally bind to an existing hash attestation.

    The attested path is used only for long-running local rehearsal when the exact
    candidate SHA was already computed by the package integrity run. Payload bytes
    are still verified against that inventory as they are copied into the install.
    """
    if prior_attestation is None:
        if digest_path(candidate) != expected_sha256:
            raise ValueError("candidate ZIP digest mismatch")
    else:
        try:
            summary = json.loads(prior_attestation.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("prior candidate attestation unavailable") from exc
        recorded_archive = str(summary.get("archive", "")).replace("\\", "/")
        candidate_suffix = "/".join(candidate.parts[-2:])
        if (summary.get("status") != "WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS"
                or summary.get("archive_sha256") != expected_sha256
                or summary.get("archive_bytes") != candidate.stat().st_size
                or not recorded_archive.endswith(candidate_suffix)
                or summary.get("release_eligible") is not False
                or summary.get("legal_clearance") is not False):
            raise ValueError("prior candidate attestation mismatch")
    with zipfile.ZipFile(candidate) as archive:
        members = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(members) != len(set(members)) or set(META) - set(members):
            raise ValueError("candidate member set rejected")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != KIND or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False
                or manifest.get("formal_tls_material_included") is not False):
            raise ValueError("current-app NON-RELEASE identity required")
        expected = checksums(archive.read("payload-sha256sums.txt"))
        if set(members) != set(expected) | META or manifest.get("payload_file_count") != len(expected):
            raise ValueError("candidate file inventory mismatch")
    return expected, mapping_for(set(expected))


def validate_candidate(candidate: Path, expected_sha256: str, stage: Path) -> tuple[dict[str, str], dict[str, str]]:
    expected, mapping = candidate_inventory(candidate, expected_sha256)
    extracted = verify_stage(stage, expected_kind=KIND)
    staged = extracted.get("files")
    if isinstance(staged, dict):
        actual = {str(name): str(digest) for name, digest in staged.items()}
        if actual != expected:
            raise ValueError("candidate and clean stage differ")
    else:
        # The independent stage verifier returns aggregate evidence on older schemas;
        # compare every file directly so no version can silently skip source binding.
        actual = {name: digest_path(stage / name) for name in expected}
        if actual != expected:
            raise ValueError("candidate and clean stage differ")
    return expected, mapping


def copy_and_publish(stage: Path, target: Path, expected: dict[str, str], mapping: dict[str, str],
                     *, fail_after: int | None = None) -> dict[str, object]:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (target.parent.resolve(strict=True) != temp or not str(target).isascii()
            or target.exists() or target.is_symlink() or Path(r"C:\PLMTool").exists()):
        raise ValueError("fresh direct ASCII Temp install target required")
    partial = Path(tempfile.mkdtemp(prefix="plm-current-app-partial-", dir=temp))
    committed = False
    try:
        app_root = partial / "app"
        app_root.mkdir()
        for index, (source_name, target_name) in enumerate(sorted(mapping.items())):
            if fail_after is not None and index >= fail_after:
                raise RuntimeError("injected copy interruption")
            source = stage / source_name
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(stage.resolve()):
                raise ValueError("staged source escaped verified root")
            destination = partial / target_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
        for folder in ("plugins", "data", "logs", "license", "runtime"):
            (partial / folder).mkdir(exist_ok=False)
        for source_name, target_name in mapping.items():
            if digest_path(partial / target_name) != expected[source_name]:
                raise ValueError("installed file readback hash mismatch")
        landed = {item.relative_to(partial).as_posix() for item in partial.rglob("*") if item.is_file()}
        if landed != set(mapping.values()):
            raise ValueError("installed file set differs")
        if target.exists() or target.is_symlink():
            raise ValueError("install target appeared before publication")
        os.rename(partial, target)
        committed = True
        return {"status": "NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_PASS",
                "payload_file_count": len(mapping), "release_eligible": False,
                "formal_install_performed": False, "services_changed": False,
                "database_started": False}
    finally:
        if not committed and partial.exists():
            if partial.parent.resolve(strict=True) != temp or not partial.name.startswith("plm-current-app-partial-"):
                raise ValueError("private partial ownership lost; manual inspection required")
            shutil.rmtree(partial)


def rehearse(candidate: Path, expected_sha256: str, stage: Path, target: Path) -> dict[str, object]:
    expected, mapping = validate_candidate(candidate, expected_sha256, stage)
    result = copy_and_publish(stage, target, expected, mapping)
    result["candidate_sha256"] = digest_path(candidate)
    result["mapping_sha256"] = hashlib.sha256(
        "".join(f"{a}\t{b}\n" for a, b in sorted(mapping.items())).encode("utf-8")
    ).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.candidate, args.expected_sha256, args.stage, args.target), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_REJECTED",
                          "reason": type(exc).__name__, "release_eligible": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
