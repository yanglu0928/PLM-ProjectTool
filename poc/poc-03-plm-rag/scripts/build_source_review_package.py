from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.confirmation_prototype import (  # noqa: E402
    build_confirmation_tasks,
    build_evidence_navigator_html,
    build_sanitized_confirmation_report,
)
from poc03_rag.review_import import load_candidate_records  # noqa: E402


def _mapping(values: list[str], *, option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        label, separator, raw_path = value.partition("=")
        label = label.strip().upper()
        if not separator or not label or not raw_path.strip():
            raise ValueError(f"{option} expects LABEL=PATH, got: {value}")
        result[label] = Path(raw_path.strip())
    return result


def _review_rows(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": item["candidate_id"],
            "query": item.get("query", ""),
            "source_type": item.get("source_type", ""),
            "classification": item.get("classification", ""),
            "answer_terms": "；".join(item.get("answer_terms") or []),
            "confirmed_locator": "；".join(item.get("citation_locators") or []),
            "review_status": "PENDING",
            "reviewed_by": "",
            "reviewed_at": "",
            "review_note": "",
        }
        for item in suggestions
    ]


def _parsed_document(document_id: str, parsed_roots: dict[str, Path]) -> dict[str, Any]:
    source_corpus, separator, parsed_id = document_id.partition("-")
    if not separator or source_corpus not in parsed_roots:
        return {}
    path = parsed_roots[source_corpus] / f"{parsed_id}.parsed.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _find_original(source_root: Path | None, file_name: str) -> Path | None:
    if source_root is None or not source_root.is_dir() or not file_name:
        return None
    matches = [path for path in source_root.rglob(file_name) if path.is_file()]
    return matches[0] if len(matches) == 1 else None


def _original_url(path: Path | None, locators: list[str]) -> str:
    if path is None:
        return ""
    uri = path.resolve().as_uri()
    if path.suffix.lower() == ".pdf":
        for locator in locators:
            parts = locator.split("/")
            if len(parts) >= 3 and parts[0] == "pdf" and parts[1] == "pages":
                return f"{uri}#page={parts[2]}"
    return uri


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local four-source POC-03 human-review package."
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--suggestions", type=Path, required=True)
    parser.add_argument(
        "--parsed-source",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Repeatable parsed-corpus mapping.",
    )
    parser.add_argument(
        "--source-root",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Repeatable original-source mapping.",
    )
    parser.add_argument("--task-output", type=Path, required=True)
    parser.add_argument("--navigator-output", type=Path, required=True)
    parser.add_argument("--sanitized-report", type=Path, required=True)
    args = parser.parse_args()

    parsed_roots = _mapping(args.parsed_source, option="--parsed-source")
    source_roots = _mapping(args.source_root, option="--source-root")
    candidates = load_candidate_records(args.candidates)
    suggestions = json.loads(args.suggestions.read_text(encoding="utf-8"))
    if len(candidates) != len(suggestions):
        raise ValueError(
            f"candidate/suggestion count mismatch: {len(candidates)} != {len(suggestions)}"
        )

    review_rows = _review_rows(suggestions)
    tasks = build_confirmation_tasks(candidates, review_rows)
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    suggestion_by_id = {item["candidate_id"]: item for item in suggestions}
    for task in tasks:
        candidate = candidate_by_id[task["candidate_id"]]
        suggestion = suggestion_by_id[task["candidate_id"]]
        citation = (candidate.get("expected_citations") or [{}])[0]
        task["human_decision"] = ""
        task["current_status"] = "待确认"
        task["answer_terms"] = "；".join(suggestion.get("answer_terms") or [])
        task["confirmed_locator"] = "；".join(
            suggestion.get("citation_locators") or []
        )
        task["document_id"] = str(citation.get("document_id") or "")
        task["chunk_id"] = str(citation.get("chunk_id") or "")
        task["candidate_content_sha256"] = str(
            candidate.get("candidate_content_sha256") or ""
        )

    navigator_entries: list[dict[str, Any]] = []
    unresolved_original_count = 0
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        suggestion = suggestion_by_id[candidate_id]
        citation = (candidate.get("expected_citations") or [{}])[0]
        document_id = str(citation.get("document_id") or "")
        locators = list(citation.get("source_locators") or [])
        source_corpus = str(candidate.get("source_corpus") or "").upper()
        parsed = _parsed_document(document_id, parsed_roots)
        file_name = str((parsed.get("source") or {}).get("file_name") or "")
        original = _find_original(source_roots.get(source_corpus), file_name)
        unresolved_original_count += original is None
        navigator_entries.append(
            {
                "candidate_id": candidate_id,
                "query": suggestion.get("query", ""),
                "source_name": file_name,
                "document_id": document_id,
                "content": candidate.get("candidate_content", ""),
                "locators": locators,
                "original_url": _original_url(original, locators),
            }
        )

    args.task_output.parent.mkdir(parents=True, exist_ok=True)
    args.task_output.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.navigator_output.parent.mkdir(parents=True, exist_ok=True)
    args.navigator_output.write_text(
        build_evidence_navigator_html(navigator_entries),
        encoding="utf-8",
    )
    report = build_sanitized_confirmation_report(
        tasks,
        generated_at=datetime.now(UTC).isoformat(),
    )
    report["schema_version"] = "poc-03.source-review-package-result.v1"
    report["status"] = (
        "PASS_FOR_HUMAN_REVIEW"
        if tasks and unresolved_original_count == 0
        else "FAIL"
    )
    report["summary"]["unresolved_original_count"] = unresolved_original_count
    report["summary"]["pending_human_decision_count"] = sum(
        not item["human_decision"] for item in tasks
    )
    report["conclusion"] = (
        "The local four-source review package is ready; no candidate is approved until a human decision is recorded."
    )
    args.sanitized_report.parent.mkdir(parents=True, exist_ok=True)
    args.sanitized_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS_FOR_HUMAN_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
