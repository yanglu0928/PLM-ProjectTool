"""Assemble a non-release Tesseract 5.5.3 MSYS2 CLI PoC from fixed package bytes.

Static imports are a lower bound; this tool does not validate dynamic loads or rights.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from audit_tesseract_runtime_dependencies import pe_imports


SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "comdlg32.dll", "crypt32.dll", "gdi32.dll",
    "iphlpapi.dll", "kernel32.dll", "msvcrt.dll", "ole32.dll", "secur32.dll",
    "shell32.dll", "user32.dll", "version.dll", "wldap32.dll", "ws2_32.dll",
}
TESSERACT_PACKAGE = ("mingw-w64-x86_64-tesseract-ocr", "5.5.3-1")
GCC_PACKAGE = ("mingw-w64-x86_64-gcc-libs", "16.1.0-5")
EXTRA_ARCHIVE_HASHES = {
    TESSERACT_PACKAGE: "67c0a857e9f028f88d1463c0293885d806334346a81d70be5e38f08bad11e1e3",
    GCC_PACKAGE: "aa560f5438c35b71c3e7b24fd5becbca028f70c5b4d1f1697a86ff80fec947da",
}
TESSDATA_FILES = ("eng.traineddata", "chi_sim.traineddata", "chi_sim_vert.traineddata",
                  "osd.traineddata", "pdf.ttf")
TESSDATA_HASHES = {
    "eng.traineddata": "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba",
    "chi_sim.traineddata": "4fef2d1306c8e87616d4d3e4c6c67faf5d44be3342290cf8f2f0f6e3aa7e735b",
    "chi_sim_vert.traineddata": "ea672a78157199c333aa12ec4e74550077689b545df5fc770903716850c8b2e5",
    "osd.traineddata": "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff",
    "pdf.ttf": "c7845420925a23d88ed830a63957b8af85a66a8daf8d9fc90e843673b2ef1a59",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata(root: Path) -> tuple[str, str]:
    values = {}
    for line in (root / ".PKGINFO").read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            values.setdefault(key, value)
    return values["pkgname"], values["pkgver"]


def archive(root: Path, name: str, version: str) -> Path:
    base = root.parent.parent
    short = name.removeprefix("mingw-w64-x86_64-")
    candidates = (
        base / f"{name}-{version}-any.pkg.tar.zst",
        base / f"msys2-candidate-{short}-{version}-any.pkg.tar.zst",
    )
    matches = [path for path in candidates if path.is_file()]
    if len(matches) != 1:
        raise ValueError(f"Source archive missing or ambiguous: {name} {version}")
    return matches[0]


def audit_inputs(matrix_path: Path, package_dir: Path) -> dict[tuple[str, str], dict]:
    expected = {}
    with matrix_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if not row["package"].startswith("mingw-w64-x86_64-"):
                continue
            key = row["package"], row["package_version"]
            prior = expected.setdefault(key, row["archive_sha256"])
            if prior != row["archive_sha256"]:
                raise ValueError(f"Conflicting package hashes in matrix: {key}")
    expected.update(EXTRA_ARCHIVE_HASHES)
    found = {}
    for root in package_dir.glob("msys2-candidate-*/extracted"):
        if not (root / ".PKGINFO").is_file():
            continue
        key = metadata(root)
        if key not in expected:
            continue
        if key in found:
            raise ValueError(f"Duplicate extracted package: {key}")
        package_archive = archive(root, *key)
        actual = sha256(package_archive)
        if actual != expected[key]:
            raise ValueError(f"Package archive hash differs from matrix: {key}")
        found[key] = {"root": root, "archive_sha256": actual}
    if set(found) != set(expected):
        raise ValueError(f"Required package set incomplete: {sorted(set(expected) - set(found))}")
    return found


def build(matrix_path: Path, package_dir: Path, tessdata_source: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Output must be a new path; do not overwrite an earlier PoC")
    packages = audit_inputs(matrix_path, package_dir)
    sources: dict[str, tuple[Path, tuple[str, str]]] = {}
    for key, package in packages.items():
        for path in (package["root"] / "mingw64/bin").glob("*.dll"):
            name = path.name.casefold()
            if name in sources and sha256(sources[name][0]) != sha256(path):
                raise ValueError(f"Ambiguous DLL from candidate packages: {name}")
            sources.setdefault(name, (path, key))
    exe = packages[TESSERACT_PACKAGE]["root"] / "mingw64/bin/tesseract.exe"
    if not exe.is_file():
        raise ValueError("Tesseract CLI missing from fixed package")
    needed = {"tesseract.exe": (exe, TESSERACT_PACKAGE)}
    pending = ["tesseract.exe"]
    external = set()
    while pending:
        for name in sorted(pe_imports(needed[pending.pop()][0])):
            if name in sources and name not in needed:
                needed[name] = sources[name]
                pending.append(name)
            elif name not in sources:
                if name not in SYSTEM_DLLS:
                    raise ValueError(f"Unresolved non-system PE import: {name}")
                external.add(name)
    output.mkdir(parents=True)
    files = []
    for name, (source, key) in sorted(needed.items()):
        target = output / name
        shutil.copyfile(source, target)
        if sha256(target) != sha256(source):
            raise ValueError(f"Copy changed binary bytes: {name}")
        files.append({"path": name, "sha256": sha256(target), "package": key[0],
                      "version": key[1], "archive_sha256": packages[key]["archive_sha256"]})
    tessdata_target = output / "tessdata"
    tessdata_target.mkdir()
    for name in TESSDATA_FILES:
        source = tessdata_source / name
        if sha256(source) != TESSDATA_HASHES[name]:
            raise ValueError(f"Fixed tessdata input hash differs: {name}")
        target = tessdata_target / name
        shutil.copyfile(source, target)
        files.append({"path": f"tessdata/{name}", "sha256": sha256(target),
                      "package": "fixed prior PoC tessdata", "version": None,
                      "archive_sha256": None})
    for name in ("configs", "tessconfigs"):
        shutil.copytree(tessdata_source / name, tessdata_target / name)
        for target in sorted((tessdata_target / name).rglob("*")):
            if target.is_file():
                files.append({"path": target.relative_to(output).as_posix(),
                              "sha256": sha256(target), "package": "fixed prior PoC tessdata",
                              "version": None, "archive_sha256": None})
    result = {"schema_version": 1, "release_eligible": False,
              "status": "STATIC_IMPORT_CLOSURE_ONLY", "local_binary_count": len(needed),
              "external_import_names": sorted(external), "files": files}
    (output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--tessdata-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.matrix, args.package_dir, args.tessdata_source, args.output)
    print(json.dumps({key: result[key] for key in ("status", "release_eligible", "local_binary_count")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
