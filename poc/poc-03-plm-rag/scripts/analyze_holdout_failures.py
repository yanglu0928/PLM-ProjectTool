from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.dataset import chunk_document  # noqa: E402
from poc03_rag.holdout_failure_analysis import (  # noqa: E402
    analyze_holdout_failures,
    sanitized_failure_analysis,
)


def _load_chunks(parsed_root: Path, project_id: str) -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    for corpus_dir in sorted(path for path in parsed_root.iterdir() if path.is_dir()):
        for path in sorted(corpus_dir.glob("*.parsed.json")):
            parsed_id = path.name.removesuffix(".parsed.json")
            document_id = f"{corpus_dir.name}-{parsed_id}"
            parsed = json.loads(path.read_text(encoding="utf-8"))
            for chunk in chunk_document(
                document_id,
                parsed,
                project_id,
                source_corpus=corpus_dir.name,
            ):
                chunk_id = str(chunk["chunk_id"])
                existing = chunks.get(chunk_id)
                if existing is not None and existing != chunk:
                    raise ValueError(f"conflicting duplicate ChunkId: {chunk_id}")
                chunks[chunk_id] = chunk
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze POC-03 holdout classification and citation failures locally."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--case-level-result", required=True, type=Path)
    parser.add_argument("--parsed-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sanitized-output", required=True, type=Path)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    case_level = json.loads(args.case_level_result.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    project_ids = {str(case["project_id"]) for case in cases}
    if len(project_ids) != 1:
        raise ValueError("analysis requires exactly one ProjectId")
    chunks_by_id = _load_chunks(args.parsed_root, next(iter(project_ids)))
    report = analyze_holdout_failures(
        cases,
        case_level.get("retrievals") or {},
        case_level.get("predictions") or {},
        chunks_by_id=chunks_by_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.sanitized_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.sanitized_output.write_text(
        json.dumps(sanitized_failure_analysis(report), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(sanitized_failure_analysis(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
