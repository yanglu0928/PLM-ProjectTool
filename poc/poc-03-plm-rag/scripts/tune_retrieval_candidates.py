from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from poc03_rag.layered_diagnostics import fuse_ranked_scores  # noqa: E402
from poc03_rag.quality_evaluation import lexical_terms, tsquery_or  # noqa: E402
from validate_live_quality_metrics import (  # noqa: E402
    SCHEMA_NAME,
    _create_index,
    _load_chunks,
    _load_embedding_cache,
    _sha256,
    _vector_literal,
)


VECTOR_TEMPLATE = """
SELECT chunk_id, 1 - (embedding <=> %(query_vector)s::vector) AS score
FROM {schema}.retrieval_chunk
WHERE scope = 'PROJECT' AND project_id = %(project_id)s {source_filter}
ORDER BY embedding <=> %(query_vector)s::vector, chunk_id
LIMIT %(limit)s
""".strip()

TEXT_TEMPLATE = """
SELECT chunk_id,
       ts_rank_cd(to_tsvector('simple', search_body), to_tsquery('simple', %(tsquery)s)) AS score
FROM {schema}.retrieval_chunk
WHERE scope = 'PROJECT' AND project_id = %(project_id)s {source_filter}
  AND to_tsvector('simple', search_body) @@ to_tsquery('simple', %(tsquery)s)
ORDER BY score DESC, chunk_id
LIMIT %(limit)s
""".strip()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline candidate retrieval parameter sweep")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--dimension", type=int, default=1024)
    args = parser.parse_args()

    dataset = load_json(args.dataset)
    cases = list(dataset.get("cases") or [])
    project_id = str(cases[0]["project_id"])
    if any(str(case.get("project_id") or "") != project_id for case in cases):
        raise ValueError("tuning requires one ProjectId")
    chunks = _load_chunks(args.parsed_root, project_id)
    cached = _load_embedding_cache(args.embedding_cache, args.dimension)
    required_texts = {
        **{str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks},
        **{f"QUERY:{case['case_id']}": str(case["query"]) for case in cases},
    }
    if any(
        item_id not in cached or cached[item_id][0] != _sha256(text)
        for item_id, text in required_texts.items()
    ):
        raise ValueError("embedding cache is incomplete or stale")
    embeddings = {item_id: cached[item_id][1] for item_id in required_texts}
    document_chunks: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        document_chunks[str(chunk["document_id"])].append(str(chunk["chunk_id"]))
    chunk_position = {
        chunk_id: (document_id, index)
        for document_id, chunk_ids in document_chunks.items()
        for index, chunk_id in enumerate(chunk_ids)
    }

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
        connect_timeout=10,
    )
    limits = [20, 50, 100]
    weights = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    modes = ["normalized_score", "rrf"]
    configs: dict[tuple[bool, int, str, float], dict[str, Any]] = {
        (source_filter, limit, mode, weight): {
            "source_type_filter": source_filter,
            "channel_limit": limit,
            "fusion_mode": mode,
            "vector_weight": weight,
            "full_text_weight": 1.0 - weight,
            "top5_hits": 0,
            "top20_hits": 0,
        }
        for source_filter in (False, True)
        for limit in limits
        for mode in modes
        for weight in weights
    }
    candidate_pools: dict[tuple[bool, int], dict[str, Any]] = {
        (source_filter, limit): {
            "source_type_filter": source_filter,
            "channel_limit": limit,
            "exact_pool_hits": 0,
            "same_document_pool_hits": 0,
        }
        for source_filter in (False, True)
        for limit in limits
    }
    neighbor_pools: dict[tuple[bool, int, int], dict[str, Any]] = {
        (source_filter, limit, radius): {
            "source_type_filter": source_filter,
            "channel_limit": limit,
            "neighbor_radius": radius,
            "exact_pool_hits": 0,
            "expanded_candidate_total": 0,
        }
        for source_filter in (False, True)
        for limit in limits
        for radius in (1, 2, 3, 5)
    }
    expanded_fusions: dict[tuple[bool, int, str, float, int, int], dict[str, Any]] = {
        (source_filter, limit, mode, weight, fused_limit, radius): {
            "source_type_filter": source_filter,
            "channel_limit": limit,
            "fusion_mode": mode,
            "vector_weight": weight,
            "full_text_weight": 1.0 - weight,
            "fused_candidate_limit": fused_limit,
            "neighbor_radius": radius,
            "exact_pool_hits": 0,
            "expanded_candidate_total": 0,
        }
        for source_filter in (False, True)
        for limit in limits
        for mode in modes
        for weight in weights
        for fused_limit in (20, 50, 100)
        for radius in (1, 2, 3)
    }
    try:
        _create_index(connection, chunks, embeddings, args.dimension)
        for case in cases:
            case_id = str(case["case_id"])
            expected = {str(item) for item in case["expected_relevant_chunk_ids"]}
            for source_filter in (False, True):
                clause = "AND source_corpus = %(source_type)s" if source_filter else ""
                common = {
                    "project_id": project_id,
                    "source_type": str(case["source_type"]),
                    "limit": max(limits),
                }
                with connection.cursor() as cursor:
                    cursor.execute(
                        VECTOR_TEMPLATE.format(schema=SCHEMA_NAME, source_filter=clause),
                        {**common, "query_vector": _vector_literal(embeddings[f"QUERY:{case_id}"])},
                    )
                    vector_rows = [(str(item), float(score)) for item, score in cursor.fetchall()]
                    text_rows: list[tuple[str, float]] = []
                    tsquery = tsquery_or(lexical_terms(str(case["query"])))
                    if tsquery:
                        cursor.execute(
                            TEXT_TEMPLATE.format(schema=SCHEMA_NAME, source_filter=clause),
                            {**common, "tsquery": tsquery},
                        )
                        text_rows = [(str(item), float(score)) for item, score in cursor.fetchall()]
                for limit in limits:
                    pool = {item for item, _ in vector_rows[:limit]} | {
                        item for item, _ in text_rows[:limit]
                    }
                    expected_documents = {
                        item.split("-C-", 1)[0] for item in expected
                    }
                    pool_config = candidate_pools[(source_filter, limit)]
                    pool_config["exact_pool_hits"] += bool(expected.intersection(pool))
                    pool_config["same_document_pool_hits"] += any(
                        item.split("-C-", 1)[0] in expected_documents for item in pool
                    )
                    for radius in (1, 2, 3, 5):
                        expanded = set(pool)
                        for item in pool:
                            position = chunk_position.get(item)
                            if position is None:
                                continue
                            document_id, index = position
                            siblings = document_chunks[document_id]
                            expanded.update(
                                siblings[max(0, index - radius) : index + radius + 1]
                            )
                        neighbor_config = neighbor_pools[(source_filter, limit, radius)]
                        neighbor_config["exact_pool_hits"] += bool(
                            expected.intersection(expanded)
                        )
                        neighbor_config["expanded_candidate_total"] += len(expanded)
                    for mode in modes:
                        for weight in weights:
                            ranked = fuse_ranked_scores(
                                vector_rows[:limit],
                                text_rows[:limit],
                                vector_weight=weight,
                                mode=mode,
                            )
                            config = configs[(source_filter, limit, mode, weight)]
                            config["top5_hits"] += bool(expected.intersection(ranked[:5]))
                            config["top20_hits"] += bool(expected.intersection(ranked[:20]))
                            for fused_limit in (20, 50, 100):
                                for radius in (1, 2, 3):
                                    expanded = set(ranked[:fused_limit])
                                    for item in ranked[:fused_limit]:
                                        position = chunk_position.get(item)
                                        if position is None:
                                            continue
                                        document_id, index = position
                                        siblings = document_chunks[document_id]
                                        expanded.update(
                                            siblings[
                                                max(0, index - radius) : index + radius + 1
                                            ]
                                        )
                                    expanded_config = expanded_fusions[
                                        (
                                            source_filter,
                                            limit,
                                            mode,
                                            weight,
                                            fused_limit,
                                            radius,
                                        )
                                    ]
                                    expanded_config["exact_pool_hits"] += bool(
                                        expected.intersection(expanded)
                                    )
                                    expanded_config["expanded_candidate_total"] += len(
                                        expanded
                                    )
        rows = []
        for config in configs.values():
            config["top5_recall"] = config["top5_hits"] / len(cases)
            config["top20_recall"] = config["top20_hits"] / len(cases)
            rows.append(config)
        rows.sort(
            key=lambda item: (
                -item["top20_hits"],
                -item["top5_hits"],
                item["channel_limit"],
                item["fusion_mode"],
                item["vector_weight"],
            )
        )
        pool_rows = []
        for pool_config in candidate_pools.values():
            pool_config["exact_pool_recall"] = pool_config["exact_pool_hits"] / len(cases)
            pool_config["same_document_pool_recall"] = (
                pool_config["same_document_pool_hits"] / len(cases)
            )
            pool_rows.append(pool_config)
        pool_rows.sort(
            key=lambda item: (
                -item["exact_pool_hits"],
                item["channel_limit"],
                not item["source_type_filter"],
            )
        )
        neighbor_rows = []
        for neighbor_config in neighbor_pools.values():
            neighbor_config["exact_pool_recall"] = (
                neighbor_config["exact_pool_hits"] / len(cases)
            )
            neighbor_config["average_expanded_candidate_count"] = (
                neighbor_config.pop("expanded_candidate_total") / len(cases)
            )
            neighbor_rows.append(neighbor_config)
        neighbor_rows.sort(
            key=lambda item: (
                -item["exact_pool_hits"],
                item["average_expanded_candidate_count"],
                item["neighbor_radius"],
            )
        )
        expanded_rows = []
        for expanded_config in expanded_fusions.values():
            expanded_config["exact_pool_recall"] = (
                expanded_config["exact_pool_hits"] / len(cases)
            )
            expanded_config["average_expanded_candidate_count"] = (
                expanded_config.pop("expanded_candidate_total") / len(cases)
            )
            expanded_rows.append(expanded_config)
        expanded_rows.sort(
            key=lambda item: (
                -item["exact_pool_hits"],
                item["average_expanded_candidate_count"],
                item["channel_limit"],
            )
        )
        threshold_configs = [
            item for item in expanded_rows if item["exact_pool_recall"] >= 0.95
        ]
        threshold_configs.sort(
            key=lambda item: (
                item["average_expanded_candidate_count"],
                -item["exact_pool_hits"],
            )
        )
        report = {
            "schema_version": "poc-03.retrieval-tuning-sweep.v1",
            "status": "PASS",
            "generated_at": datetime.now().astimezone().isoformat(),
            "case_count": len(cases),
            "configuration_count": len(rows),
            "best_by_top20_then_top5": rows[0],
            "top_configurations": rows[:12],
            "candidate_pool_coverage": pool_rows,
            "neighbor_expansion_coverage": neighbor_rows,
            "best_expanded_fusion_coverage": expanded_rows[:12],
            "lowest_cost_expanded_fusion_at_least_95_percent": (
                threshold_configs[0] if threshold_configs else None
            ),
            "baseline": next(
                row
                for row in rows
                if not row["source_type_filter"]
                and row["channel_limit"] == 20
                and row["fusion_mode"] == "normalized_score"
                and row["vector_weight"] == 0.6
            ),
            "privacy": {
                "queries_committed": False,
                "chunk_ids_committed": False,
                "vectors_committed": False,
                "source_names_committed": False,
                "external_calls": 0,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        finally:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
