from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_native_license_source_bytes import read_tar_member, split_evidence  # noqa: E402


class NativeLicenseSourceByteTests(unittest.TestCase):
    def test_evidence_pairing_rejects_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "pairing differs"):
            split_evidence({"license_evidence_path": "../LICENSE",
                            "license_evidence_sha256": "0" * 64})

    def test_evidence_pairing_rejects_cardinality_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "pairing differs"):
            split_evidence({"license_evidence_path": "A | B",
                            "license_evidence_sha256": "0" * 64})

    def test_gzip_source_member_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.tar.gz"
            body = b"license\r\ntext\n"
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo("project/LICENSE")
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
            self.assertEqual(read_tar_member(path, "project/LICENSE"), body)
            self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(
                read_tar_member(path, "project/LICENSE")).hexdigest())

    def test_unsafe_tar_member_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe"):
            read_tar_member(Path("unused.tar.gz"), "../LICENSE")


if __name__ == "__main__":
    unittest.main()
