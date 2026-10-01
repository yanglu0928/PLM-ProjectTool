"""Atomically publish the fixed P33 non-release payload to a fresh ASCII Temp root.

This exercises only new-install file placement. It never writes C:\\PLMTool,
registers SCM services, starts a database, or claims release clearance.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_windows_unified_caddy_go_source_candidate import KIND
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from rehearse_windows_unified_pg18_layout import _copy_checked, validate_output_root
from verify_windows_unified_caddy_go_source_candidate import ARCHIVE_SHA256, verify as verify_candidate
from verify_windows_unified_extract import verify as verify_stage


def _assert_private_partial(path: Path, parent: Path) -> None:
    if (path.parent.resolve(strict=True) != parent or not path.name.startswith("plm-p39-partial-")
            or not path.is_dir() or path.is_symlink()):
        raise ValueError("partial install root is no longer owned")
    if any(item.is_symlink() for item in path.rglob("*")):
        raise ValueError("partial install contains link; manual inspection required")


def _copy_and_publish(stage: Path, target: Path, mapping: dict[str, str],
                      hashes: dict[str, str], *, fail_after: int | None = None) -> dict:
    """Copy verified names to a private sibling; publish only after full readback.

    On an ordinary exception the just-created sibling is removed. An OS/process
    crash may leave that sibling for manual inspection; it is never published.
    """
    validate_output_root(target)
    parent = target.parent.resolve(strict=True)
    partial = Path(tempfile.mkdtemp(prefix="plm-p39-partial-", dir=parent))
    committed = False
    try:
        for index, (source, destination) in enumerate(sorted(mapping.items())):
            if fail_after is not None and index >= fail_after:
                raise RuntimeError("injected copy interruption")
            expected = hashes[source] if source in hashes else digest_path(stage / source)
            _copy_checked(stage / source, partial / destination, expected)
        for name in ("plugins", "data", "logs", "license"):
            (partial / name).mkdir(exist_ok=False)
        landed = {str(path.relative_to(partial)).replace("\\", "/").casefold()
                  for path in partial.rglob("*") if path.is_file()}
        if landed != {destination.casefold() for destination in mapping.values()}:
            raise ValueError("partial install file set differs")
        for source, destination in mapping.items():
            expected = hashes[source] if source in hashes else digest_path(stage / source)
            if digest_path(partial / destination) != expected:
                raise ValueError("partial install readback hash differs")
        if target.exists() or target.is_symlink():
            raise ValueError("new install target appeared before publication")
        os.rename(partial, target)  # Same-volume Windows rename; never replace an existing root.
        committed = True
        return {"status": "NON_RELEASE_ATOMIC_FILE_PLACEMENT_PASS",
                "release_eligible": False, "formal_install_performed": False,
                "target_file_count": len(mapping), "services_changed": False,
                "database_started": False, "migration_executed": False}
    finally:
        if not committed and partial.exists():
            _assert_private_partial(partial, parent)
            shutil.rmtree(partial)


def rehearse(candidate: Path, source: Path, stage: Path, target: Path) -> dict:
    validate_output_root(target)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (stage.resolve(strict=True).parent != temp or stage == target
            or not str(stage).isascii() or Path(r"C:\PLMTool").exists()):
        raise ValueError("source stage or formal install root rejected")
    identity = verify_candidate(candidate, source)
    extracted = verify_stage(stage, expected_kind=KIND)
    if identity["payload_file_count"] != extracted["payload_file_count"]:
        raise ValueError("fixed candidate/stage count differs")
    hashes = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("stage hash manifest rejected")
        hashes[name] = digest
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("stage metadata differs from fixed candidate")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if len(hashes) != 21112 or len(mapping) != 21115:
        raise ValueError("fixed install mapping count differs")
    result = _copy_and_publish(stage, target, mapping, hashes)
    return {**result, "candidate_sha256": ARCHIVE_SHA256,
            "mapping_sha256": mapping_sha256, "target_root": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "source", "stage", "target"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = rehearse(args.candidate, args.source, args.stage, args.target)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"status": "ATOMIC_FILE_PLACEMENT_REJECTED",
                          "release_eligible": False, "reason": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
