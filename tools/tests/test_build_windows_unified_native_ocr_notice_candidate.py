from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_native_ocr_notice_candidate import (  # noqa: E402
    source_texts_and_map, updated_metadata,
)


class NativeOcrNoticeCandidateTests(unittest.TestCase):
    def test_42_exact_texts_preserve_61_binary_attributions(self) -> None:
        matrix = [{"binary": f"a{index}.dll", "binary_sha256": "a" * 64,
                   "source_name": "sample", "source_version": "1.0",
                   "package_declared_license": "spdx:MIT",
                   "release_obligations_reviewed": "NO"} for index in range(34)]
        proof_rows = []
        for index in range(61):
            body = f"text {index % 42}".encode()
            proof_rows.append({"binary": f"a{index % 34}.dll", "evidence_kind": "PACKAGE_MEMBER",
                               "source_archive": "artifacts/sample.pkg.tar.zst",
                               "source_archive_sha256": "b" * 64,
                               "member_path": f"member/{index}",
                               "text_sha256": hashlib.sha256(body).hexdigest()})
        proof = {"verified_evidence_records": 61, "native_matrix_sha256": "c" * 64,
                 "rows": proof_rows}
        with patch("build_windows_unified_native_ocr_notice_candidate.read_tar_member",
                   side_effect=lambda _path, member: f"text {int(member.split('/')[-1]) % 42}".encode()):
            texts, body = source_texts_and_map(proof, matrix)
        index = json.loads(body)
        self.assertEqual(len(texts), 42)
        self.assertEqual(len(index["evidence"]), 61)
        self.assertEqual({item["binary"] for item in index["evidence"]},
                         {item["binary"] for item in matrix})
        self.assertFalse(index["release_eligible"])
        self.assertFalse(index["legal_clearance"])
        self.assertTrue(all(item["text_path"] in texts for item in index["evidence"]))

    def test_metadata_remains_non_release(self) -> None:
        manifest = {"payload_file_count": 21114, "release_eligible": False,
                    "legal_clearance": False, "installation_performed": False,
                    "service_registration_performed": False}
        inventory = {"review_status": "REVIEW_REQUIRED",
                     "ghostscript_source": {"review_status": "REVIEW_REQUIRED"}}
        new_manifest, new_inventory = updated_metadata(manifest, inventory, 21158, "d" * 64)
        self.assertEqual(json.loads(new_manifest)["payload_file_count"], 21158)
        self.assertFalse(json.loads(new_manifest)["release_eligible"])
        self.assertEqual(json.loads(new_inventory)["native_ocr_license_evidence"]["review_status"],
                         "REVIEW_REQUIRED")

    def test_release_flag_change_rejected(self) -> None:
        manifest = {"payload_file_count": 21114, "release_eligible": True,
                    "legal_clearance": False, "installation_performed": False,
                    "service_registration_performed": False}
        inventory = {"review_status": "REVIEW_REQUIRED",
                     "ghostscript_source": {"review_status": "REVIEW_REQUIRED"}}
        with self.assertRaisesRegex(ValueError, "boundary changed"):
            updated_metadata(manifest, inventory, 21158, "d" * 64)


if __name__ == "__main__":
    unittest.main()
