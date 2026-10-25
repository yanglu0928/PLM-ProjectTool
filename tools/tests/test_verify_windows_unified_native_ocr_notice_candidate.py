from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_native_ocr_notice_candidate import INDEX, PREFIX, README  # noqa: E402
from verify_windows_unified_native_ocr_notice_candidate import (  # noqa: E402
    P43_SHA256, check_lineage,
)


def fixture() -> tuple[dict, dict, dict, dict, dict, list[dict]]:
    parent = {f"payload/dummy/{index}": "0" * 64 for index in range(21114)}
    texts = {hashlib.sha256(f"text {index}".encode()).hexdigest() for index in range(42)}
    hashes = {**parent, **{PREFIX + "texts/" + sha + ".txt": sha for sha in texts},
              INDEX: "f" * 64, README.casefold(): "e" * 64}
    manifest = {"source_p43_sha256": P43_SHA256,
                "native_ocr_license_evidence_added": True,
                "native_ocr_review_map_sha256": "f" * 64,
                "release_eligible": False, "legal_clearance": False,
                "installation_performed": False, "service_registration_performed": False,
                "formal_tls_material_included": False}
    inventory = {"review_status": "REVIEW_REQUIRED",
                 "native_ocr_license_evidence": {
                     "binary_count": 34, "evidence_record_count": 61,
                     "unique_text_count": 42, "mapping_path": INDEX,
                     "mapping_sha256": "f" * 64,
                     "review_status": "REVIEW_REQUIRED", "legal_clearance": False}}
    evidence = []
    matrix = []
    for binary_index in range(34):
        members, shas = [], []
        for item_index in range(binary_index, 61, 34):
            sha = hashlib.sha256(f"text {item_index % 42}".encode()).hexdigest()
            member = f"licenses/L{item_index}"
            members.append(member)
            shas.append(sha)
            evidence.append({"binary": f"a{binary_index}.dll", "binary_sha256": "a" * 64,
                             "source_name": "sample", "source_version": "1.0",
                             "package_declared_license": "spdx:MIT",
                             "release_obligations_reviewed": "NO",
                             "evidence_kind": "PACKAGE_MEMBER",
                             "source_archive_name": "archive.pkg.tar.zst",
                             "source_archive_sha256": "b" * 64,
                             "source_member": member,
                             "text_sha256": sha,
                             "text_path": PREFIX + "texts/" + sha + ".txt"})
        matrix.append({"binary": f"a{binary_index}.dll", "binary_sha256": "a" * 64,
                       "source_name": "sample", "source_version": "1.0",
                       "source_sha256": "b" * 64,
                       "package_declared_license": "spdx:MIT",
                       "license_evidence_path": " | ".join(members),
                       "license_evidence_sha256": " | ".join(shas)})
    index = {"source_p43_sha256": P43_SHA256,
             "source_matrix_sha256": "a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc",
             "binary_count": 34, "evidence_record_count": 61, "unique_text_count": 42,
             "review_status": "REVIEW_REQUIRED", "legal_clearance": False,
             "release_eligible": False, "evidence": evidence}
    return manifest, inventory, index, hashes, parent, matrix


class VerifyNativeNoticeTests(unittest.TestCase):
    def test_exact_non_release_lineage(self) -> None:
        check_lineage(*fixture())

    def test_release_flag_rejected(self) -> None:
        case = list(fixture())
        case[0]["release_eligible"] = True
        with self.assertRaisesRegex(ValueError, "non-release metadata differs"):
            check_lineage(*case)

    def test_missing_text_rejected(self) -> None:
        case = list(fixture())
        path = next(name for name in case[3] if name.startswith(PREFIX + "texts/"))
        del case[3][path]
        with self.assertRaisesRegex(ValueError, "payload lineage differs"):
            check_lineage(*case)


if __name__ == "__main__":
    unittest.main()
