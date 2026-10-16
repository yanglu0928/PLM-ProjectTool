from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("ocr_input_audit", TOOLS / "audit_windows_ocr_offline_inputs.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OcrInputAuditTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path, dict]:
        candidate = root / "candidate.zip"
        with zipfile.ZipFile(candidate, "w") as archive:
            archive.writestr("payload/runtime/python.exe", b"synthetic")
        gs = root / "gs10080w64.exe"
        gs.write_bytes(b"gs")
        ocr = root / "ocrmypdf-17.12.1-py3-none-any.whl"
        ocr.write_bytes(b"ocr")
        tesseract = root / "tesseract.exe"
        tesseract.write_bytes(b"tesseract")
        tessdata = root / "tessdata"
        tessdata.mkdir()
        expected = {}
        for name in MODULE.TESSDATA_HASHES:
            data = name.encode()
            (tessdata / name).write_bytes(data)
            expected[name] = MODULE.digest_file(tessdata / name)
        det, rec = root / "det", root / "rec"
        for directory in (det, rec):
            directory.mkdir()
            for name in MODULE.MODEL_FILES:
                (directory / name).write_bytes((directory.name + name).encode())
            (directory / "README.md").write_text("---\nlicense: apache-2.0\n---\n", encoding="utf-8")
        return candidate, gs, ocr, tessdata, det, rec, tesseract, expected

    def test_exact_inputs_do_not_clear_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            args = self._fixture(Path(temp))
            candidate, gs, ocr, tessdata, det, rec, tesseract, expected = args
            with patch.object(MODULE, "inspect_archive", return_value=({"release_eligible": False}, {}, {})), \
                 patch.object(MODULE, "GHOSTSCRIPT_SHA256", MODULE.digest_file(gs)), \
                 patch.object(MODULE, "OCRMYPDF_SHA256", MODULE.digest_file(ocr)), \
                 patch.object(MODULE, "TESSDATA_HASHES", expected), \
                 patch.object(MODULE, "MODEL_FINGERPRINT", MODULE.model_fingerprint(det, rec)), \
                 patch.object(MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "tesseract v5.4.0.20240606\n", "")):
                result = MODULE.audit_ocr(*args[:7])
            self.assertEqual(result["status"], "INPUT_BYTES_VERIFIED_DEPLOYMENT_INCOMPLETE")
            self.assertFalse(result["release_eligible"])
            self.assertFalse(any(result["candidate_presence"].values()))

    def test_model_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, gs, ocr, tessdata, det, rec, tesseract, expected = self._fixture(Path(temp))
            fingerprint = MODULE.model_fingerprint(det, rec)
            (det / "inference.json").write_bytes(b"tampered")
            with patch.object(MODULE, "inspect_archive", return_value=({"release_eligible": False}, {}, {})), \
                 patch.object(MODULE, "GHOSTSCRIPT_SHA256", MODULE.digest_file(gs)), \
                 patch.object(MODULE, "OCRMYPDF_SHA256", MODULE.digest_file(ocr)), \
                 patch.object(MODULE, "TESSDATA_HASHES", expected), \
                 patch.object(MODULE, "MODEL_FINGERPRINT", fingerprint), \
                 self.assertRaisesRegex(ValueError, "Paddle model fingerprint mismatch"):
                MODULE.audit_ocr(candidate, gs, ocr, tessdata, det, rec, tesseract)


if __name__ == "__main__":
    unittest.main()
