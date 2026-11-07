"""Split and securely reassemble large non-release parent candidate artifacts.

The workflow uses small independent GitHub artifacts to transfer a verified
parent ZIP to a Windows 11 target when the artifact connector cannot stream the
full package. Every chunk is bound to a manifest and the original ZIP digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


CHUNK_BYTES = 50_000_000
MAX_ARCHIVE_BYTES = 512_000_000
MANIFEST_NAME = "chunk-manifest.json"
SUMMARY_NAME = "verification-summary.json"
FORMAT = "PLM_PARENT_CANDIDATE_CHUNKS_V1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _runner_root() -> Path:
    value = os.environ.get("RUNNER_TEMP")
    if not value:
        raise ValueError("D-drive RUNNER_TEMP is required")
    root = Path(value).resolve(strict=True)
    if (not str(root).isascii() or root.drive.casefold() != "d:"
            or Path(tempfile.gettempdir()).resolve(strict=True) != root):
        raise ValueError("D-drive RUNNER_TEMP boundary rejected")
    return root


def _direct_child(path: Path, root: Path, *, must_exist: bool) -> Path:
    if path.is_symlink():
        raise ValueError("candidate transfer path is a symlink")
    resolved = path.resolve(strict=must_exist)
    if (resolved.parent != root or resolved.drive.casefold() == "c:"
            or not str(resolved).isascii() or resolved.is_symlink()):
        raise ValueError("candidate transfer path escaped RUNNER_TEMP")
    return resolved


def _validate_manifest(manifest: object, prefix: str) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise ValueError("candidate chunk manifest rejected")
    if (manifest.get("format") != FORMAT
            or manifest.get("candidate_prefix") != prefix):
        raise ValueError("candidate chunk manifest rejected")
    size = manifest.get("source_archive_size_bytes")
    chunk_size = manifest.get("chunk_size_bytes")
    chunks = manifest.get("chunks")
    if (not isinstance(size, int) or not 0 < size <= MAX_ARCHIVE_BYTES
            or not isinstance(chunk_size, int) or not 0 < chunk_size <= CHUNK_BYTES
            or not isinstance(chunks, list) or not 0 < len(chunks) <= 16
            or len(chunks) != (size + chunk_size - 1) // chunk_size):
        raise ValueError("candidate chunk manifest bounds rejected")
    archive_name = manifest.get("source_archive_name")
    archive_path = PurePosixPath(str(archive_name))
    if (not archive_name or archive_path.name != archive_name
            or archive_name in {".", ".."}):
        raise ValueError("candidate archive name rejected")
    for index, meta in enumerate(chunks):
        if not isinstance(meta, dict):
            raise ValueError("candidate chunk entry rejected")
        expected_name = f"{prefix}.part-{index:02d}.bin"
        expected_size = chunk_size if index < len(chunks) - 1 else size - chunk_size * index
        if (meta.get("index") != index or meta.get("name") != expected_name
                or meta.get("size_bytes") != expected_size
                or not isinstance(meta.get("sha256"), str)
                or len(meta["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in meta["sha256"])):
            raise ValueError("candidate chunk entry bounds rejected")
    for key in ("source_archive_sha256", "verification_summary_sha256"):
        value = manifest.get(key)
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("candidate digest format rejected")
    return manifest


def split_candidate(input_dir: Path, output_dir: Path, prefix: str,
                    chunk_bytes: int = CHUNK_BYTES) -> dict[str, object]:
    if prefix not in {"old", "current"}:
        raise ValueError("candidate prefix rejected")
    if not 1 <= chunk_bytes <= CHUNK_BYTES:
        raise ValueError("chunk size rejected")
    root = _runner_root()
    source = _direct_child(input_dir, root, must_exist=True)
    target = _direct_child(output_dir, root, must_exist=False)
    if target.exists():
        raise ValueError("chunk output must be new")
    entries = list(source.iterdir())
    archives = [p for p in entries if p.is_file() and p.suffix.casefold() == ".zip"]
    summary = source / SUMMARY_NAME
    if (len(entries) != 2 or len(archives) != 1 or not summary.is_file() or summary.is_symlink()
            or any(p.is_symlink() for p in archives)):
        raise ValueError("candidate artifact inventory rejected")
    archive = archives[0]
    size = archive.stat().st_size
    if size <= 0 or size > MAX_ARCHIVE_BYTES:
        raise ValueError("candidate archive size rejected")
    # The input artifact's verification record is part of the handoff and must be
    # valid JSON before any output chunks are created.
    summary_data = json.loads(summary.read_text(encoding="utf-8-sig"))
    if not isinstance(summary_data, dict) or summary.stat().st_size > 1_000_000:
        raise ValueError("candidate verification summary rejected")

    target.mkdir()
    digest = hashlib.sha256()
    chunks: list[dict[str, object]] = []
    try:
        with archive.open("rb") as src:
            index = 0
            while True:
                block = src.read(chunk_bytes)
                if not block:
                    break
                name = f"{prefix}.part-{index:02d}.bin"
                part = target / name
                part.write_bytes(block)
                digest.update(block)
                chunks.append({"index": index, "name": name,
                               "size_bytes": len(block),
                               "sha256": hashlib.sha256(block).hexdigest()})
                index += 1
        if digest.digest_size != 32 or sum(int(c["size_bytes"]) for c in chunks) != size:
            raise ValueError("candidate split byte count mismatch")
        if (summary_data.get("status") !=
                "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS"
                or summary_data.get("release_eligible") is not False
                or summary_data.get("legal_clearance") is not False
                or summary_data.get("archive_sha256") != digest.hexdigest()):
            raise ValueError("candidate archive identity or release state rejected")
        manifest = {
            "format": FORMAT,
            "candidate_prefix": prefix,
            "source_archive_name": archive.name,
            "source_archive_size_bytes": size,
            "source_archive_sha256": digest.hexdigest(),
            "verification_summary_sha256": _sha256(summary),
            "chunk_size_bytes": chunk_bytes,
            "chunks": chunks,
        }
        manifest_path = target / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")
        (target / SUMMARY_NAME).write_bytes(summary.read_bytes())
        return manifest
    except Exception:
        # Target is a newly-created direct child owned by this invocation. Remove
        # only that child on failure; never clean the RUNNER_TEMP root.
        import shutil
        shutil.rmtree(target)
        raise


def join_candidate(artifact_zips: list[Path], output_archive: Path,
                   output_summary: Path, prefix: str) -> dict[str, object]:
    if prefix not in {"old", "current"} or not artifact_zips:
        raise ValueError("candidate transfer inputs rejected")
    root = _runner_root()
    output = _direct_child(output_archive, root, must_exist=False)
    summary_out = _direct_child(output_summary, root, must_exist=False)
    if output.exists() or summary_out.exists() or output == summary_out:
        raise ValueError("candidate transfer outputs must be new and distinct")
    stage = root / ("a35-join-stage-" + secrets.token_hex(8))
    if stage.exists():
        raise ValueError("candidate join staging collision")
    stage.mkdir()
    manifests: list[dict[str, object]] = []
    parts: dict[int, Path] = {}
    summary_bytes: bytes | None = None
    try:
        for artifact_path in artifact_zips:
            if artifact_path.is_symlink():
                raise ValueError("artifact ZIP path rejected")
            artifact = artifact_path.resolve(strict=True)
            try:
                artifact.relative_to(root)
            except ValueError:
                raise ValueError("artifact ZIP escaped RUNNER_TEMP") from None
            if artifact.suffix.casefold() != ".zip":
                raise ValueError("artifact ZIP path rejected")
            with zipfile.ZipFile(artifact) as bundle:
                names = bundle.namelist()
                if (len(names) != 3 or len(names) != len(set(names))
                        or MANIFEST_NAME not in names or SUMMARY_NAME not in names):
                    raise ValueError("chunk artifact inventory rejected")
                if any(PurePosixPath(n).is_absolute() or "\\" in n
                       or any(p in {"", ".", ".."} for p in PurePosixPath(n).parts)
                       for n in names):
                    raise ValueError("chunk artifact path rejected")
                manifest = json.loads(bundle.read(MANIFEST_NAME))
                manifest = _validate_manifest(manifest, prefix)
                part_names = [n for n in names if n not in {MANIFEST_NAME, SUMMARY_NAME}]
                part_meta = manifest.get("chunks")
                if not isinstance(part_meta, list):
                    raise ValueError("chunk manifest inventory rejected")
                meta = {str(m.get("name")): m for m in part_meta if isinstance(m, dict)}
                if len(meta) != len(part_meta) or len(part_names) != 1:
                    raise ValueError("chunk artifact membership rejected")
                name = part_names[0]
                if name not in meta:
                    raise ValueError("unexpected candidate chunk")
                if bundle.getinfo(name).file_size > CHUNK_BYTES:
                    raise ValueError("candidate chunk size rejected")
                index = int(meta[name]["index"])
                if index in parts or index < 0 or index >= len(part_meta):
                    raise ValueError("duplicate candidate chunk")
                part_path = stage / (f"part-{index:02d}.bin")
                part_hash = hashlib.sha256()
                part_size = 0
                with bundle.open(name) as part, part_path.open("xb") as out:
                    while block := part.read(1024 * 1024):
                        out.write(block)
                        part_hash.update(block)
                        part_size += len(block)
                if (part_size != int(meta[name]["size_bytes"])
                        or part_hash.hexdigest() != meta[name]["sha256"]):
                    raise ValueError("candidate chunk digest mismatch")
                parts[index] = part_path
                manifests.append(manifest)
                summary_info = bundle.getinfo(SUMMARY_NAME)
                if summary_info.file_size > 1_000_000:
                    raise ValueError("candidate verification summary size rejected")
                bundle_summary = bundle.read(SUMMARY_NAME)
                if hashlib.sha256(bundle_summary).hexdigest() != manifest.get(
                        "verification_summary_sha256"):
                    raise ValueError("candidate summary digest mismatch")
                if summary_bytes is not None and summary_bytes != bundle_summary:
                    raise ValueError("candidate summaries differ")
                summary_bytes = bundle_summary
        canonical = manifests[0]
        if any(m != canonical for m in manifests):
            raise ValueError("candidate chunk manifests differ")
        expected = canonical["chunks"]
        if set(parts) != set(range(len(expected))):
            raise ValueError("candidate chunk sequence incomplete")
        if canonical.get("candidate_prefix") != prefix:
            raise ValueError("candidate prefix mismatch")
        joined_hash = hashlib.sha256()
        written = 0
        try:
            with output.open("xb") as stream:
                for index in range(len(expected)):
                    with parts[index].open("rb") as part:
                        while block := part.read(1024 * 1024):
                            stream.write(block)
                            joined_hash.update(block)
                            written += len(block)
            if (written != int(canonical["source_archive_size_bytes"])
                    or joined_hash.hexdigest() != canonical["source_archive_sha256"]
                    or summary_bytes is None):
                raise ValueError("reassembled candidate digest mismatch")
            summary_out.write_bytes(summary_bytes)
        except Exception:
            output.unlink(missing_ok=True)
            summary_out.unlink(missing_ok=True)
            raise
        return {"status": "CANDIDATE_ARTIFACT_REASSEMBLED",
                "candidate_prefix": prefix, "archive_size_bytes": written,
                "archive_sha256": joined_hash.hexdigest(),
                "chunk_count": len(parts),
                "verification_summary_sha256": hashlib.sha256(summary_bytes).hexdigest()}
    finally:
        shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    split = sub.add_parser("split")
    split.add_argument("--input-dir", type=Path, required=True)
    split.add_argument("--output-dir", type=Path, required=True)
    split.add_argument("--prefix", choices=("old", "current"), required=True)
    split.add_argument("--chunk-bytes", type=int, default=CHUNK_BYTES)
    join = sub.add_parser("join")
    join.add_argument("--artifact-zips", nargs="+", type=Path, required=True)
    join.add_argument("--output-archive", type=Path, required=True)
    join.add_argument("--output-summary", type=Path, required=True)
    join.add_argument("--prefix", choices=("old", "current"), required=True)
    args = parser.parse_args()
    try:
        if args.command == "split":
            result = split_candidate(args.input_dir, args.output_dir, args.prefix,
                                     args.chunk_bytes)
        else:
            result = join_candidate(args.artifact_zips, args.output_archive,
                                    args.output_summary, args.prefix)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        print(json.dumps({"status": "CANDIDATE_ARTIFACT_TRANSFER_REJECTED"}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
