from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
REPO_ROOT = POC_DIR.parents[1]
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(REPO_ROOT / "poc" / "poc-04-ai-gateway" / "src"))

from poc03_rag.dataset import chunk_document  # noqa: E402
from poc03_rag.quality_evaluation import (  # noqa: E402
    evaluate_quality,
    evaluate_retrieval_quality,
    lexical_terms,
    merge_hybrid_and_lexical_candidates,
    merge_reranked_with_protected_lexical,
    parse_plain_prediction,
    rank_lexical_overlap,
    searchable_text,
    tsquery_or,
)
from poc03_rag.prompt_v2 import (  # noqa: E402
    FINAL_CLASSIFICATIONS,
    PLAIN_RECOVERY_PROMPT,
    PROMPT_ID,
    PROMPT_VERSION,
    RECOVERY_JSON_PROMPT,
    SYSTEM_PROMPT,
    build_case_payload,
    prediction_schema,
)
from poc03_rag.reranker import (  # noqa: E402
    RerankCandidate,
    RerankerConfig,
    rerank_candidates_with_retry,
)
from poc04_gateway import (  # noqa: E402
    AIError,
    AIRequest,
    AIService,
    ChatMessage,
    DeepSeekAdapter,
    ModelRouter,
    RetryPolicy,
)


SCHEMA_NAME = "poc03_live_quality"
TOP_K = 5
CANDIDATE_LIMIT = 20
EMBEDDING_BATCH_SIZE = 20
PREDICTION_BATCH_SIZE = 1
RERANKER_CANDIDATE_PIPELINE_VERSION = "r4-source-filter-lexical-idf-v1"
RETRIEVAL_PIPELINE_VERSION = "r5-protected-lexical-fusion-v1"
PROTECTED_LEXICAL_COUNT = 4
HOLDOUT_SCHEMA_VERSION = "poc-03.holdout.v1"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_evaluation_dataset_size(dataset: dict[str, Any]) -> str:
    cases = list(dataset.get("cases") or [])
    if dataset.get("schema_version") == HOLDOUT_SCHEMA_VERSION:
        if len(cases) != 50:
            raise ValueError("Independent holdout dataset must contain exactly 50 cases")
        return "independent_holdout"
    if not 100 <= len(cases) <= 200:
        raise ValueError("Golden Dataset must contain 100 to 200 cases")
    return "golden_dataset"


def _retrieval_cache_is_current(
    row: dict[str, Any] | None, *, source_type: str
) -> bool:
    return bool(
        row
        and row.get("pipeline_version") == RETRIEVAL_PIPELINE_VERSION
        and row.get("source_type") == source_type
    )


def _cached_reranker_top5(
    row: dict[str, Any] | None, *, source_type: str
) -> list[str] | None:
    if not row or row.get("source_type") != source_type or not row.get("reranker_live"):
        return None
    if row.get("pipeline_version") == RERANKER_CANDIDATE_PIPELINE_VERSION:
        values = row.get("top5_ids")
    elif row.get("reranker_candidate_pipeline_version") == RERANKER_CANDIDATE_PIPELINE_VERSION:
        values = row.get("reranker_top5_ids")
    else:
        return None
    if not isinstance(values, list) or not values:
        return None
    return [str(value) for value in values]


def _vector_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.9g}" for value in vector) + "]"


def _load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _append_json_lines(path: Path, rows: Iterable[dict[str, Any]]) -> None:
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


def _load_complete_embeddings(
    items: list[tuple[str, str]], *, cache_path: Path, dimension: int
) -> dict[str, list[float]]:
    cache = _load_embedding_cache(cache_path, dimension)
    stale = [
        item_id
        for item_id, value in items
        if item_id not in cache or cache[item_id][0] != _sha256(value)
    ]
    if stale:
        raise RuntimeError(
            f"retrieval-only mode requires a complete embedding cache; stale={len(stale)}"
        )
    return {item_id: cache[item_id][1] for item_id, _ in items}


