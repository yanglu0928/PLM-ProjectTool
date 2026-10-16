"""Re-read exact native OCR license texts from fixed package/source archives.

This establishes source-byte provenance only, not applicable rights or release approval.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

from audit_native_pe_license_materials import audit as audit_native
from build_tesseract_msys2_poc import archive as package_archive, metadata, sha256


LIBTIFF_UPSTREAM = Path("msys2-source-libtiff-4.7.2-1/mingw-w64-libtiff/tiff-4.7.2.tar.gz")


def split_evidence(row: dict) -> list[tuple[str, str]]:
    paths = [part.strip() for part in row["license_evidence_path"].split(" | ")]
    hashes = [part.strip() for part in row["license_evidence_sha256"].split(" | ")]
    if (not paths or len(paths) != len(hashes)
            or any(not path or PurePosixPath(path).is_absolute()
                   or ".." in PurePosixPath(path).parts for path in paths)
            or any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
                   for value in hashes)):
        raise ValueError("native license evidence path/hash pairing differs")
    return list(zip(paths, hashes))


def read_tar_member(archive_path: Path, member: str) -> bytes:
    if (PurePosixPath(member).is_absolute() or ".." in PurePosixPath(member).parts
            or not member):
        raise ValueError("unsafe source archive member")
    if archive_path.name.endswith(".pkg.tar.zst"):
        process = subprocess.run(["tar.exe", "-xOf", str(archive_path), member],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 check=False, timeout=60)
        if process.returncode != 0:
            raise ValueError(f"source package member unavailable: {archive_path.name}/{member}")
        return process.stdout
    with tarfile.open(archive_path, "r:gz") as source:
        item = source.getmember(member)
        if not item.isfile():
            raise ValueError(f"source member is not a regular file: {member}")
        handle = source.extractfile(item)
        if handle is None:
            raise ValueError(f"source member unavailable: {member}")
        return handle.read()


def verify_sources(rows: list[dict], package_dir: Path, fallback_rows: list[dict]) -> dict:
    fallback: dict[str, list[dict]] = {}
    for item in fallback_rows:
        fallback.setdefault(item["dll"], []).append(item)
    package_roots: dict[tuple[str, str], Path] = {}
    for root in package_dir.glob("msys2-candidate-*/extracted"):
        if (root / ".PKGINFO").is_file():
            key = metadata(root)
            if key in package_roots:
                raise ValueError(f"ambiguous extracted package: {key}")
            package_roots[key] = root

    archive_hashes: dict[Path, str] = {}
    member_bytes: dict[tuple[Path, str], bytes] = {}

    def fixed_archive(path: Path, expected: str) -> None:
        if not path.is_file():
            raise ValueError(f"source archive missing: {path}")
        if path not in archive_hashes:
            archive_hashes[path] = sha256(path)
        actual = archive_hashes[path]
        if actual != expected:
            raise ValueError(f"source archive SHA differs: {path}")

    def fixed_member(path: Path, member: str, expected: str) -> bytes:
        key = path, member
        if key not in member_bytes:
            member_bytes[key] = read_tar_member(path, member)
        body = member_bytes[key]
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError(f"source license text SHA differs: {path.name}/{member}")
        return body

    result = []
    for row in rows:
        binary = row["binary"]
        status = row["license_evidence_status"]
        if row["source_kind"] == "MSYS2_PACKAGE_BYTES":
            key = row["source_name"], row["source_version"]
            root = package_roots.get(key)
            if root is None:
                raise ValueError(f"exact extracted package missing: {key}")
            binary_archive = package_archive(root, *key)
            fixed_archive(binary_archive, row["source_sha256"])
            if status == "PACKAGE_TEXT_HASH_VERIFIED":
                if binary in fallback:
                    raise ValueError(f"unexpected source fallback: {binary}")
                for path, expected in split_evidence(row):
                    body = fixed_member(binary_archive, path, expected)
                    extracted = root / Path(*PurePosixPath(path).parts)
                    if not extracted.is_file() or extracted.read_bytes() != body:
                        raise ValueError(f"extracted package license differs: {binary}/{path}")
                    result.append({"binary": binary, "evidence_kind": "PACKAGE_MEMBER",
                                   "source_archive": binary_archive.as_posix(),
                                   "source_archive_sha256": row["source_sha256"],
                                   "member_path": path, "text_sha256": expected})
            elif status == "PRIOR_A04_SOURCE_TEXT_REFERENCE":
                source_rows = fallback.get(binary, [])
                pairs = split_evidence(row)
                if len(source_rows) != len(pairs):
                    raise ValueError(f"source fallback cardinality differs: {binary}")
                for (matrix_path, expected), source in zip(pairs, source_rows):
                    if (matrix_path != source["source_package"] + "/" + source["source_relative_path"]
                            or expected != source["text_sha256"]):
                        raise ValueError(f"source fallback matrix pairing differs: {binary}")
                    source_archive = package_dir / ("msys2-source-" + source["source_package"])
                    fixed_archive(source_archive, source["source_archive_sha256"])
                    source_stem = source["source_package"].removeprefix("mingw-w64-").removesuffix(".src.tar.zst")
                    source_root = package_dir / ("msys2-source-" + source_stem)
                    upstream_name = PurePosixPath(source["source_relative_path"]).parts[0] + ".tar.gz"
                    upstream = list((source_root / "extracted").glob("mingw-w64-*/" + upstream_name))
                    if len(upstream) != 1:
                        raise ValueError(f"exact upstream archive missing: {binary}")
                    fixed_archive(upstream[0], source["upstream_archive_sha256"])
                    fixed_member(upstream[0], source["source_relative_path"], expected)
                    result.append({"binary": binary, "evidence_kind": "UPSTREAM_FALLBACK_MEMBER",
                                   "source_archive": source_archive.as_posix(),
                                   "source_archive_sha256": source["source_archive_sha256"],
                                   "upstream_archive": upstream[0].as_posix(),
                                   "upstream_archive_sha256": source["upstream_archive_sha256"],
                                   "member_path": source["source_relative_path"],
                                   "text_sha256": expected})
            else:
                raise ValueError(f"unexpected native license evidence status: {binary}")
        elif row["source_kind"] == "UPSTREAM_SOURCE_BUILD" and status == "SOURCE_TEXT_HASH_VERIFIED":
            upstream = package_dir / LIBTIFF_UPSTREAM
            fixed_archive(upstream, row["source_sha256"])
            for member, expected in split_evidence(row):
                fixed_member(upstream, member, expected)
                result.append({"binary": binary, "evidence_kind": "UPSTREAM_BUILD_MEMBER",
                               "source_archive": upstream.as_posix(),
                               "source_archive_sha256": row["source_sha256"],
                               "member_path": member, "text_sha256": expected})
        else:
            raise ValueError(f"unexpected native source kind: {binary}")
    if len(rows) != 34 or len(result) != 61 or len(fallback_rows) != 7:
        raise ValueError("34-PE/61-text source evidence population differs")
    return {"verified_evidence_records": len(result),
            "unique_text_sha256_count": len({item["text_sha256"] for item in result}),
            "unique_archive_count": len(archive_hashes),
            "evidence_kind_counts": dict(sorted(Counter(item["evidence_kind"] for item in result).items())),
            "rows": result}


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path,
          package_dir: Path, fallback_csv: Path) -> dict:
    prior = audit_native(candidate, parent, ancestor, native_matrix)
    with native_matrix.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with fallback_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        fallback = list(csv.DictReader(stream))
    verified = verify_sources(rows, package_dir, fallback)
    return {"status": "NATIVE_LICENSE_SOURCE_BYTES_VERIFIED_NON_RELEASE",
            "candidate_sha256": prior["candidate_sha256"],
            "native_matrix_sha256": prior["native_matrix_sha256"],
            "release_eligible": False, "legal_clearance": False, **verified}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "native-matrix", "package-dir", "fallback-csv"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.ancestor, args.native_matrix,
                           args.package_dir, args.fallback_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
