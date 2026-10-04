"""Export exact P45 native OCR license review bytes to a small tracked packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from build_windows_unified_native_ocr_notice_candidate import INDEX, PREFIX, README
from verify_windows_unified_native_ocr_notice_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)


def packet_members(review: dict) -> dict[str, str]:
    if (review.get("binary_count") != 34 or review.get("evidence_record_count") != 61
            or review.get("unique_text_count") != 42
            or review.get("release_eligible") is not False
            or review.get("legal_clearance") is not False
            or review.get("review_status") != "REVIEW_REQUIRED"):
        raise ValueError("native OCR review boundary differs")
    evidence = review.get("evidence", [])
    if len(evidence) != 61 or len({item.get("binary") for item in evidence}) != 34:
        raise ValueError("native OCR evidence coverage differs")
    texts: dict[str, str] = {}
    for item in evidence:
        sha = item.get("text_sha256")
        path = item.get("text_path")
        if (not isinstance(sha, str) or len(sha) != 64
                or any(char not in "0123456789abcdef" for char in sha)
                or path != PREFIX + "texts/" + sha + ".txt"
                or item.get("release_obligations_reviewed") != "NO"):
            raise ValueError("native OCR review text attribution differs")
        texts[path] = sha
    if len(texts) != 42:
        raise ValueError("native OCR unique text count differs")
    return texts


def export(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
           native_matrix: Path, output: Path) -> dict:
    if not output.parent.is_dir() or output.exists() or output.is_symlink():
        raise ValueError("review output must be a new child of an existing directory")
    proof = verify_candidate(candidate, parent, ancestor, grandparent, native_matrix)
    if proof.get("archive_sha256") != ARCHIVE_SHA256 or proof.get("release_eligible") is not False:
        raise ValueError("native OCR candidate proof differs")
    with zipfile.ZipFile(candidate) as archive:
        review_bytes = archive.read(INDEX)
        review = json.loads(review_bytes)
        texts = packet_members(review)
        bodies = {"review-map.json": review_bytes,
                  "README.txt": archive.read(README)}
        for path, sha in texts.items():
            body = archive.read(path)
            if hashlib.sha256(body).hexdigest() != sha:
                raise ValueError("native OCR candidate text differs")
            bodies[path.removeprefix(PREFIX)] = body
    if len(bodies) != 44 or sum(len(body) for body in bodies.values()) > 1024 * 1024:
        raise ValueError("native OCR review packet scope differs")
    output.mkdir(exist_ok=False)
    for name, body in sorted(bodies.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(body)
        if target.read_bytes() != body:
            raise ValueError("native OCR review packet write/readback differs")
    return {"status": "NON_RELEASE_NATIVE_OCR_REVIEW_PACKET_EXPORTED",
            "candidate_sha256": ARCHIVE_SHA256,
            "packet_file_count": len(bodies),
            "packet_bytes": sum(len(body) for body in bodies.values()),
            "review_map_sha256": hashlib.sha256(review_bytes).hexdigest(),
            "license_text_count": len(texts), "evidence_record_count": len(review["evidence"]),
            "release_eligible": False, "legal_clearance": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.candidate, args.parent, args.ancestor, args.grandparent,
                            args.native_matrix, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
