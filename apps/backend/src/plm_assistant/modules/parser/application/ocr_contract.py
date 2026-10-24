"""Parser-owned OCR output contract; engines are replaceable adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


class OcrResultError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str = field(repr=False)
    confidence: float
    bbox: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if (type(self.text) is not str or not self.text.strip()
                or type(self.confidence) not in (int, float)
                or not math.isfinite(self.confidence)
                or not 0 <= self.confidence <= 1
                or type(self.bbox) is not tuple or len(self.bbox) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or not 0 <= value <= 1
                       for value in self.bbox)
                or self.bbox[0] >= self.bbox[2]
                or self.bbox[1] >= self.bbox[3]):
            raise OcrResultError("OCR_RESULT_INVALID")


class OcrEnginePort(Protocol):
    model_fingerprint: str

    def recognize(self, image: np.ndarray) -> tuple[OcrLine, ...]: ...
