from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from poc03_rag.layered_diagnostics import (  # noqa: E402
    document_key,
    expand_ranked_neighbors,
    fuse_ranked_scores,
)
from poc03_rag.dataset import chunk_document  # noqa: E402
from poc03_rag.quality_evaluation import (  # noqa: E402
    lexical_terms,
    searchable_text,
    tsquery_or,
)
from poc03_rag.reranker import (  # noqa: E402
    RerankCandidate,
    RerankerConfig,
    rerank_candidates,
)
SCHEMA_NAME = "poc03_live_quality"
CHANNEL_LIMIT = 100
FUSED_LIMIT = 100
NEIGHBOR_RADIUS = 3
VECTOR_WEIGHT = 0.4
TOP_K = 5

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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.9g}" for value in vector) + "]"


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _append_json_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
        stream.flush()


def _load_embedding_cache(path: Path, dimension: int) -> dict[str, tuple[str, list[float]]]:
    cache: dict[str, tuple[str, list[float]]] = {}
    for row in _load_json_lines(path):
        vector = row.get("vector")
        if isinstance(vector, list) and len(vector) == dimension:
            cache[str(row["id"])] = (str(row["text_sha256"]), vector)
    return cache


def _load_chunks(parsed_root: Path, project_id: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for corpus_dir in sorted(path for path in parsed_root.iterdir() if path.is_dir()):
        for path in sorted(corpus_dir.glob("*.parsed.json")):
            parsed_id = path.name.removesuffix(".parsed.json")
            document_id = f"{corpus_dir.name}-{parsed_id}"
            parsed = json.loads(path.read_text(encoding="utf-8"))
            chunks.extend(
                chunk_document(
                    document_id,
                    parsed,
                    project_id,
                    source_corpus=corpus_dir.name,
                )
            )
    return chunks


def _create_index(
    connection: psycopg.Connection,
    chunks: list[dict[str, Any]],
    embeddings: dict[str, list[float]],
    dimension: int,
) -> tuple[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        cursor.execute(f"CREATE SCHEMA {SCHEMA_NAME}")
        cursor.execute(
            f"""
            CREATE TABLE {SCHEMA_NAME}.retrieval_chunk (
              chunk_id text PRIMARY KEY,
              document_id text NOT NULL,
              source_corpus text NOT NULL,
              scope text NOT NULL CHECK (scope = 'PROJECT'),
              project_id text NOT NULL,
              body text NOT NULL,
              search_body text NOT NULL,
              source_locators jsonb NOT NULL,
              embedding vector({dimension}) NOT NULL
            )
            """
        )
        records = [
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["source_corpus"],
                chunk["scope"],
                chunk["project_id"],
                chunk["text"],
                searchable_text(chunk["text"]),
                json.dumps(chunk["source_locators"], ensure_ascii=False),
                _vector_literal(embeddings[str(chunk["chunk_id"])]),
            )
            for chunk in chunks
        ]
        cursor.executemany(
            f"""
            INSERT INTO {SCHEMA_NAME}.retrieval_chunk
              (chunk_id, document_id, source_corpus, scope, project_id, body,
               search_body, source_locators, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
            """,
            records,
        )
        cursor.execute(
            f"CREATE INDEX poc03_live_fts_idx ON {SCHEMA_NAME}.retrieval_chunk "
            "USING gin (to_tsvector('simple', search_body))"
        )
        cursor.execute(
            f"CREATE INDEX poc03_live_hnsw_idx ON {SCHEMA_NAME}.retrieval_chunk "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 32, ef_construction = 200)"
        )
        cursor.execute(f"ANALYZE {SCHEMA_NAME}.retrieval_chunk")
        cursor.execute("SET enable_seqscan = off")
        cursor.execute("SET hnsw.ef_search = 200")
        cursor.execute("SELECT version(), extversion FROM pg_extension WHERE extname='vector'")
        database_version, pgvector_version = cursor.fetchone()
    return str(database_version).split(",")[0], str(pgvector_version)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _document_hit(expected: set[str], ranked: list[str]) -> bool:
    expected_documents = {document_key(item) for item in expected}
    return any(document_key(item) in expected_documents for item in ranked[:TOP_K])


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate frozen tuned retrieval with live reranking")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reranker-base-url", required=True)
    parser.add_argument("--reranker-model", default="qwen3-rerank")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--dimension", type=int, default=1024)
    args = parser.parse_args()

    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = _load_json(args.dataset)
    cases = list(dataset.get("cases") or [])
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("validation requires one non-empty ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(args.parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    document_chunks: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        document_chunks[str(chunk["document_id"])].append(str(chunk["chunk_id"]))

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

    retrieval_cache_path = args.output_dir / "tuned-reranker-cache.jsonl"
    retrieval_cache = {
        str(row["case_id"]): row for row in _load_json_lines(retrieval_cache_path)
    }
    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
        connect_timeout=10,
    )
    config = RerankerConfig(
        provider="aliyun-bailian",
        base_url=args.reranker_base_url,
        model=args.reranker_model,
        timeout_seconds=120,
        fail_open=False,
    )
    exact_hits = document_hits = candidate_pool_hits = live_count = 0
    candidate_counts: list[int] = []
    total_characters: list[int] = []
    case_results: list[dict[str, Any]] = []
    try:
        database_version, pgvector_version = _create_index(
            connection, chunks, embeddings, args.dimension
        )
        for index, case in enumerate(cases, start=1):
            case_id = str(case["case_id"])
            expected = {str(item) for item in case["expected_relevant_chunk_ids"]}
            row = retrieval_cache.get(case_id)
            if row is None:
                common = {
                    "project_id": project_id,
                    "source_type": str(case["source_type"]),
                    "limit": CHANNEL_LIMIT,
                }
                source_clause = "AND source_corpus = %(source_type)s"
                with connection.cursor() as cursor:
                    cursor.execute(
                        VECTOR_TEMPLATE.format(
                            schema=SCHEMA_NAME, source_filter=source_clause
                        ),
                        {
                            **common,
                            "query_vector": _vector_literal(
                                embeddings[f"QUERY:{case_id}"]
                            ),
                        },
                    )
                    vector_rows = [
                        (str(item), float(score)) for item, score in cursor.fetchall()
                    ]
                    text_rows: list[tuple[str, float]] = []
                    tsquery = tsquery_or(lexical_terms(str(case["query"])))
                    if tsquery:
                        cursor.execute(
                            TEXT_TEMPLATE.format(
                                schema=SCHEMA_NAME, source_filter=source_clause
                            ),
                            {**common, "tsquery": tsquery},
                        )
                        text_rows = [
                            (str(item), float(score))
                            for item, score in cursor.fetchall()
                        ]
                fused = fuse_ranked_scores(
                    vector_rows,
                    text_rows,
                    vector_weight=VECTOR_WEIGHT,
                    mode="rrf",
                )
                candidate_ids = expand_ranked_neighbors(
                    fused,
                    document_chunks=document_chunks,
                    fused_limit=FUSED_LIMIT,
                    neighbor_radius=NEIGHBOR_RADIUS,
                )
                if len(candidate_ids) > 500:
                    raise ValueError("expanded candidate count exceeds provider limit")
                characters = sum(len(str(chunks_by_id[item]["text"])) for item in candidate_ids)
                candidates = [
                    RerankCandidate(item, str(chunks_by_id[item]["text"]))
                    for item in candidate_ids
                ]
                reranked = rerank_candidates(
                    config=config,
                    api_key=api_key,
                    query=str(case["query"]),
                    candidates=candidates,
                    top_n=min(TOP_K, len(candidates)),
                )
                row = {
                    "case_id": case_id,
                    "top5_ids": [item.candidate_id for item in reranked.items],
                    "candidate_count": len(candidate_ids),
                    "candidate_character_count": characters,
                    "candidate_pool_hit": bool(expected.intersection(candidate_ids)),
                    "reranker_live": bool(reranked.provider_used and not reranked.degraded),
                }
                _append_json_lines(retrieval_cache_path, [row])
                retrieval_cache[case_id] = row
            top5_ids = [str(item) for item in row["top5_ids"]]
            exact_hit = bool(expected.intersection(top5_ids))
            same_document_hit = _document_hit(expected, top5_ids)
            exact_hits += exact_hit
            document_hits += same_document_hit
            candidate_pool_hits += bool(row["candidate_pool_hit"])
            live_count += bool(row["reranker_live"])
            candidate_counts.append(int(row["candidate_count"]))
            total_characters.append(int(row["candidate_character_count"]))
            case_results.append(
                {
                    "case_id": case_id,
                    "top5_ids": top5_ids,
                    "exact_top5_hit": exact_hit,
                    "same_document_top5_hit": same_document_hit,
                    "candidate_pool_hit": bool(row["candidate_pool_hit"]),
                }
            )
            if index % 5 == 0 or index == len(cases):
                print(f"reranker cases: {index}/{len(cases)}", flush=True)
        count = len(cases)
        report = {
            "schema_version": "poc-03.tuned-reranker-result.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "status": "PASS" if count and exact_hits / count >= 0.95 else "FAIL",
            "threshold": {"metric": "exact_top5_recall", "minimum": 0.95},
            "summary": {
                "case_count": count,
                "candidate_pool_hits": candidate_pool_hits,
                "candidate_pool_recall": candidate_pool_hits / count if count else 0.0,
                "exact_top5_hits": exact_hits,
                "exact_top5_recall": exact_hits / count if count else 0.0,
                "same_document_top5_hits": document_hits,
                "same_document_top5_recall": document_hits / count if count else 0.0,
                "reranker_live_count": live_count,
                "candidate_count_average": sum(candidate_counts) / count if count else 0.0,
                "candidate_count_max": max(candidate_counts, default=0),
                "candidate_character_count_average": sum(total_characters) / count if count else 0.0,
                "candidate_character_count_max": max(total_characters, default=0),
            },
            "configuration": {
                "source_type_filter": True,
                "channel_limit": CHANNEL_LIMIT,
                "fusion_mode": "rrf",
                "vector_weight": VECTOR_WEIGHT,
                "full_text_weight": 1.0 - VECTOR_WEIGHT,
                "fused_candidate_limit": FUSED_LIMIT,
                "neighbor_radius": NEIGHBOR_RADIUS,
                "reranker_provider": "aliyun-bailian",
                "reranker_model": args.reranker_model,
            },
            "environment": {
                "postgresql_version": database_version,
                "pgvector_version": pgvector_version,
                "platform": "Windows 11 x86-64",
            },
            "privacy": {
                "queries_in_report": False,
                "chunk_text_in_report": False,
                "vectors_in_report": False,
                "provider_response_body_committed": False,
                "api_key_committed": False,
            },
        }
        (args.output_dir / "tuned-reranker-case-result.json").write_text(
            json.dumps({"cases": case_results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path = args.output_dir / "tuned-reranker-result.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return 0 if report["status"] == "PASS" else 1
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        finally:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
