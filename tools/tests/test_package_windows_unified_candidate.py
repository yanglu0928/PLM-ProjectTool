from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
import hashlib
import json
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_windows_unified_candidate import safe_name, select_entries, zip_members  # noqa: E402
from verify_windows_unified_extract import verify  # noqa: E402


class UnifiedCandidateTests(unittest.TestCase):
    def test_unsafe_paths_and_case_collision_rejected(self) -> None:
        for name in ("../secret", "C:/secret", "/absolute", "a\\b", "a//b", "a/./b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "duplicate.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("payload/a", b"a")
                output.writestr("PAYLOAD/A", b"b")
            with zipfile.ZipFile(archive) as source, self.assertRaisesRegex(ValueError, "duplicate"):
                zip_members(source)

    def test_old_tesseract_is_not_selected(self) -> None:
        base = {"payload/frontend/dist/index.html", "payload/config/bootstrap.example.yaml"}
        base |= {f"payload/frontend/dist/f{i}" for i in range(2)}
        native = {f"payload/ocr/ghostscript/file{i}" for i in range(654)}
        native |= {f"payload/ocr/tesseract/tessdata/file{i}" for i in range(41)}
        native |= {"payload/ocr/tesseract/tesseract.exe", "payload/ocr/tesseract/libjbig-0.dll"}
        models = {f"models/file{i}" for i in range(10)}
        selected_base, selected_native, selected_models = select_entries(base, native, models)
        self.assertEqual((len(selected_base), len(selected_native), len(selected_models)), (4, 695, 10))
        self.assertNotIn("payload/ocr/tesseract/tesseract.exe", selected_native)
        self.assertNotIn("payload/ocr/tesseract/libjbig-0.dll", selected_native)
        self.assertTrue(all(target.startswith("payload/ocr/models/") for target in selected_models.values()))

    def test_changed_source_count_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "counts changed"):
            select_entries(set(), set(), set())

    def test_clean_extract_verifier_rejects_tamper_and_extra(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "payload").mkdir()
            payload = root / "payload" / "data.txt"
            payload.write_bytes(b"synthetic")
            digest = hashlib.sha256(b"synthetic").hexdigest()
            (root / "payload-sha256sums.txt").write_text(f"{digest}  payload/data.txt\n", encoding="ascii")
            (root / "manifest.json").write_text(json.dumps({
                "kind": "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE",
                "release_eligible": False, "payload_file_count": 1,
            }))
            (root / "third-party-inventory.json").write_text("{}")
            self.assertEqual(verify(root)["status"], "CLEAN_EXTRACT_HASH_PASS")
            payload.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify(root)
            payload.write_bytes(b"synthetic")
            (root / "extra.txt").write_text("extra")
            with self.assertRaisesRegex(ValueError, "file set differs"):
                verify(root)


if __name__ == "__main__":
    unittest.main()
