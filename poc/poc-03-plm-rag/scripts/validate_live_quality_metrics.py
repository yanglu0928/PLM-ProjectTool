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
    ALLOWED_CLASSIFICATIONS,
    evaluate_quality,
    lexical_terms,
    parse_plain_prediction,
    searchable_text,
    tsquery_or,
)
from poc03_rag.reranker import (  # noqa: E402
    RerankCandidate,
    RerankerConfig,
    rerank_candidates,
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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


VECTOR_SQL = f"""
SELECT chunk_id, 1 - (embedding <=> %(query_vector)s::vector) AS score
FROM {SCHEMA_NAME}.retrieval_chunk
WHERE scope = 'PROJECT' AND project_id = %(project_id)s
ORDER BY embedding <=> %(query_vector)s::vector, chunk_id
LIMIT %(limit)s
""".strip()


FULL_TEXT_SQL = f"""
SELECT chunk_id,
       ts_rank_cd(to_tsvector('simple', search_body), to_tsquery('simple', %(tsquery)s)) AS score
FROM {SCHEMA_NAME}.retrieval_chunk
WHERE scope = 'PROJECT'
  AND project_id = %(project_id)s
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
    query: str,
    query_vector: list[float],
) -> tuple[list[str], bool, bool]:
    parameters = {
        "project_id": project_id,
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
                "tsquery": tsquery,
                "limit": CANDIDATE_LIMIT,
            }
            cursor.execute(FULL_TEXT_SQL, text_parameters)
            text_rows = cursor.fetchall()
            cursor.execute("EXPLAIN " + FULL_TEXT_SQL, text_parameters)
            text_plan = "\n".join(str(row[0]) for row in cursor.fetchall())
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
    ranked = sorted(combined, key=lambda chunk_id: (-combined[chunk_id], chunk_id))
    return (
        ranked[:CANDIDATE_LIMIT],
        "poc03_live_fts_idx" in text_plan,
        "poc03_live_hnsw_idx" in vector_plan,
    )


def _prediction_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["case_id", "classification", "citation_chunk_ids"],
                    "properties": {
                        "case_id": {"type": "string", "minLength": 1},
                        "classification": {"enum": sorted(ALLOWED_CLASSIFICATIONS)},
                        "citation_chunk_ids": {
                            "type": "array",
                            "minItems": 1,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                    "additionalProperties": False,
                },
            }
        },
        "additionalProperties": False,
    }


SYSTEM_PROMPT = """You are evaluating PLM implementation evidence. Use only the supplied retrieved contexts.
For each case choose exactly one classification:
- STANDARD_SATISFIED: the supplied standard capability clearly satisfies the question.
- PARTIALLY_SATISFIED: only part is supported or project configuration/integration remains.
- NON_STANDARD: the requirement clearly needs non-standard development or customization.
- INSUFFICIENT_INFORMATION: relevant evidence exists but is insufficient for a conclusion.
- NO_RELIABLE_MATCH: no supplied context reliably matches the question.
- HUMAN_CONFIRMATION_REQUIRED: evidence is relevant but contract scope, responsibility, or project judgement needs human confirmation.
Return one JSON object exactly in this shape and do not use Markdown fences:
{"items":[{"case_id":"the supplied case id","classification":"one allowed enum","citation_chunk_ids":["one supplied chunk_id"]}]}
Cite one or more chunk_id values from the supplied contexts. Never invent an id."""

RECOVERY_JSON_PROMPT = """Use only the supplied question and contexts. Return valid JSON only.
Choose exactly one of STANDARD_SATISFIED, PARTIALLY_SATISFIED, NON_STANDARD,
INSUFFICIENT_INFORMATION, NO_RELIABLE_MATCH, HUMAN_CONFIRMATION_REQUIRED and cite one supplied chunk_id.
Never add Markdown or explanation.
Exact shape: {"items":[{"case_id":"supplied id","classification":"ALLOWED_ENUM","citation_chunk_ids":["supplied chunk_id"]}]}"""

PLAIN_RECOVERY_PROMPT = """Use only the supplied question and contexts.
End the response with exactly one line in this format: FINAL:CLASSIFICATION|CHUNK_ID
CLASSIFICATION must be exactly one of STANDARD_SATISFIED, PARTIALLY_SATISFIED,
NON_STANDARD, INSUFFICIENT_INFORMATION, NO_RELIABLE_MATCH, HUMAN_CONFIRMATION_REQUIRED.
CHUNK_ID must be one supplied id.
Do not return JSON or Markdown. Never emit more than one FINAL line."""


def _load_prediction_cache(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["case_id"]): row for row in _load_json_lines(path)}


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
                contexts = []
                for chunk_id in retrievals[case_id]:
                    chunk = chunks_by_id[chunk_id]
                    contexts.append(
                        {
                            "chunk_id": chunk_id,
                            "document_id": chunk["document_id"],
                            "source_locators": chunk["source_locators"],
                            "text": str(chunk["text"])[:600],
                        }
                    )
                payload_cases.append(
                    {
                        "case_id": case_id,
                        "source_type": case["source_type"],
                        "query": case["query"],
                        "contexts": contexts,
                    }
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
                        metadata={"prompt_id": "poc03-quality", "prompt_version": "v1"},
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
                                "prompt_id": "poc03-quality-json-recovery",
                                "prompt_version": "v1",
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
                                    "prompt_id": "poc03-quality-plain-recovery",
                                    "prompt_version": "v1",
                                    "recovery_attempt": recovery_attempt,
                                },
                            )
                        )
                        try:
                            parsed = parse_plain_prediction(
                                candidate.text, valid_chunk_ids=valid_chunk_ids
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
    args = parser.parse_args()

    bailian_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not bailian_key or not deepseek_key:
        raise RuntimeError("DASHSCOPE_API_KEY and DEEPSEEK_API_KEY are required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    if not 100 <= len(cases) <= 200:
        raise ValueError("Golden Dataset must contain 100 to 200 cases")
    project_ids = {str(case.get("project_id") or "") for case in cases}
    if len(project_ids) != 1 or "" in project_ids:
        raise ValueError("live quality run requires one non-empty ProjectId")
    project_id = next(iter(project_ids))
    chunks = _load_chunks(args.parsed_root, project_id)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    expected_chunk_ids = {
        str(chunk_id)
        for case in cases
        for chunk_id in case["expected_relevant_chunk_ids"]
    }
    missing_expected = sorted(expected_chunk_ids - set(chunks_by_id))
    if missing_expected:
        raise ValueError(f"expected chunks missing from corpus: {len(missing_expected)}")
    print(f"corpus ready: {len(chunks)} chunks, {len(cases)} cases", flush=True)

    embedding_cache = args.output_dir / "embedding-cache.jsonl"
    embedding_items = [(str(chunk["chunk_id"]), str(chunk["text"])) for chunk in chunks]
    embedding_items.extend(
        (f"QUERY:{case['case_id']}", str(case["query"])) for case in cases
    )
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
        cached_retrievals = {
            str(row["case_id"]): row for row in _load_json_lines(retrieval_cache_path)
        }
        for index, case in enumerate(cases, start=1):
            case_id = str(case["case_id"])
            cached = cached_retrievals.get(case_id)
            if cached is not None:
                retrievals[case_id] = [str(value) for value in cached["top5_ids"]]
                reranker_live_count += bool(cached.get("reranker_live"))
                gin_index_used = gin_index_used or bool(cached.get("gin_index_used"))
                hnsw_index_used = hnsw_index_used or bool(cached.get("hnsw_index_used"))
                continue
            candidate_ids, used_gin, used_hnsw = _hybrid_candidates(
                connection,
                project_id=project_id,
                query=str(case["query"]),
                query_vector=embeddings[f"QUERY:{case_id}"],
            )
            gin_index_used = gin_index_used or used_gin
            hnsw_index_used = hnsw_index_used or used_hnsw
            candidates = [
                RerankCandidate(chunk_id, str(chunks_by_id[chunk_id]["text"]))
                for chunk_id in candidate_ids
            ]
            reranked = rerank_candidates(
                config=reranker_config,
                api_key=bailian_key,
                query=str(case["query"]),
                candidates=candidates,
                top_n=min(TOP_K, len(candidates)),
            )
            reranker_live_count += reranked.provider_used and not reranked.degraded
            retrievals[case_id] = [item.candidate_id for item in reranked.items]
            cache_row = {
                "case_id": case_id,
                "top5_ids": retrievals[case_id],
                "reranker_live": bool(reranked.provider_used and not reranked.degraded),
                "gin_index_used": used_gin,
                "hnsw_index_used": used_hnsw,
            }
            _append_json_lines(retrieval_cache_path, [cache_row])
            if index % 10 == 0 or index == len(cases):
                print(f"retrieval cases: {index}/{len(cases)}", flush=True)

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
            "embedding_provider": "aliyun-model-studio-openai-compatible",
            "embedding_model": args.embedding_model,
            "embedding_dimension": args.embedding_dimension,
            "index_version": "v1",
            "vector_weight": 0.6,
            "full_text_weight": 0.4,
            "candidate_limit_per_channel": CANDIDATE_LIMIT,
            "reranker_provider": "aliyun-bailian",
            "reranker_model": args.reranker_model,
            "ai_provider": "deepseek",
            "ai_model": args.deepseek_model,
            "prompt_id": "poc03-quality",
            "prompt_version": "v1",
            "format_recovery": "structured-json-then-constrained-token",
            "label_leakage": False,
        }
        report["input"] = {
            "golden_case_count": len(cases),
            "corpus_document_count": len({chunk["document_id"] for chunk in chunks}),
            "corpus_chunk_count": len(chunks),
            "project_count": len(project_ids),
        }
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
