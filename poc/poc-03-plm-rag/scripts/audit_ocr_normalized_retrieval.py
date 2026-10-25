from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from poc03_rag.quality_evaluation import rank_lexical_overlap  # noqa: E402
from validate_tuned_reranker import _load_chunks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit OCR-normalized lexical retrieval")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case-report", type=Path, required=True)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("audit requires one non-empty ProjectId")
    chunks = _load_chunks(args.parsed_root, next(iter(project_ids)))
    candidates_by_source: dict[str, dict[str, str]] = defaultdict(dict)
    for chunk in chunks:
        candidates_by_source[str(chunk["source_corpus"])][str(chunk["chunk_id"])] = str(
            chunk["text"]
        )

    top5_hits = top20_hits = 0
    misses_by_source: Counter[str] = Counter()
    miss_ranks: list[int] = []
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        source_type = str(case["source_type"])
        ranked = rank_lexical_overlap(
            str(case["query"]),
            candidates_by_source[source_type],
            limit=len(candidates_by_source[source_type]),
        )
        expected = {str(item) for item in case["expected_relevant_chunk_ids"]}
        top5_hit = bool(expected.intersection(ranked[:5]))
        top20_hit = bool(expected.intersection(ranked[:20]))
        top5_hits += top5_hit
        top20_hits += top20_hit
        if not top5_hit:
            misses_by_source[source_type] += 1
        target_ranks = [ranked.index(item) + 1 for item in expected if item in ranked]
        best_rank = min(target_ranks) if target_ranks else None
        if not top5_hit and best_rank is not None:
            miss_ranks.append(best_rank)
        case_rows.append(
            {
                "case_id": str(case["case_id"]),
                "top5_ids": ranked[:5],
                "top5_hit": top5_hit,
                "top20_hit": top20_hit,
                "best_expected_rank": best_rank,
            }
        )
    count = len(cases)
    report = {
        "schema_version": "poc-03.ocr-normalized-retrieval-audit.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "PASS" if count and top5_hits / count >= 0.95 else "FAIL",
        "summary": {
            "case_count": count,
            "top5_hits": top5_hits,
            "top5_recall": top5_hits / count if count else 0.0,
            "top20_hits": top20_hits,
            "top20_recall": top20_hits / count if count else 0.0,
            "top5_miss_count": count - top5_hits,
            "top5_miss_expected_ranks": sorted(miss_ranks),
            "top5_misses_by_source_type": dict(sorted(misses_by_source.items())),
        },
        "configuration": {
            "source_type_filter": True,
            "cjk_ocr_spacing_normalization": True,
            "term_features": "cjk_bigrams_trigrams_and_alphanumeric_tokens",
            "scoring": "binary_term_coverage_with_corpus_idf",
            "query_label_leakage": False,
            "expected_chunk_id_leakage": False,
        },
        "limitations": {
            "same_dataset_used_for_exploratory_tuning": True,
            "independent_holdout_required_before_production_claim": True,
            "citation_accuracy_ceiling_when_context_is_top5": top5_hits / count
            if count
            else 0.0,
        },
        "privacy": {
            "queries_in_report": False,
            "chunk_ids_in_report": False,
            "document_text_in_report": False,
            "source_names_in_report": False,
            "case_level_report_committed": False,
            "external_calls": 0,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.case_report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.case_report.write_text(
        json.dumps({"cases": case_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
