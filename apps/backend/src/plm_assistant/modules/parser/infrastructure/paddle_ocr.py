"""Offline PP-OCRv5 CPU adapter; never downloads models or writes source images."""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
from pathlib import Path

import numpy as np

from plm_assistant.modules.parser.application.ocr_contract import OcrLine, OcrResultError


_MODEL_FILES = ("config.json", "inference.json", "inference.pdiparams", "inference.yml")
_MAX_IMAGE_PIXELS = 20_000_000


class PaddleOcrError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OfflinePaddleOcr:
    def __init__(self, *, detection_model_dir: Path,
                 recognition_model_dir: Path,
                 expected_model_fingerprint: str) -> None:
        if os.environ.get("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK") != "True":
            raise PaddleOcrError("OCR_OFFLINE_MODE_REQUIRED")
        if (type(expected_model_fingerprint) is not str
                or len(expected_model_fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in expected_model_fingerprint)):
            raise PaddleOcrError("OCR_MODEL_FINGERPRINT_INVALID")
        det = _model_dir(detection_model_dir)
        rec = _model_dir(recognition_model_dir)
        # Paddle 3.3.1 on Windows fails to read inference.json beneath a
        # non-ASCII absolute path even when identical model bytes load from
        # an ASCII path. Do not enter the third-party predictor with that path.
        if sys.platform == "win32" and (not str(det).isascii() or not str(rec).isascii()):
            raise PaddleOcrError("OCR_MODEL_PATH_UNSUPPORTED")
        try:
            self.model_fingerprint = _model_fingerprint(det, rec)
        except OSError:
            raise PaddleOcrError("OCR_MODEL_UNAVAILABLE") from None
        if not hmac.compare_digest(self.model_fingerprint, expected_model_fingerprint):
            raise PaddleOcrError("OCR_MODEL_INTEGRITY_MISMATCH")
        try:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_detection_model_dir=str(det),
                text_recognition_model_name="PP-OCRv5_mobile_rec",
                text_recognition_model_dir=str(rec),
                use_doc_orientation_classify=False, use_doc_unwarping=False,
                use_textline_orientation=False, device="cpu", enable_mkldnn=False,
            )
        except Exception:
            raise PaddleOcrError("OCR_ENGINE_UNAVAILABLE") from None

    def recognize(self, image: np.ndarray) -> tuple[OcrLine, ...]:
        if (type(image) is not np.ndarray or image.dtype != np.uint8
                or image.ndim != 3 or image.shape[2] != 3
                or not 1 <= image.shape[0] * image.shape[1] <= _MAX_IMAGE_PIXELS):
            raise PaddleOcrError("OCR_IMAGE_INVALID")
        try:
            results = list(self._engine.predict(np.ascontiguousarray(image)))
            if len(results) != 1:
                raise PaddleOcrError("OCR_RESULT_INVALID")
            result = results[0]
            texts = result["rec_texts"]
            scores = result["rec_scores"]
            polys = result["rec_polys"]
            if not len(texts) == len(scores) == len(polys):
                raise PaddleOcrError("OCR_RESULT_INVALID")
            lines: list[OcrLine] = []
            height, width = image.shape[:2]
            for raw_text, raw_score, polygon in zip(texts, scores, polys):
                if type(raw_text) is not str:
                    raise PaddleOcrError("OCR_RESULT_INVALID")
                if not raw_text.strip():
                    continue
                points = np.asarray(polygon, dtype=float)
                if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
                    raise PaddleOcrError("OCR_RESULT_INVALID")
                if not np.isfinite(points).all():
                    raise PaddleOcrError("OCR_RESULT_INVALID")
                left = max(0.0, min(1.0, float(points[:, 0].min()) / width))
                top = max(0.0, min(1.0, float(points[:, 1].min()) / height))
                right = max(0.0, min(1.0, float(points[:, 0].max()) / width))
                bottom = max(0.0, min(1.0, float(points[:, 1].max()) / height))
                lines.append(OcrLine(raw_text.strip(), float(raw_score),
                                     (left, top, right, bottom)))
                if len(lines) > 100_000:
                    raise PaddleOcrError("OCR_RESULT_LIMIT_EXCEEDED")
            return tuple(lines)
        except OcrResultError:
            raise PaddleOcrError("OCR_RESULT_INVALID") from None
        except PaddleOcrError:
            raise
        except Exception:
            raise PaddleOcrError("OCR_ENGINE_FAILED") from None


def _model_dir(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or not value.is_dir():
        raise PaddleOcrError("OCR_MODEL_UNAVAILABLE")
    for name in _MODEL_FILES:
        if not (value / name).is_file():
            raise PaddleOcrError("OCR_MODEL_UNAVAILABLE")
    return value.resolve(strict=True)


def _model_fingerprint(det: Path, rec: Path) -> str:
    digest = hashlib.sha256()
    for role, directory in (("det", det), ("rec", rec)):
        digest.update(role.encode("ascii"))
        for name in _MODEL_FILES:
            digest.update(name.encode("ascii"))
            with (directory / name).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()
