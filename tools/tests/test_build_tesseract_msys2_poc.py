from __future__ import annotations

import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_tesseract_msys2_poc as candidate


class FixedPackageInputTests(unittest.TestCase):
    def test_fixed_archive_hash_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            name, version = candidate.TESSERACT_PACKAGE
            root = base / f"msys2-candidate-tesseract-ocr-{version}" / "extracted"
            root.mkdir(parents=True)
            (root / ".PKGINFO").write_text(
                f"pkgname = {name}\npkgver = {version}\n", encoding="utf-8"
            )
            archive = base / f"msys2-candidate-tesseract-ocr-{version}-any.pkg.tar.zst"
            archive.write_bytes(b"fixed archive")
            expected_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            matrix = base / "matrix.csv"
            with matrix.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=(
                    "package", "package_version", "archive_sha256"
                ))
                writer.writeheader()
            with patch.dict(candidate.EXTRA_ARCHIVE_HASHES,
                            {(name, version): expected_hash}, clear=True):
                result = candidate.audit_inputs(matrix, base)
                self.assertEqual(result[(name, version)]["archive_sha256"], expected_hash)
                archive.write_bytes(b"tampered archive")
                with self.assertRaisesRegex(ValueError, "Package archive hash differs"):
                    candidate.audit_inputs(matrix, base)

    def test_existing_output_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Output must be a new path"):
                candidate.build(Path("unused.csv"), Path("unused"), Path("unused"), output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
