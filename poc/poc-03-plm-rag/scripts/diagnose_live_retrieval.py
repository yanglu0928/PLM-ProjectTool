from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from poc03_rag.layered_diagnostics import (  # noqa: E402
    build_layered_diagnostic,
    sanitized_layered_report,
)
from poc03_rag.quality_evaluation import lexical_terms, tsquery_or  # noqa: E402
from validate_live_quality_metrics import (  # noqa: E402
    FULL_TEXT_SQL,
    SCHEMA_NAME,
    VECTOR_SQL,
    _create_index,
    _load_chunks,
    _load_embedding_cache,
    _sha256,
    _vector_literal,
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose live retrieval stages without external model calls")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--retrieval-cache", type=Path, required=True)
    parser.add_argument("--prediction-cache", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--dimension", type=int, default=1024)
    args = parser.parse_args()

    dataset = load_json(args.dataset)
    cases = list(dataset.get("cases") or [])
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("diagnostic requires one non-empty ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(args.parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    cached = _load_embedding_cache(args.embedding_cache, args.dimension)
    required_texts = {
        **{str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks},
        **{f"QUERY:{case['case_id']}": str(case["query"]) for case in cases},
    }
    missing_or_changed = [
        item_id
        for item_id, text in required_texts.items()
        if item_id not in cached or cached[item_id][0] != _sha256(text)
    ]
    if missing_or_changed:
        raise ValueError(f"embedding cache is missing or stale for {len(missing_or_changed)} items")
    embeddings = {item_id: cached[item_id][1] for item_id in required_texts}
    reranked = {
        str(row["case_id"]): [str(item) for item in row["top5_ids"]]
        for row in load_json_lines(args.retrieval_cache)
    }
    predictions = {
        str(row["case_id"]): row for row in load_json_lines(args.prediction_cache)
    }
    if set(reranked) != {str(case["case_id"]) for case in cases}:
        raise ValueError("retrieval cache does not match the frozen dataset")

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
        connect_timeout=10,
    )
    vector_rankings: dict[str, list[str]] = {}
    full_text_rankings: dict[str, list[str]] = {}
    fusion_rankings: dict[str, list[str]] = {}
    try:
        _create_index(connection, chunks, embeddings, args.dimension)
        for case in cases:
            case_id = str(case["case_id"])
            parameters = {
                "project_id": project_id,
                "source_type": str(case["source_type"]),
                "query_vector": _vector_literal(embeddings[f"QUERY:{case_id}"]),
                "limit": 20,
            }
            with connection.cursor() as cursor:
                cursor.execute(VECTOR_SQL, parameters)
                vector_rows = cursor.fetchall()
                text_rows: list[tuple[Any, ...]] = []
                tsquery = tsquery_or(lexical_terms(str(case["query"])))
                if tsquery:
                    cursor.execute(
                        FULL_TEXT_SQL,
                        {
                            "project_id": project_id,
                            "source_type": str(case["source_type"]),
                            "tsquery": tsquery,
                            "limit": 20,
                        },
                    )
                    text_rows = cursor.fetchall()
            vector_scores = {str(row[0]): max(0.0, float(row[1])) for row in vector_rows}
            raw_text_scores = {str(row[0]): max(0.0, float(row[1])) for row in text_rows}
            max_text_score = max(raw_text_scores.values(), default=0.0)
            text_scores = {
                chunk_id: score / max_text_score if max_text_score else 0.0
                for chunk_id, score in raw_text_scores.items()
            }
            combined = {
                chunk_id: 0.6 * vector_scores.get(chunk_id, 0.0)
                + 0.4 * text_scores.get(chunk_id, 0.0)
                for chunk_id in set(vector_scores) | set(text_scores)
            }
            vector_rankings[case_id] = [str(row[0]) for row in vector_rows]
            full_text_rankings[case_id] = [str(row[0]) for row in text_rows]
            fusion_rankings[case_id] = sorted(
                combined, key=lambda chunk_id: (-combined[chunk_id], chunk_id)
            )[:20]

        report = build_layered_diagnostic(
            cases,
            vector_rankings=vector_rankings,
            full_text_rankings=full_text_rankings,
            fusion_rankings=fusion_rankings,
            reranked_rankings=reranked,
            predictions=predictions,
        )
        report["generated_at"] = datetime.now().astimezone().isoformat()
        report["configuration"] = {
            "vector_weight": 0.6,
            "full_text_weight": 0.4,
            "channel_limit": 20,
            "reranker_top_k": 5,
            "external_calls": 0,
            "embedding_cache_reused": True,
            "reranker_cache_reused": True,
            "prediction_cache_reused": True,
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "case-level-diagnostic.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        sanitized = sanitized_layered_report(report)
        (args.output_dir / "layered-retrieval-diagnostic.json").write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(sanitized, ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        finally:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
