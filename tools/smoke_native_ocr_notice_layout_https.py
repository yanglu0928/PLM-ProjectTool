"""Full-hash-check P45 native OCR notice layout, then smoke loopback HTTPS."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from build_windows_unified_native_ocr_notice_candidate import KIND, INDEX, PREFIX, README
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from smoke_caddy_isolated_layout_https import smoke as original_smoke
from verify_windows_unified_extract import verify as verify_stage
from verify_windows_unified_native_ocr_notice_candidate import verify as verify_candidate


def verify_layout(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
                  native_matrix: Path, stage: Path, layout: Path) -> dict:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    stage = stage.resolve(strict=True)
    layout = layout.resolve(strict=True)
    if (stage.parent != temp or layout.parent != temp or not str(stage).isascii()
            or not str(layout).isascii() or stage == layout
            or not layout.name.startswith("plm-install-rehearsal-")
            or Path("C:\\PLMTool").exists()):
        raise ValueError("native OCR notice isolated stage/layout root rejected")
    identity = verify_candidate(candidate, parent, ancestor, grandparent, native_matrix)
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("native OCR notice stage count differs")
    hashes: dict[str, str] = {}
    folded: set[str] = set()
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        sha, separator, name = line.partition("  ")
        if separator != "  " or name.casefold() in folded:
            raise ValueError("native OCR notice stage hash list rejected")
        hashes[name] = sha
        folded.add(name.casefold())
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("native OCR notice stage metadata differs")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if (len(hashes) != 21158 or len(mapping) != 21161
            or mapping.get(INDEX) != "app/third-party-licenses/native-ocr/review-map.json"
            or mapping.get(README) != "app/third-party-licenses/native-ocr/README.txt"):
        raise ValueError("native OCR notice layout mapping differs")
    review = json.loads((stage / INDEX).read_text(encoding="utf-8"))
    if (len(review.get("evidence", [])) != 61 or review.get("unique_text_count") != 42
            or review.get("legal_clearance") is not False
            or review.get("release_eligible") is not False):
        raise ValueError("native OCR notice review boundary differs")
    texts = {}
    for item in review["evidence"]:
        source, sha = item["text_path"], item["text_sha256"]
        if (source != PREFIX + "texts/" + sha + ".txt"
                or mapping.get(source) != "app/third-party-licenses/native-ocr/texts/" + sha + ".txt"
                or item.get("release_obligations_reviewed") != "NO"):
            raise ValueError("native OCR notice text mapping differs")
        texts[source] = sha
    if len(texts) != 42:
        raise ValueError("native OCR notice unique text count differs")
    landed = {str(path.relative_to(layout)).replace("\\", "/").casefold()
              for path in layout.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("native OCR notice layout file set differs")
    for source, target in mapping.items():
        expected = hashes[source] if source in hashes else digest_path(stage / source)
        if digest_path(layout / target) != expected:
            raise ValueError("native OCR notice layout target hash differs")
    for source, sha in texts.items():
        if digest_path(layout / mapping[source]) != sha:
            raise ValueError("native OCR notice layout text differs")
    return {"mapping_sha256": mapping_sha256, "file_count": len(mapping),
            "license_text_count": len(texts), "evidence_record_count": len(review["evidence"])}


def smoke(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
          native_matrix: Path, stage: Path, layout: Path) -> dict:
    verified = verify_layout(candidate, parent, ancestor, grandparent,
                             native_matrix, stage, layout)
    result = original_smoke(candidate, stage, layout, layout_verifier=lambda *_: verified)
    if result["verified_file_count"] != 21161 or result["release_eligible"] is not False:
        raise ValueError("native OCR notice HTTPS result differs")
    return {**result, "status": "NON_RELEASE_NATIVE_OCR_NOTICE_LAYOUT_HTTPS_PASS",
            "license_text_count": verified["license_text_count"],
            "evidence_record_count": verified["evidence_record_count"],
            "legal_clearance": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix", "stage", "layout"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.parent, args.ancestor, args.grandparent,
                           args.native_matrix, args.stage, args.layout),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
