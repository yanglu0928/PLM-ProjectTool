from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.dataset import (  # noqa: E402
    build_candidate_records,
    build_sanitized_report,
    chunk_document,
    write_json_lines,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local, human-review-only POC-03 candidate dataset."
    )
    parser.add_argument(
        "--parsed-source",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Repeatable parsed corpus source; LABEL is used only in redacted identifiers.",
    )
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--sanitized-report", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--target-count", type=int, default=120)
    parser.add_argument("--max-chars", type=int, default=900)
    args = parser.parse_args()

    documents: list[dict] = []
    chunks: list[dict] = []
    for source in args.parsed_source:
        if "=" not in source:
            raise ValueError("--parsed-source must use LABEL=PATH")
        label, raw_path = source.split("=", 1)
        label = label.strip().upper()
        if not label or not label.replace("-", "").isalnum():
            raise ValueError(f"Invalid parsed source label: {label!r}")
        parsed_dir = Path(raw_path).resolve()
        if not parsed_dir.is_dir():
            raise FileNotFoundError(parsed_dir)
        parsed_files = sorted(parsed_dir.glob("SL-*.parsed.json"), key=lambda path: path.name)
        if not parsed_files:
            raise ValueError(f"No parsed POC-05 documents found in {parsed_dir}")
        for path in parsed_files:
            document = json.loads(path.read_text(encoding="utf-8"))
            document_id = f"{label}-{path.name.split('.', 1)[0]}"
            documents.append(document)
            chunks.extend(
                chunk_document(
                    document_id,
                    document,
                    args.project_id,
                    source_corpus=label,
                    max_chars=args.max_chars,
                )
            )

    candidates = build_candidate_records(chunks, target_count=args.target_count)
    args.local_output.parent.mkdir(parents=True, exist_ok=True)
    write_json_lines(args.local_output, candidates)

    generated_at = datetime.now(UTC).isoformat()
    report = build_sanitized_report(
        documents=documents,
        chunks=chunks,
        candidates=candidates,
        target_count=args.target_count,
        local_output_location="git-ignored artifacts/poc-03/candidate-dataset/",
        generated_at=generated_at,
    )
    args.sanitized_report.parent.mkdir(parents=True, exist_ok=True)
    args.sanitized_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
