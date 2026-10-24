from __future__ import annotations

import locale
import os
from collections.abc import Iterable


def _candidate_encodings() -> Iterable[str]:
    yield "utf-8"
    preferred = locale.getpreferredencoding(False)
    if preferred:
        yield preferred
    if os.name == "nt":
        yield "mbcs"
    yield "gb18030"


def decode_tesseract_output(binary_output: bytes) -> str:
    """Decode Tesseract output without assuming UTF-8 on Windows."""
    attempted: set[str] = set()
    for encoding in _candidate_encodings():
        normalized = encoding.lower()
        if normalized in attempted:
            continue
        attempted.add(normalized)
        try:
            return binary_output.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return binary_output.decode("utf-8", errors="replace")


def parse_tesseract_output(binary_output: bytes) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in decode_tesseract_output(binary_output).splitlines():
        parts = line.strip().split(":", maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0].strip()] = parts[1].strip()
    return parsed


def install() -> bool:
    """Install the compatibility parser in OCRmyPDF on Windows."""
    if os.name != "nt":
        return False

    from ocrmypdf._exec import tesseract

    tesseract._parse_tesseract_output = parse_tesseract_output
    return True