def _request_embeddings(
    *,
    base_url: str,
    api_key: str,
    model: str,
    dimension: int,
    texts: list[str],
    timeout: float,
) -> list[list[float]]:
    payload = json.dumps(
        {"model": model, "input": texts, "dimensions": dimension},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + "/embeddings",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error = "UNKNOWN"
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read())
            records = sorted(body["data"], key=lambda item: int(item["index"]))
            vectors = [record["embedding"] for record in records]
            if len(vectors) != len(texts) or any(len(vector) != dimension for vector in vectors):
                raise ValueError("embedding response shape mismatch")
            return vectors
        except HTTPError as exc:
            last_error = f"HTTP_{exc.code}"
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                break
        except (
            URLError,
            TimeoutError,
            OSError,
            http.client.IncompleteRead,
            ValueError,
            KeyError,
            TypeError,
        ):
            last_error = "NETWORK_OR_RESPONSE_ERROR"
            if attempt == 3:
                break
        time.sleep(min(2 ** (attempt - 1), 4))
    raise RuntimeError(f"embedding request failed: {last_error}")


def _ensure_embeddings(
    items: list[tuple[str, str]],
    *,
    cache_path: Path,
    base_url: str,
    api_key: str,
    model: str,
    dimension: int,
    timeout: float,
) -> dict[str, list[float]]:
    cache = _load_embedding_cache(cache_path, dimension)
    missing = [
        (item_id, text)
        for item_id, text in items
        if item_id not in cache or cache[item_id][0] != _sha256(text)
    ]
    total_batches = (len(missing) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
    for start in range(0, len(missing), EMBEDDING_BATCH_SIZE):
        batch = missing[start : start + EMBEDDING_BATCH_SIZE]
        vectors = _request_embeddings(
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimension=dimension,
            texts=[text for _, text in batch],
            timeout=timeout,
        )
        new_rows = []
        for (item_id, text), vector in zip(batch, vectors, strict=True):
            digest = _sha256(text)
            cache[item_id] = (digest, vector)
            new_rows.append({"id": item_id, "text_sha256": digest, "vector": vector})
        _append_json_lines(cache_path, new_rows)
        batch_number = start // EMBEDDING_BATCH_SIZE + 1
        if batch_number % 10 == 0 or batch_number == total_batches:
            print(f"embedding batches: {batch_number}/{total_batches}", flush=True)
    return {item_id: cache[item_id][1] for item_id, _ in items}


def _deduplicate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        existing = unique.get(chunk_id)
        if existing is None:
            unique[chunk_id] = chunk
            continue
        if existing != chunk:
            raise ValueError(f"conflicting duplicate ChunkId: {chunk_id}")
    return list(unique.values())


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
    return _deduplicate_chunks(chunks)


VECTOR_SQL = f"""
SELECT chunk_id, 1 - (embedding <=> %(query_vector)s::vector) AS score
FROM {SCHEMA_NAME}.retrieval_chunk
WHERE scope = 'PROJECT' AND project_id = %(project_id)s
  AND source_corpus = %(source_type)s
ORDER BY embedding <=> %(query_vector)s::vector, chunk_id
LIMIT %(limit)s
""".strip()


FULL_TEXT_SQL = f"""
SELECT chunk_id,
       ts_rank_cd(to_tsvector('simple', search_body), to_tsquery('simple', %(tsquery)s)) AS score
FROM {SCHEMA_NAME}.retrieval_chunk
WHERE scope = 'PROJECT'
  AND project_id = %(project_id)s
  AND source_corpus = %(source_type)s
  AND to_tsvector('simple', search_body) @@ to_tsquery('simple', %(tsquery)s)
ORDER BY score DESC, chunk_id
LIMIT %(limit)s
""".strip()


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
                _vector_literal(embeddings[chunk["chunk_id"]]),
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


def _hybrid_candidates(
    connection: psycopg.Connection,
    *,
    project_id: str,
    source_type: str,
    query: str,
    query_vector: list[float],
    lexical_corpus: dict[str, str],
) -> tuple[list[str], bool, bool]:
    parameters = {
        "project_id": project_id,
        "source_type": source_type,
        "query_vector": _vector_literal(query_vector),
        "limit": CANDIDATE_LIMIT,
    }
    terms = lexical_terms(query)
    tsquery = tsquery_or(terms)
    with connection.cursor() as cursor:
        cursor.execute(VECTOR_SQL, parameters)
        vector_rows = cursor.fetchall()
        cursor.execute("EXPLAIN " + VECTOR_SQL, parameters)
        vector_plan = "\n".join(str(row[0]) for row in cursor.fetchall())
        text_rows: list[tuple[Any, ...]] = []
        text_plan = ""
        if tsquery:
            text_parameters = {
                "project_id": project_id,
                "source_type": source_type,
                "tsquery": tsquery,
                "limit": CANDIDATE_LIMIT,
            }
            cursor.execute(FULL_TEXT_SQL, text_parameters)
            text_rows = cursor.fetchall()
            cursor.execute("EXPLAIN " + FULL_TEXT_SQL, text_parameters)
            text_plan = "\n".join(str(row[0]) for row in cursor.fetchall())
    lexical_ranked = rank_lexical_overlap(
        query,
        lexical_corpus,
        limit=min(CANDIDATE_LIMIT, len(lexical_corpus)),
    )
    ranked = merge_hybrid_and_lexical_candidates(
        [(str(row[0]), float(row[1])) for row in vector_rows],
        [(str(row[0]), float(row[1])) for row in text_rows],
        lexical_ranked,
        channel_limit=CANDIDATE_LIMIT,
        vector_weight=0.6,
    )
    return (
        ranked,
        "poc03_live_fts_idx" in text_plan,
        "poc03_live_hnsw_idx" in vector_plan,
    )


def _prediction_schema() -> dict[str, Any]:
    return prediction_schema()


def _load_prediction_cache(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row["case_id"]): row
        for row in _load_json_lines(path)
        if row.get("prompt_id") == PROMPT_ID
        and row.get("prompt_version") == PROMPT_VERSION
    }


