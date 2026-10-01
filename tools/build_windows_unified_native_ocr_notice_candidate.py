"""Add exact native OCR license source bytes to a new NON-RELEASE P43 ZIP."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path

from audit_native_license_source_bytes import audit as audit_sources, read_tar_member
from audit_ghostscript_source_input import digest
from package_windows_embedded_candidate import _verify_archive
from package_windows_unified_candidate import _copy_stream, safe_name, zip_members
from verify_windows_unified_ghostscript_source_candidate import ARCHIVE_SHA256


KIND = "WINDOWS11_UNIFIED_PG18_CADDY_GO_GHOSTSCRIPT_NATIVE_OCR_NOTICE_DEVELOPMENT_CANDIDATE"
PREFIX = "payload/third-party-licenses/native-ocr/"
INDEX = PREFIX + "review-map.json"
README = PREFIX + "README.txt"
META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
README_BODY = (
    "Native OCR third-party license-text review inputs.\n"
    "The texts are copied byte-for-byte from fixed package/source archives.\n"
    "review-map.json maps each original PE and evidence record to a text hash.\n"
    "This is not a final NOTICE, legal approval, or release authorization.\n"
).encode("ascii")


def source_texts_and_map(proof: dict, matrix_rows: list[dict]) -> tuple[dict[str, bytes], bytes]:
    by_binary = {row["binary"]: row for row in matrix_rows}
    if len(by_binary) != 34 or proof["verified_evidence_records"] != 61:
        raise ValueError("native evidence population differs")
    texts: dict[str, bytes] = {}
    evidence = []
    for item in proof["rows"]:
        binary = by_binary.get(item["binary"])
        if binary is None or binary["release_obligations_reviewed"] != "NO":
            raise ValueError("native binary attribution differs")
        source_archive = Path(item.get("upstream_archive", item["source_archive"]))
        body = read_tar_member(source_archive, item["member_path"])
        sha = hashlib.sha256(body).hexdigest()
        if sha != item["text_sha256"]:
            raise ValueError("native source text changed during staging")
        path = PREFIX + "texts/" + sha + ".txt"
        if path in texts and texts[path] != body:
            raise ValueError("native text SHA collision")
        texts[path] = body
        evidence.append({"binary": item["binary"],
                         "binary_sha256": binary["binary_sha256"],
                         "source_name": binary["source_name"],
                         "source_version": binary["source_version"],
                         "package_declared_license": binary["package_declared_license"],
                         "evidence_kind": item["evidence_kind"],
                         "source_archive_name": Path(item["source_archive"]).name,
                         "source_archive_sha256": item["source_archive_sha256"],
                         "upstream_archive_name": Path(item["upstream_archive"]).name
                         if item.get("upstream_archive") else None,
                         "upstream_archive_sha256": item.get("upstream_archive_sha256"),
                         "source_member": item["member_path"],
                         "text_path": path, "text_sha256": sha,
                         "release_obligations_reviewed": "NO"})
    if len(evidence) != 61 or len(texts) != 42:
        raise ValueError("native text deduplication boundary differs")
    review_map = {"schema_version": "plm.native-ocr-license-review.v1",
                  "source_p43_sha256": ARCHIVE_SHA256,
                  "source_matrix_sha256": proof["native_matrix_sha256"],
                  "binary_count": 34, "evidence_record_count": 61,
                  "unique_text_count": 42, "review_status": "REVIEW_REQUIRED",
                  "legal_clearance": False, "release_eligible": False,
                  "evidence": evidence}
    return texts, (json.dumps(review_map, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def updated_metadata(manifest: dict, inventory: dict, count: int,
                     index_sha256: str) -> tuple[bytes, bytes]:
    if (manifest.get("payload_file_count") != 21114
            or any(manifest.get(key) is not False for key in (
                "release_eligible", "legal_clearance", "installation_performed",
                "service_registration_performed"))
            or inventory.get("review_status") != "REVIEW_REQUIRED"
            or inventory.get("ghostscript_source", {}).get("review_status") != "REVIEW_REQUIRED"
            or "native_ocr_license_evidence" in inventory):
        raise ValueError("P43 candidate metadata boundary changed")
    next_manifest = {**manifest, "kind": KIND, "source_p43_sha256": ARCHIVE_SHA256,
                     "payload_file_count": count,
                     "native_ocr_license_evidence_added": True,
                     "native_ocr_review_map_sha256": index_sha256,
                     "release_eligible": False, "legal_clearance": False,
                     "installation_performed": False, "service_registration_performed": False}
    next_inventory = {**inventory, "review_status": "REVIEW_REQUIRED",
                      "native_ocr_license_evidence": {
                          "binary_count": 34, "evidence_record_count": 61,
                          "unique_text_count": 42, "mapping_path": INDEX,
                          "mapping_sha256": index_sha256,
                          "review_status": "REVIEW_REQUIRED",
                          "legal_clearance": False}}
    return tuple((json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
                 for item in (next_manifest, next_inventory))


def build(parent: Path, ancestor: Path, grandparent: Path, native_matrix: Path,
          package_dir: Path, fallback_csv: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir():
        raise ValueError("output parent must exist")
    proof = audit_sources(parent, ancestor, grandparent, native_matrix, package_dir, fallback_csv)
    with native_matrix.open("r", encoding="utf-8", newline="") as stream:
        matrix_rows = list(csv.DictReader(stream))
    texts, index_body = source_texts_and_map(proof, matrix_rows)
    additions = {**texts, INDEX: index_body, README: README_BODY}
    with zipfile.ZipFile(parent) as old:
        members = zip_members(old)
        manifest = json.loads(old.read("manifest.json"))
        inventory = json.loads(old.read("third-party-inventory.json"))
        hashes = {}
        folded = set()
        for line in old.read("payload-sha256sums.txt").decode("ascii").splitlines():
            sha, separator, name = line.partition("  ")
            safe_name(name)
            if separator != "  " or name.casefold() in folded:
                raise ValueError("P43 payload hash list rejected")
            hashes[name] = sha
            folded.add(name.casefold())
        if (len(hashes) != 21114 or set(members) != set(hashes) | META
                or any(name.casefold() in folded for name in additions)):
            raise ValueError("P43 payload set or new sidecar collision")
        for name in additions:
            safe_name(name)
        expected = {**hashes, **{name: hashlib.sha256(body).hexdigest()
                                for name, body in additions.items()}}
        if len(expected) != 21158:
            raise ValueError("native OCR candidate payload count differs")
        manifest_body, inventory_body = updated_metadata(
            manifest, inventory, len(expected), expected[INDEX])
        run = output_parent / ("unified-native-ocr-notice-candidate-" + uuid.uuid4().hex[:12])
        run.mkdir(mode=0o700, exist_ok=False)
        output = run / "NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-ghostscript-native-ocr-notices.zip"
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as target:
            for name in sorted(hashes):
                with old.open(name) as inp, target.open(name, "w", force_zip64=True) as out:
                    if _copy_stream(inp, out) != hashes[name]:
                        raise ValueError("P43 payload changed during copy")
            for name, body in sorted(additions.items()):
                target.writestr(name, body)
            sums = "".join(f"{sha}  {name}\n" for name, sha in sorted(expected.items())).encode("ascii")
            target.writestr("payload-sha256sums.txt", sums)
            target.writestr("manifest.json", manifest_body)
            target.writestr("third-party-inventory.json", inventory_body)
    if digest(parent) != ARCHIVE_SHA256:
        raise ValueError("P43 parent changed after assembly")
    expected.update({"payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                     "manifest.json": hashlib.sha256(manifest_body).hexdigest(),
                     "third-party-inventory.json": hashlib.sha256(inventory_body).hexdigest()})
    _verify_archive(output, expected)
    result = {"status": "NON_RELEASE_NATIVE_OCR_NOTICE_CANDIDATE_INTEGRITY_PASS",
              "archive": str(output), "archive_sha256": digest(output),
              "archive_bytes": output.stat().st_size,
              "payload_file_count": len(expected) - len(META),
              "source_p43_sha256": ARCHIVE_SHA256,
              "unchanged_parent_payload_count": 21114,
              "unique_license_text_count": 42, "evidence_record_count": 61,
              "release_eligible": False, "legal_clearance": False,
              "installation_performed": False, "service_registration_performed": False}
    (run / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parent", "ancestor", "grandparent", "native-matrix", "package-dir",
                 "fallback-csv", "output-parent"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.parent, args.ancestor, args.grandparent, args.native_matrix,
                           args.package_dir, args.fallback_csv, args.output_parent),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
