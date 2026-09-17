from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from importlib import metadata
from pathlib import Path


PACKAGES = [
    "fastapi",
    "uvicorn",
    "SQLAlchemy",
    "alembic",
    "psycopg",
    "pgvector",
    "PyMuPDF",
    "pdfplumber",
    "python-docx",
    "python-pptx",
    "openpyxl",
    "paddleocr",
    "paddlepaddle",
    "pytesseract",
    "ocrmypdf",
]


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def executable_available(name: str) -> bool:
    scripts_dir = Path(sys.executable).parent
    candidates = (name, f"{name}.exe") if platform.system() == "Windows" else (name,)
    standard_paths: tuple[Path, ...] = ()
    if platform.system() == "Windows":
        if name == "tesseract":
            standard_paths = (Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),)
        elif name == "gswin64c":
            standard_paths = tuple(Path("C:/Program Files/gs").glob("gs*/bin/gswin64c.exe"))
    return (
        bool(shutil.which(name))
        or any((scripts_dir / candidate).is_file() for candidate in candidates)
        or any(path.is_file() for path in standard_paths)
    )


def main() -> int:
    report = {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "architecture": platform.machine(),
            "executable_name": os.path.basename(sys.executable),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
        },
        "executables": {
            name: executable_available(name)
            for name in ("tesseract", "gs", "gswin64c", "ocrmypdf")
        },
        "packages": {name: package_version(name) for name in PACKAGES},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