def _predict(
    cases: list[dict[str, Any]],
    retrievals: dict[str, list[str]],
    chunks_by_id: dict[str, dict[str, Any]],
    *,
    cache_path: Path,
    api_key: str,
    base_url: str,
    model: str,
) -> tuple[dict[str, dict[str, Any]], int]:
    predictions = _load_prediction_cache(cache_path)
    fallback_count = sum(bool(row.get("format_fallback")) for row in predictions.values())
    pending = [case for case in cases if str(case["case_id"]) not in predictions]
    router = ModelRouter()
    router.register(
        DeepSeekAdapter(api_key=api_key, base_url=base_url, timeout_seconds=90)
    )
    service = AIService(
        router,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4),
    )
    try:
        for start in range(0, len(pending), PREDICTION_BATCH_SIZE):
            batch = pending[start : start + PREDICTION_BATCH_SIZE]
            payload_cases = []
            for case in batch:
                case_id = str(case["case_id"])
                payload_cases.append(
                    build_case_payload(
                        case,
                        retrievals[case_id],
                        chunks_by_id,
                    )
                )
            request_payload = json.dumps({"cases": payload_cases}, ensure_ascii=False)
            format_fallback = False
            try:
                response = service.complete(
                    AIRequest(
                        task_type="REQUIREMENT_MATCH",
                        provider="deepseek",
                        model=model,
                        messages=(
                            ChatMessage("system", SYSTEM_PROMPT),
                            ChatMessage("user", request_payload),
                        ),
                        output_schema=_prediction_schema(),
                        max_tokens=1024,
                        temperature=0.0,
                        metadata={"prompt_id": PROMPT_ID, "prompt_version": PROMPT_VERSION},
                    )
                )
            except AIError as first_error:
                if first_error.code not in {"AI_JSON_INVALID", "AI_SCHEMA_INVALID"}:
                    raise
                compact_cases = []
                for payload_case in payload_cases:
                    compact_cases.append(
                        {
                            **payload_case,
                            "contexts": [
                                {**context, "text": str(context["text"])[:200]}
                                for context in payload_case["contexts"]
                            ],
                        }
                    )
                compact_payload = json.dumps(
                    {"cases": compact_cases}, ensure_ascii=False
                )
                try:
                    response = service.complete(
                        AIRequest(
                            task_type="REQUIREMENT_MATCH",
                            provider="deepseek",
                            model=model,
                            messages=(
                                ChatMessage("system", RECOVERY_JSON_PROMPT),
                                ChatMessage("user", compact_payload),
                            ),
                            output_schema=_prediction_schema(),
                            max_tokens=4096,
                            temperature=0.0,
                            metadata={
                                "prompt_id": f"{PROMPT_ID}-json-recovery",
                                "prompt_version": PROMPT_VERSION,
                            },
                        )
                    )
                except AIError as second_error:
                    if second_error.code not in {"AI_JSON_INVALID", "AI_SCHEMA_INVALID"}:
                        raise
                    if len(batch) != 1:
                        raise RuntimeError("plain recovery requires a single case")
                    case_id = str(batch[0]["case_id"])
                    valid_chunk_ids = retrievals[case_id]
                    plain_response = None
                    last_parse_error: ValueError | None = None
                    for recovery_attempt in range(1, 4):
                        candidate = service.complete(
                            AIRequest(
                                task_type="REQUIREMENT_MATCH",
                                provider="deepseek",
                                model=model,
                                messages=(
                                    ChatMessage("system", PLAIN_RECOVERY_PROMPT),
                                    ChatMessage("user", compact_payload),
                                ),
                                max_tokens=2048,
                                temperature=0.0,
                                metadata={
                                    "prompt_id": f"{PROMPT_ID}-plain-recovery",
                                    "prompt_version": PROMPT_VERSION,
                                    "recovery_attempt": recovery_attempt,
                                },
                            )
                        )
                        try:
                            parsed = parse_plain_prediction(
                                candidate.text,
                                valid_chunk_ids=valid_chunk_ids,
                                allowed_classifications=FINAL_CLASSIFICATIONS,
                            )
                        except ValueError as exc:
                            last_parse_error = exc
                            continue
                        parsed["case_id"] = case_id
                        parsed["format_fallback"] = True
                        plain_response = parsed
                        break
                    if plain_response is None:
                        raise RuntimeError(
                            "AI plain recovery did not return a constrained prediction"
                        ) from last_parse_error
                    items = [plain_response]
                    format_fallback = True
                else:
                    items = list((response.structured or {}).get("items") or [])
            else:
                items = list((response.structured or {}).get("items") or [])
            expected_ids = {str(case["case_id"]) for case in batch}
            actual_ids = {str(item.get("case_id")) for item in items}
            if actual_ids != expected_ids or len(items) != len(batch):
                raise RuntimeError("AI prediction response case IDs do not match request")
            for item in items:
                item["case_id"] = str(item["case_id"])
                item["format_fallback"] = bool(
                    item.get("format_fallback") or format_fallback
                )
                item["prompt_id"] = PROMPT_ID
                item["prompt_version"] = PROMPT_VERSION
                predictions[item["case_id"]] = item
                fallback_count += bool(item["format_fallback"])
            _append_json_lines(cache_path, items)
            completed = min(start + len(batch), len(pending))
            print(f"AI prediction cases: {completed}/{len(pending)}", flush=True)
    finally:
        router.close()
    return predictions, fallback_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live POC-03 Golden Dataset metrics.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--parsed-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        help="Optional existing embedding cache; required to avoid embedding calls in retrieval-only mode",
    )
    parser.add_argument(
        "--reranker-cache",
        type=Path,
        help="Optional prior live R4 reranker cache for label-free R5 replay",
    )
    parser.add_argument("--embedding-base-url", required=True)
    parser.add_argument("--reranker-base-url", required=True)
    parser.add_argument("--embedding-model", default="qwen3.7-text-embedding")
    parser.add_argument("--embedding-dimension", type=int, default=1024)
    parser.add_argument("--reranker-model", default="qwen3-rerank")
    parser.add_argument("--deepseek-base-url", default="https://api.deepseek.com")
    parser.add_argument("--deepseek-model", default="deepseek-flash")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Run live embedding/hybrid/reranker validation without DeepSeek predictions",
    )
    mode.add_argument(
        "--prediction-only",
        action="store_true",
        help="Require complete local embedding/retrieval caches and call only DeepSeek",
    )
    args = parser.parse_args()

    bailian_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not bailian_key and not args.prediction_only:
        raise RuntimeError("DASHSCOPE_API_KEY is required")
    if not args.retrieval_only and not deepseek_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required unless --retrieval-only is set")
    if args.prediction_only and (not args.embedding_cache or not args.reranker_cache):
        raise RuntimeError(
            "--prediction-only requires --embedding-cache and --reranker-cache"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    dataset_kind = _validate_evaluation_dataset_size(dataset)
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("live quality run requires one non-empty ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(args.parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    chunks_by_source: dict[str, dict[str, str]] = {}
    for chunk in chunks:
        source_type = str(chunk["source_corpus"])
        chunks_by_source.setdefault(source_type, {})[str(chunk["chunk_id"])] = str(
            chunk["text"]
        )
    expected_chunk_ids = {
        str(chunk_id)
        for case in cases
        for chunk_id in case["expected_relevant_chunk_ids"]
    }
    missing_expected = sorted(expected_chunk_ids - set(chunks_by_id))
    if missing_expected:
        raise ValueError(f"expected chunks missing from corpus: {len(missing_expected)}")
    print(f"corpus ready: {len(chunks)} chunks, {len(cases)} cases", flush=True)

    embedding_cache = args.embedding_cache or args.output_dir / "embedding-cache.jsonl"
    embedding_items = [(str(chunk["chunk_id"]), str(chunk["text"])) for chunk in chunks]
    embedding_items.extend(
        (f"QUERY:{case['case_id']}", str(case["query"])) for case in cases
    )
    if args.retrieval_only or args.prediction_only:
        embeddings = _load_complete_embeddings(
            embedding_items,
            cache_path=embedding_cache,
            dimension=args.embedding_dimension,
        )
    else:
        embeddings = _ensure_embeddings(
            embedding_items,
            cache_path=embedding_cache,
            base_url=args.embedding_base_url,
            api_key=bailian_key,
            model=args.embedding_model,
            dimension=args.embedding_dimension,
            timeout=60,
        )
    print(f"embedding cache ready: {len(embeddings)} vectors", flush=True)

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
    )
    retrievals: dict[str, list[str]] = {}
    reranker_live_count = 0
    reranker_external_calls = 0
    reranker_cached_live_results_reused = 0
    gin_index_used = False
    hnsw_index_used = False
    try:
        database_version, pgvector_version = _create_index(
            connection,
            chunks,
            embeddings,
            args.embedding_dimension,
        )
        print("PostgreSQL hybrid index ready", flush=True)
        reranker_config = RerankerConfig(
            provider="aliyun-bailian",
            base_url=args.reranker_base_url,
            model=args.reranker_model,
            timeout_seconds=60,
            fail_open=False,
        )
        retrieval_cache_path = args.output_dir / "retrieval-cache.jsonl"
        cached_retrievals: dict[str, dict[str, Any]] = {}
        if args.reranker_cache:
            cached_retrievals.update(
                {
                    str(row["case_id"]): row
                    for row in _load_json_lines(args.reranker_cache)
                }
            )
        cached_retrievals.update(
            {
                str(row["case_id"]): row
                for row in _load_json_lines(retrieval_cache_path)
            }
        )
        for index, case in enumerate(cases, start=1):
            case_id = str(case["case_id"])
            cached = cached_retrievals.get(case_id)
            if _retrieval_cache_is_current(
                cached, source_type=str(case["source_type"])
            ):
                retrievals[case_id] = [str(value) for value in cached["top5_ids"]]
                reranker_live_count += bool(cached.get("reranker_live"))
                gin_index_used = gin_index_used or bool(cached.get("gin_index_used"))
                hnsw_index_used = hnsw_index_used or bool(cached.get("hnsw_index_used"))
                reranker_cached_live_results_reused += bool(cached.get("reranker_live"))
                continue
            if args.prediction_only:
                raise RuntimeError(
                    f"prediction-only mode requires a complete current R5 retrieval cache: {case_id}"
                )
            source_type = str(case["source_type"])
            lexical_top5 = rank_lexical_overlap(
                str(case["query"]),
                chunks_by_source[source_type],
                limit=TOP_K,
            )
            reranker_top5 = _cached_reranker_top5(cached, source_type=source_type)
            if reranker_top5 is not None:
                used_gin = bool(cached.get("gin_index_used"))
                used_hnsw = bool(cached.get("hnsw_index_used"))
                reranker_live = True
                reranker_cached_live_results_reused += 1
            else:
                candidate_ids, used_gin, used_hnsw = _hybrid_candidates(
                    connection,
                    project_id=project_id,
                    source_type=source_type,
                    query=str(case["query"]),
                    query_vector=embeddings[f"QUERY:{case_id}"],
                    lexical_corpus=chunks_by_source[source_type],
                )
                candidates = [
                    RerankCandidate(chunk_id, str(chunks_by_id[chunk_id]["text"]))
                    for chunk_id in candidate_ids
                ]
                reranked = rerank_candidates_with_retry(
                    config=reranker_config,
                    api_key=bailian_key,
                    query=str(case["query"]),
                    candidates=candidates,
                    top_n=min(TOP_K, len(candidates)),
                    max_attempts=3,
                    initial_backoff_seconds=2,
                )
                reranker_top5 = [item.candidate_id for item in reranked.items]
                reranker_live = bool(reranked.provider_used and not reranked.degraded)
                reranker_external_calls += 1
            gin_index_used = gin_index_used or used_gin
            hnsw_index_used = hnsw_index_used or used_hnsw
            reranker_live_count += reranker_live
            retrievals[case_id] = merge_reranked_with_protected_lexical(
                reranker_top5,
                lexical_top5,
                top_k=TOP_K,
                protected_lexical_count=PROTECTED_LEXICAL_COUNT,
            )
            cache_row = {
                "case_id": case_id,
                "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
                "reranker_candidate_pipeline_version": RERANKER_CANDIDATE_PIPELINE_VERSION,
                "source_type": source_type,
                "reranker_top5_ids": reranker_top5,
                "top5_ids": retrievals[case_id],
                "reranker_live": reranker_live,
                "gin_index_used": used_gin,
                "hnsw_index_used": used_hnsw,
            }
            _append_json_lines(retrieval_cache_path, [cache_row])
            if index % 10 == 0 or index == len(cases):
                print(f"retrieval cases: {index}/{len(cases)}", flush=True)

        common_configuration = {
            "embedding_provider": "aliyun-model-studio-openai-compatible",
            "embedding_model": args.embedding_model,
            "embedding_dimension": args.embedding_dimension,
            "index_version": "v1",
            "vector_weight": 0.6,
            "full_text_weight": 0.4,
            "candidate_limit_per_channel": CANDIDATE_LIMIT,
            "candidate_channels": ["vector", "full_text", "lexical_idf"],
            "source_type_filter": True,
            "cjk_ocr_spacing_normalization": True,
            "retrieval_pipeline_version": RETRIEVAL_PIPELINE_VERSION,
            "reranker_candidate_pipeline_version": RERANKER_CANDIDATE_PIPELINE_VERSION,
            "protected_lexical_count": PROTECTED_LEXICAL_COUNT,
            "semantic_reranker_count": TOP_K - PROTECTED_LEXICAL_COUNT,
            "reranker_provider": "aliyun-bailian",
            "reranker_model": args.reranker_model,
            "embedding_external_calls": 0
            if args.retrieval_only or args.prediction_only
            else "as_needed",
            "reranker_external_calls_current_run": reranker_external_calls,
            "cached_live_reranker_results_reused": reranker_cached_live_results_reused,
        }
        common_input = {
            "dataset_kind": dataset_kind,
            "golden_case_count": len(cases),
            "corpus_document_count": len({chunk["document_id"] for chunk in chunks}),
            "corpus_chunk_count": len(chunks),
            "project_count": len(project_ids),
        }
        if args.retrieval_only:
            report = evaluate_retrieval_quality(
                cases,
                retrievals,
                reranker_live_count=reranker_live_count,
                gin_index_used=gin_index_used,
                hnsw_index_used=hnsw_index_used,
            )
            report["generated_at"] = datetime.now().astimezone().isoformat()
            report["environment"] = {
                "postgresql_version": database_version,
                "pgvector_version": pgvector_version,
                "platform": "Windows 11 x86-64",
            }
            report["configuration"] = common_configuration
            report["input"] = common_input
            report["conclusion"] = (
                "The live retrieval and reranker threshold passed."
                if report["status"] == "PASS"
                else "The live retrieval and reranker threshold failed."
            )
            report_path = args.output_dir / "live-retrieval-result.json"
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            return 0 if report["status"] == "PASS" else 1

        predictions, format_fallback_count = _predict(
            cases,
            retrievals,
            chunks_by_id,
            cache_path=args.output_dir / "prediction-cache.jsonl",
            api_key=deepseek_key,
            base_url=args.deepseek_base_url,
            model=args.deepseek_model,
        )
        report = evaluate_quality(
            cases,
            retrievals,
            predictions,
            reranker_live_count=reranker_live_count,
            gin_index_used=gin_index_used,
            hnsw_index_used=hnsw_index_used,
        )
        if format_fallback_count:
            report["summary"]["prediction_plain_protocol_count"] = format_fallback_count
        report["generated_at"] = datetime.now().astimezone().isoformat()
        report["environment"] = {
            "postgresql_version": database_version,
            "pgvector_version": pgvector_version,
            "platform": "Windows 11 x86-64",
        }
        report["configuration"] = {
            **common_configuration,
            "ai_provider": "deepseek",
            "ai_model": args.deepseek_model,
            "prompt_id": PROMPT_ID,
            "prompt_version": PROMPT_VERSION,
            "format_recovery": "structured-json-then-constrained-token",
            "label_leakage": False,
        }
        report["input"] = common_input
        report["conclusion"] = (
            "All three live Golden Dataset quality thresholds passed."
            if report["status"] == "PASS"
            else "One or more live Golden Dataset quality thresholds failed."
        )
        raw_result = {
            "retrievals": retrievals,
            "predictions": predictions,
        }
        (args.output_dir / "case-level-result.json").write_text(
            json.dumps(raw_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path = args.output_dir / "live-quality-result.json"
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
