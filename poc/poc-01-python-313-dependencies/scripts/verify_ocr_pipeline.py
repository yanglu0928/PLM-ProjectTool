from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont


EXPECTED_TERMS = [
    "PLM项目实施辅助工具",
    "需求调研",
    "合同编号",
    "PLM-2026-001",
    "客户确认",
]


def find_tesseract() -> Path | None:
    configured = os.environ.get("TESSERACT_EXE")
    candidates = [
        Path(configured) if configured else None,
        Path(shutil.which("tesseract")) if shutil.which("tesseract") else None,
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def find_ghostscript() -> Path | None:
    configured = os.environ.get("GHOSTSCRIPT_EXE")
    candidates = [
        Path(configured) if configured else None,
        Path(shutil.which("gswin64c")) if shutil.which("gswin64c") else None,
        Path(shutil.which("gs")) if shutil.which("gs") else None,
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def find_font() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ]
    font = next((path for path in candidates if path.is_file()), None)
    if font is None:
        raise RuntimeError("No configured Chinese font was found")
    return font


def generate_scanned_pdf(path: Path) -> None:
    image = Image.new("RGB", (2480, 3508), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(find_font()), 104)
    body_font = ImageFont.truetype(str(find_font()), 82)
    draw.text((180, 260), EXPECTED_TERMS[0], font=title_font, fill="black")
    draw.text((180, 620), EXPECTED_TERMS[1], font=body_font, fill="black")
    draw.text((180, 900), f"{EXPECTED_TERMS[2]}：{EXPECTED_TERMS[3]}", font=body_font, fill="black")
    draw.text((180, 1180), EXPECTED_TERMS[4], font=body_font, fill="black")
    image.save(path, "PDF", resolution=300.0)


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as document:
        return "\n".join(page.get_text() for page in document)


def normalize(text: str) -> str:
    return "".join(text.split()).replace("：", ":")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-type", choices=("pdf", "pdfa-2"), default="pdf")
    parser.add_argument("--deskew", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    input_pdf = args.output_dir / "input-scanned.pdf"
    output_pdf = args.output_dir / "output-searchable.pdf"
    stderr_path = args.output_dir / "ocrmypdf-stderr.txt"
    result_path = args.output_dir / "result.json"

    output_pdf.unlink(missing_ok=True)

    tesseract = find_tesseract()
    if tesseract is None:
        raise RuntimeError("Tesseract executable was not found")
    ghostscript = find_ghostscript()
    if args.output_type == "pdfa-2" and ghostscript is None:
        raise RuntimeError("Ghostscript executable was not found")

    generate_scanned_pdf(input_pdf)
    env = os.environ.copy()
    executable_dirs = [tesseract.parent]
    if ghostscript:
        executable_dirs.append(ghostscript.parent)
    env["PATH"] = os.pathsep.join(
        [*(str(path) for path in executable_dirs), env.get("PATH", "")]
    )
    compat_dir = Path(__file__).parent / "compat"
    env["PYTHONPATH"] = os.pathsep.join([str(compat_dir), env.get("PYTHONPATH", "")])
    command = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "--language",
        "chi_sim+eng",
        "--output-type",
        args.output_type,
        "--optimize",
        "0",
        "--oversample",
        "400",
        "--tesseract-pagesegmode",
        "6",
    ]
    if args.deskew:
        command.append("--deskew")
    command.extend([str(input_pdf), str(output_pdf)])
    completed = subprocess.run(
        command,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    stderr_path.write_text(completed.stderr.rstrip() + "\n", encoding="utf-8")

    extracted = extract_text(output_pdf) if output_pdf.is_file() else ""
    normalized = normalize(extracted)
    matches = {term: normalize(term) in normalized for term in EXPECTED_TERMS}
    report = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
        },
        "python_version": platform.python_version(),
        "tesseract": {
            "path": tesseract.name,
            "languages": ["chi_sim", "eng"],
        },
        "ghostscript": {
            "path": ghostscript.name if ghostscript else None,
        },
        "output_type": args.output_type,
        "deskew": args.deskew,
        "pdfa_validated": (
            "Output file is a PDF/A-2b (as expected)" in completed.stderr
            if args.output_type == "pdfa-2"
            else None
        ),
        "ocrmypdf_exit_code": completed.returncode,
        "input_size_bytes": input_pdf.stat().st_size,
        "output_size_bytes": output_pdf.stat().st_size if output_pdf.is_file() else 0,
        "expected_terms": matches,
        "term_recall": sum(matches.values()) / len(matches),
        "extracted_text": extracted.strip(),
    }
    report["status"] = (
        "PASS"
        if completed.returncode == 0
        and output_pdf.is_file()
        and report["term_recall"] == 1.0
        and (args.output_type != "pdfa-2" or report["pdfa_validated"] is True)
        else "FAIL"
    )
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
