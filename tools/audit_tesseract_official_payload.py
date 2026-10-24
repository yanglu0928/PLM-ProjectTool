"""Inventory the pinned official Windows Tesseract payload without licensing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


INSTALLER_SHA256 = "bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4"
EXE_SHA256 = "c66f0f12ed76f6aa455dac97684bbc86756d6a732380bee09122454cfda3f420"
LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
NOTICE_PATTERN = re.compile(r"(?:^|/)(?:license|copying|notice)(?:[._-]|$)", re.IGNORECASE)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def audit(installer: Path, payload: Path, sevenzip: Path, *, installer_sha256: str = INSTALLER_SHA256,
          exe_sha256: str = EXE_SHA256, license_sha256: str = LICENSE_SHA256,
          expected_counts: tuple[int, int, int] = (139, 61, 4)) -> dict:
    if digest(installer) != installer_sha256:
        raise ValueError("installer hash mismatch")
    if digest(payload / "tesseract.exe") != exe_sha256:
        raise ValueError("extracted executable hash mismatch")
    if digest(payload / "doc" / "LICENSE") != license_sha256:
        raise ValueError("top-level license hash mismatch")
    files = sorted(path for path in payload.rglob("*") if path.is_file())
    if any(path.is_symlink() for path in payload.rglob("*")):
        raise ValueError("payload link rejected")
    dlls = [path for path in files if path.suffix.casefold() == ".dll"]
    jars = [path for path in files if path.suffix.casefold() == ".jar"]
    if (len(files), len(dlls), len(jars)) != expected_counts:
        raise ValueError("payload inventory count mismatch")
    # Re-extract the fixed archive independently: a manifest of the current
    # directory alone would accept a replaced third-party DLL.
    with tempfile.TemporaryDirectory(prefix="plm-tesseract-audit-") as temp:
        fresh = Path(temp)
        process = subprocess.run([str(sevenzip), "x", str(installer), f"-o{fresh}", "-y"],
                                 capture_output=True, text=True, timeout=120, check=False)
        if process.returncode:
            raise ValueError("independent installer extraction failed")
        fresh_files = {path.relative_to(fresh).as_posix(): path for path in fresh.rglob("*") if path.is_file()}
        if set(fresh_files) != {path.relative_to(payload).as_posix() for path in files}:
            raise ValueError("extracted path inventory mismatch")
        for path in files:
            relative = path.relative_to(payload).as_posix()
            if digest(path) != digest(fresh_files[relative]):
                raise ValueError(f"extracted file mismatch: {relative}")
    notices = []
    jar_notices = {}
    inventory = []
    for path in files:
        relative = path.relative_to(payload).as_posix()
        inventory.append({"path": relative, "size": path.stat().st_size, "sha256": digest(path)})
        if NOTICE_PATTERN.search(relative):
            notices.append(relative)
        if path in jars:
            with zipfile.ZipFile(path) as archive:
                jar_notices[relative] = sorted(name for name in archive.namelist()
                                               if NOTICE_PATTERN.search(name))
    return {
        "schema_version": "plm.tesseract-official-payload.v1",
        "status": "BYTE_INVENTORY_PASS_LICENSE_ATTRIBUTION_INCOMPLETE",
        "release_eligible": False,
        "installer_sha256": installer_sha256,
        "file_count": len(files),
        "dll_count": len(dlls),
        "jar_count": len(jars),
        "standalone_notice_files": notices,
        "jar_embedded_notice_files": jar_notices,
        "files": inventory,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--sevenzip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.installer, args.payload, args.sevenzip)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "release_eligible", "file_count", "dll_count", "jar_count", "standalone_notice_files", "jar_embedded_notice_files")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
