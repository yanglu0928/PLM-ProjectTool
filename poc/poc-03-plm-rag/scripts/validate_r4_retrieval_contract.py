from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from validate_live_quality_metrics import (  # noqa: E402
    RETRIEVAL_PIPELINE_VERSION,
    SCHEMA_NAME,
    _create_index,
    _hybrid_candidates,
    _load_chunks,
    _load_embedding_cache,
    _sha256,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the R4 source-filtered three-channel retrieval contract"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case-report", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--dimension", type=int, default=1024)
    args = parser.parse_args()

    dataset = _load_json(args.dataset)
    cases = list(dataset.get("cases") or [])
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("retrieval contract requires one non-empty ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(args.parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    chunks_by_source: dict[str, dict[str, str]] = {}
    for chunk in chunks:
        source_type = str(chunk["source_corpus"])
        chunks_by_source.setdefault(source_type, {})[str(chunk["chunk_id"])] = str(
            chunk["text"]
        )

    cached = _load_embedding_cache(args.embedding_cache, args.dimension)
    required_texts = {
        **{str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks},
        **{f"QUERY:{case['case_id']}": str(case["query"]) for case in cases},
    }
    stale = [
        item_id
        for item_id, value in required_texts.items()
        if item_id not in cached or cached[item_id][0] != _sha256(value)
    ]
    if stale:
        raise ValueError(f"embedding cache is missing or stale for {len(stale)} items")
    embeddings = {item_id: cached[item_id][1] for item_id in required_texts}

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
        connect_timeout=10,
    )
    exact_hits = same_document_hits = source_violations = 0
    gin_used = hnsw_used = False
    candidate_counts: list[int] = []
    misses_by_source: Counter[str] = Counter()
    case_rows: list[dict[str, Any]] = []
    try:
        database_version, pgvector_version = _create_index(
            connection, chunks, embeddings, args.dimension
        )
        for case in cases:
            case_id = str(case["case_id"])
            source_type = str(case["source_type"])
            candidates, used_gin, used_hnsw = _hybrid_candidates(
                connection,
                project_id=project_id,
                source_type=source_type,
                query=str(case["query"]),
                query_vector=embeddings[f"QUERY:{case_id}"],
                lexical_corpus=chunks_by_source[source_type],
            )
            gin_used = gin_used or used_gin
            hnsw_used = hnsw_used or used_hnsw
            candidate_counts.append(len(candidates))
            expected = {str(value) for value in case["expected_relevant_chunk_ids"]}
            exact_hit = bool(expected.intersection(candidates))
            expected_documents = {value.rsplit("-C-", 1)[0] for value in expected}
            same_document_hit = any(
                value.rsplit("-C-", 1)[0] in expected_documents for value in candidates
            )
            violations = sum(
                str(chunks_by_id[value]["source_corpus"]) != source_type
                for value in candidates
            )
            exact_hits += exact_hit
            same_document_hits += same_document_hit
            source_violations += violations
            if not exact_hit:
                misses_by_source[source_type] += 1
            case_rows.append(
                {
                    "case_id": case_id,
                    "candidate_ids": candidates,
                    "candidate_count": len(candidates),
                    "exact_pool_hit": exact_hit,
                    "same_document_pool_hit": same_document_hit,
                    "source_type_violation_count": violations,
                }
            )
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        finally:
            connection.close()

    count = len(cases)
    exact_recall = exact_hits / count if count else 0.0
    passed = (
        count >= 100
        and exact_recall >= 0.95
        and source_violations == 0
        and gin_used
        and hnsw_used
    )
    report = {
        "schema_version": "poc-03.r4-retrieval-contract-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "PASS" if passed else "FAIL",
        "summary": {
            "case_count": count,
            "exact_candidate_pool_hits": exact_hits,
            "exact_candidate_pool_recall": exact_recall,
            "same_document_candidate_pool_hits": same_document_hits,
            "same_document_candidate_pool_recall": same_document_hits / count
            if count
            else 0.0,
            "source_type_violation_count": source_violations,
            "minimum_candidate_count": min(candidate_counts, default=0),
            "maximum_candidate_count": max(candidate_counts, default=0),
            "average_candidate_count": sum(candidate_counts) / count if count else 0.0,
            "misses_by_source_type": dict(sorted(misses_by_source.items())),
        },
        "checks": {
            "candidate_pool_recall_at_least_95_percent": exact_recall >= 0.95,
            "source_type_isolation": source_violations == 0,
            "gin_index_used": gin_used,
            "hnsw_index_used": hnsw_used,
        },
        "configuration": {
            "retrieval_pipeline_version": RETRIEVAL_PIPELINE_VERSION,
            "source_type_filter": True,
            "cjk_ocr_spacing_normalization": True,
            "candidate_channels": ["vector", "full_text", "lexical_idf"],
            "channel_limit": 20,
            "vector_weight": 0.6,
            "full_text_weight": 0.4,
            "external_calls": 0,
            "embedding_cache_reused": True,
        },
        "environment": {
            "postgresql_version": database_version,
            "pgvector_version": pgvector_version,
            "platform": "Windows 11 x86-64",
        },
        "limitations": {
            "candidate_pool_is_not_reranked_top5": True,
            "same_dataset_used_for_exploratory_tuning": True,
            "independent_holdout_required_before_production_claim": True,
        },
        "privacy": {
            "queries_in_report": False,
            "chunk_ids_in_report": False,
            "document_text_in_report": False,
            "case_level_report_committed": False,
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
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
