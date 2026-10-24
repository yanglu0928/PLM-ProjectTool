from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src" / "poc05_parser"))

from semantic_audit import evaluate_annotation, evaluate_text_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate visually transcribed checkpoints against parsed OCR output."
    )
    parser.add_argument("--annotation", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--parsed-directory", type=Path)
    source.add_argument("--text-directory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    annotation = json.loads(args.annotation.read_text(encoding="utf-8"))
    if args.text_directory is not None:
        result = evaluate_text_directory(annotation, args.text_directory)
    else:
        result = evaluate_annotation(annotation, args.parsed_directory)
    result["generated_at"] = datetime.now().astimezone().isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
