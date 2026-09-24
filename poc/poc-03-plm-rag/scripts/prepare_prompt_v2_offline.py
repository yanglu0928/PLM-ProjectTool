from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.dataset import chunk_document  # noqa: E402
from poc03_rag.prompt_v2 import (  # noqa: E402
    FINAL_CLASSIFICATIONS,
    PROMPT_ID,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_case_payload,
    payload_contains_forbidden_keys,
    prediction_schema,
)
from poc03_rag.quality_evaluation import normalize_cjk_spacing  # noqa: E402


EXPECTED_PIPELINE_VERSION = "r5-protected-lexical-fusion-v1"


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _load_chunks(parsed_root: Path, project_id: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for corpus_dir in sorted(path for path in parsed_root.iterdir() if path.is_dir()):
        for path in sorted(corpus_dir.glob("*.parsed.json")):
            parsed = json.loads(path.read_text(encoding="utf-8"))
            chunks.extend(
                chunk_document(
                    f"{corpus_dir.name}-{path.name.removesuffix('.parsed.json')}",
                    parsed,
                    project_id,
                    source_corpus=corpus_dir.name,
                )
            )
    return chunks


def _document_id(chunk_id: str) -> str:
    return chunk_id.rsplit("-C-", 1)[0]


def prepare(
    *,
    dataset_path: Path,
    parsed_root: Path,
    retrieval_cache_path: Path,
    payload_output: Path,
    report_output: Path,
) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    if not 100 <= len(cases) <= 200:
        raise ValueError("Golden Dataset must contain 100 to 200 cases")
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("offline Prompt v2 preparation requires one ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    retrieval_rows = {
        str(row["case_id"]): row for row in _load_json_lines(retrieval_cache_path)
    }

    payloads: list[dict[str, Any]] = []
    exact_hits = same_document_hits = source_violations = 0
    context_counts: list[int] = []
    truncated_context_count = 0
    for case in cases:
        case_id = str(case["case_id"])
        row = retrieval_rows.get(case_id)
        if not row or row.get("pipeline_version") != EXPECTED_PIPELINE_VERSION:
            raise ValueError(f"missing current R5 retrieval result: {case_id}")
        ranked = [str(value) for value in row.get("top5_ids") or []]
        payload = build_case_payload(case, ranked, chunks_by_id)
        if payload_contains_forbidden_keys(payload):
            raise AssertionError("Golden Dataset labels leaked into Prompt v2 payload")
        payloads.append(payload)
        context_counts.append(len(payload["contexts"]))
        source_violations += sum(
            str(chunks_by_id[chunk_id]["source_corpus"]) != str(case["source_type"])
            for chunk_id in ranked
        )
        truncated_context_count += sum(
            len(
                normalize_cjk_spacing(
                    str(chunks_by_id[context["chunk_id"]]["text"])
                ).strip()
            )
            > len(context["text"])
            for context in payload["contexts"]
        )
        expected = {str(value) for value in case["expected_relevant_chunk_ids"]}
        exact_hits += bool(expected.intersection(ranked))
        expected_documents = {_document_id(value) for value in expected}
        same_document_hits += any(
            _document_id(chunk_id) in expected_documents for chunk_id in ranked
        )

    payload_output.parent.mkdir(parents=True, exist_ok=True)
    with payload_output.open("w", encoding="utf-8", newline="\n") as stream:
        for payload in payloads:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")

    label_distribution = Counter(
        str(case["expected_classification"]) for case in cases
    )
    checks = {
        "all_cases_prepared": len(payloads) == len(cases),
        "five_final_labels_only": set(label_distribution) == set(FINAL_CLASSIFICATIONS),
        "golden_fields_absent_from_payloads": not any(
            payload_contains_forbidden_keys(payload) for payload in payloads
        ),
        "source_type_isolation": source_violations == 0,
        "five_contexts_per_case": min(context_counts) == max(context_counts) == 5,
        "r5_exact_evidence_available_at_least_95_percent": exact_hits / len(cases)
        >= 0.95,
    }
    report = {
        "schema_version": "poc-03.prompt-v2-offline-audit.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "summary": {
            "case_count": len(cases),
            "payload_count": len(payloads),
            "context_count_min": min(context_counts),
            "context_count_max": max(context_counts),
            "exact_evidence_available_count": exact_hits,
            "exact_evidence_available_rate": exact_hits / len(cases),
            "same_document_evidence_available_count": same_document_hits,
            "same_document_evidence_available_rate": same_document_hits / len(cases),
            "source_type_violation_count": source_violations,
            "truncated_context_count": truncated_context_count,
        },
        "prompt": {
            "prompt_id": PROMPT_ID,
            "prompt_version": PROMPT_VERSION,
            "system_prompt_sha256": hashlib.sha256(
                SYSTEM_PROMPT.encode("utf-8")
            ).hexdigest(),
            "allowed_classifications": list(FINAL_CLASSIFICATIONS),
            "schema_sha256": hashlib.sha256(
                json.dumps(
                    prediction_schema(), sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
        },
        "checks": checks,
        "classification_accuracy": {
            "measured": False,
            "reason": "No external model call is permitted in the offline preparation step.",
            "threshold": 0.9,
        },
        "external_calls": {"embedding": 0, "reranker": 0, "deepseek": 0},
        "limitations": {
            "same_dataset_used_for_prompt_design": True,
            "independent_holdout_required": True,
            "live_deepseek_validation_required_for_p03_a12": True,
        },
        "privacy": {
            "payload_file_committed": False,
            "queries_committed": False,
            "chunk_ids_committed": False,
            "document_text_committed": False,
            "golden_labels_in_model_payload": False,
            "api_keys_committed": False,
        },
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and audit Prompt v2 offline payloads")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--retrieval-cache", type=Path, required=True)
    parser.add_argument("--payload-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(
        dataset_path=args.dataset,
        parsed_root=args.parsed_root,
        retrieval_cache_path=args.retrieval_cache,
        payload_output=args.payload_output,
        report_output=args.report_output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
