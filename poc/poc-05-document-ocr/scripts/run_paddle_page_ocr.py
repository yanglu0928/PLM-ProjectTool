from __future__ import annotations

import argparse
import sys
from pathlib import Path

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc05_parser.parser import _extract_paddle_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local PaddleOCR over rendered PNG pages.")
    parser.add_argument("--input-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--detection-model", required=True, type=Path)
    parser.add_argument("--recognition-model", required=True, type=Path)
    args = parser.parse_args()

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_detection_model_dir=str(args.detection_model),
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        text_recognition_model_dir=str(args.recognition_model),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
        enable_mkldnn=False,
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    processed = 0
    for image_path in sorted(args.input_directory.glob("*.png")):
        records = _extract_paddle_records(ocr.predict(str(image_path)))
        text = "\n".join(record[0] for record in records)
        (args.output_directory / f"{image_path.stem}.txt").write_text(
            text + "\n", encoding="utf-8"
        )
        processed += 1
    print(f"processed_pages={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
