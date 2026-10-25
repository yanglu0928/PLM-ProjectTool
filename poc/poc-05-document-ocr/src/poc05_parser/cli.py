from __future__ import annotations

import argparse
import json
from pathlib import Path

from .parser import parse_document


def main() -> int:
    parser = argparse.ArgumentParser(description="POC-05 unified document parser")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr-engine", choices=("paddle", "tesseract"))
    args = parser.parse_args()

    parsed = parse_document(args.input, ocr_engine=args.ocr_engine)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
