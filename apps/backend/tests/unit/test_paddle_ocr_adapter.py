from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from plm_assistant.modules.parser.infrastructure.paddle_ocr import (
    OfflinePaddleOcr, OcrLine, PaddleOcrError, _model_fingerprint,
)
from plm_assistant.modules.parser.application.ocr_contract import OcrResultError


class _Engine:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result

    def predict(self, image: np.ndarray):
        assert image.shape == (100, 200, 3)
        return [self.result]


class PaddleOcrAdapterTests(unittest.TestCase):
    def test_explicit_offline_mode_and_complete_model_directories_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PaddleOcrError) as error:
                OfflinePaddleOcr(detection_model_dir=Path("C:/missing"),
                                 recognition_model_dir=Path("C:/missing"),
                                 expected_model_fingerprint="a" * 64)
        self.assertEqual(error.exception.code, "OCR_OFFLINE_MODE_REQUIRED")
        with patch.dict(os.environ, {"PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"}):
            with self.assertRaises(PaddleOcrError) as error:
                OfflinePaddleOcr(detection_model_dir=Path("C:/missing"),
                                 recognition_model_dir=Path("C:/missing"),
                                 expected_model_fingerprint="a" * 64)
        self.assertEqual(error.exception.code, "OCR_MODEL_UNAVAILABLE")

    def test_model_fingerprint_depends_on_file_bytes_not_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            det, rec = root / "det", root / "rec"
            det.mkdir()
            rec.mkdir()
            for folder in (det, rec):
                for name in ("config.json", "inference.json", "inference.pdiparams",
                             "inference.yml"):
                    (folder / name).write_bytes(name.encode())
            original = _model_fingerprint(det, rec)
            self.assertEqual(original, _model_fingerprint(det, rec))
            (rec / "inference.pdiparams").write_bytes(b"changed")
            self.assertNotEqual(original, _model_fingerprint(det, rec))
            with patch.dict(os.environ, {"PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True"}):
                with self.assertRaises(PaddleOcrError) as error:
                    OfflinePaddleOcr(detection_model_dir=det,
                                     recognition_model_dir=rec,
                                     expected_model_fingerprint=original)
            self.assertEqual(error.exception.code, "OCR_MODEL_INTEGRITY_MISMATCH")

    def test_image_bounds_and_result_coordinates(self) -> None:
        adapter = object.__new__(OfflinePaddleOcr)
        adapter._engine = _Engine({
            "rec_texts": [" SCOPE APPROVED "], "rec_scores": [0.95],
            "rec_polys": [np.array([[20, 10], [120, 10], [120, 40], [20, 40]])],
        })
        lines = adapter.recognize(np.zeros((100, 200, 3), dtype=np.uint8))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].text, "SCOPE APPROVED")
        self.assertEqual(lines[0].bbox, (0.1, 0.1, 0.6, 0.4))
        with self.assertRaises(PaddleOcrError) as error:
            adapter.recognize(np.zeros((100, 200), dtype=np.uint8))
        self.assertEqual(error.exception.code, "OCR_IMAGE_INVALID")
        adapter._engine = _Engine({"rec_texts": ["bad"], "rec_scores": [],
                                   "rec_polys": []})
        with self.assertRaises(PaddleOcrError) as error:
            adapter.recognize(np.zeros((100, 200, 3), dtype=np.uint8))
        self.assertEqual(error.exception.code, "OCR_RESULT_INVALID")

    def test_invalid_line_never_becomes_candidate(self) -> None:
        with self.assertRaises(OcrResultError):
            OcrLine("", 0.9, (0.1, 0.1, 0.9, 0.9))
        with self.assertRaises(OcrResultError):
            OcrLine("text", 1.2, (0.1, 0.1, 0.9, 0.9))
        with self.assertRaises(OcrResultError):
            OcrLine("text", 0.9, (0.8, 0.1, 0.2, 0.9))


if __name__ == "__main__":
    unittest.main()
