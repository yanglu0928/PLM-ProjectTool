from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path

import alembic.command
import numpy as np
import psycopg
from alembic.config import Config
from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, text


EMPTY_DB = "poc02_alembic_empty"
DATA_DB = "poc02_alembic_data"
BENCH_DB = "poc02_benchmark"
VECTOR_COUNT = 100_000
DIMENSIONS = 32
QUERY_COUNT = 20
TOP_K = 5
SEED = 20260917
MINIMUM_MEAN_TOP5_RECALL = 0.95


def admin_url(port: int, database: str = "postgres") -> str:
    return f"postgresql://poc_admin@127.0.0.1:{port}/{database}"


def sqlalchemy_url(port: int, database: str) -> str:
    return f"postgresql+psycopg://poc_admin@127.0.0.1:{port}/{database}"


def recreate_database(port: int, database: str) -> None:
    with psycopg.connect(admin_url(port), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
            (database,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{database}"')
        connection.execute(f'CREATE DATABASE "{database}"')


def alembic_config(root: Path, port: int, database: str) -> Config:
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlalchemy_url(port, database))
    return config


def migration_validation(root: Path, port: int) -> dict[str, object]:
    recreate_database(port, EMPTY_DB)
    empty_config = alembic_config(root, port, EMPTY_DB)
    alembic.command.upgrade(empty_config, "head")
    with psycopg.connect(admin_url(port, EMPTY_DB)) as connection:
        empty_revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        empty_columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='poc02_migration_vectors' ORDER BY ordinal_position"
        ).fetchall()
    alembic.command.downgrade(empty_config, "base")
    with psycopg.connect(admin_url(port, EMPTY_DB)) as connection:
        table_after_down = connection.execute(
            "SELECT to_regclass('public.poc02_migration_vectors')"
        ).fetchone()[0]

    recreate_database(port, DATA_DB)
    data_config = alembic_config(root, port, DATA_DB)
    alembic.command.upgrade(data_config, "0001")
    engine = create_engine(sqlalchemy_url(port, DATA_DB))
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO poc02_migration_vectors (id, source_key, embedding) "
                "VALUES (1, 'retained', CAST(:embedding AS vector))"
            ),
            {"embedding": vector_literal(np.full(DIMENSIONS, 0.25, dtype=np.float32))},
        )
    alembic.command.upgrade(data_config, "head")
    with engine.connect() as connection:
        retained = connection.execute(
            text("SELECT source_key, quality_score FROM poc02_migration_vectors WHERE id=1")
        ).one()
    alembic.command.downgrade(data_config, "0001")
    with engine.connect() as connection:
        retained_after_down = connection.execute(
            text("SELECT source_key FROM poc02_migration_vectors WHERE id=1")
        ).scalar_one()
        quality_column_after_down = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='poc02_migration_vectors' AND column_name='quality_score'"
            )
        ).scalar_one()
    alembic.command.downgrade(data_config, "base")
    engine.dispose()

    if (
        empty_revision != "0002"
        or [row[0] for row in empty_columns] != ["id", "source_key", "embedding", "quality_score"]
        or table_after_down is not None
        or retained.source_key != "retained"
        or retained.quality_score != 0.0
        or retained_after_down != "retained"
        or quality_column_after_down != 0
    ):
        raise RuntimeError("Alembic empty/data upgrade or downgrade verification failed")

    return {
        "status": "PASS",
        "empty_database_upgrade_revision": empty_revision,
        "empty_database_downgrade_to_base": True,
        "data_retained_on_upgrade": True,
        "data_retained_on_downgrade": True,
    }


def vector_literal(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(np.ceil(fraction * len(ordered))) - 1)
    return ordered[index]


def benchmark_validation(port: int) -> dict[str, object]:
    recreate_database(port, BENCH_DB)
    rng = np.random.default_rng(SEED)
    vectors = rng.normal(size=(VECTOR_COUNT, DIMENSIONS)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    data_hash = hashlib.sha256(vectors.tobytes()).hexdigest()

    load_started = time.perf_counter()
    with psycopg.connect(admin_url(port, BENCH_DB)) as connection:
        connection.execute("CREATE EXTENSION vector")
        register_vector(connection)
        connection.execute(
            "CREATE TABLE poc02_benchmark_vectors (id bigint PRIMARY KEY, embedding vector(32) NOT NULL)"
        )
        with connection.cursor().copy(
            "COPY poc02_benchmark_vectors (id, embedding) FROM STDIN"
        ) as copy:
            for offset, vector in enumerate(vectors, start=1):
                copy.write_row((offset, vector))
        connection.commit()
    load_seconds = time.perf_counter() - load_started

    index_started = time.perf_counter()
    with psycopg.connect(admin_url(port, BENCH_DB)) as connection:
        connection.execute("SET maintenance_work_mem='512MB'")
        connection.execute(
            "CREATE INDEX poc02_benchmark_hnsw_idx ON poc02_benchmark_vectors "
            "USING hnsw (embedding vector_l2_ops) WITH (m=16, ef_construction=128)"
        )
        connection.execute("ANALYZE poc02_benchmark_vectors")
        connection.commit()
    index_seconds = time.perf_counter() - index_started

    queries = vectors[np.linspace(0, VECTOR_COUNT - 1, QUERY_COUNT, dtype=int)]
    exact_latency_ms: list[float] = []
    hnsw_latency_ms: list[float] = []
    recalls: list[float] = []
    plan_text = ""
    with psycopg.connect(admin_url(port, BENCH_DB)) as connection:
        register_vector(connection)
        connection.execute("SET hnsw.ef_search=100")
        for query in queries:
            connection.execute("SET enable_indexscan=off")
            exact_started = time.perf_counter()
            exact = connection.execute(
                "SELECT id FROM poc02_benchmark_vectors ORDER BY embedding <-> %s LIMIT %s",
                (query, TOP_K),
            ).fetchall()
            exact_latency_ms.append((time.perf_counter() - exact_started) * 1000)

            connection.execute("SET enable_indexscan=on")
            approx_started = time.perf_counter()
            approximate = connection.execute(
                "SELECT id FROM poc02_benchmark_vectors ORDER BY embedding <-> %s LIMIT %s",
                (query, TOP_K),
            ).fetchall()
            hnsw_latency_ms.append((time.perf_counter() - approx_started) * 1000)
            exact_ids = {row[0] for row in exact}
            approximate_ids = {row[0] for row in approximate}
            recalls.append(len(exact_ids & approximate_ids) / TOP_K)

        plan_rows = connection.execute(
            "EXPLAIN (COSTS OFF) SELECT id FROM poc02_benchmark_vectors "
            "ORDER BY embedding <-> %s LIMIT 5",
            (queries[0],),
        ).fetchall()
        plan_text = "\n".join(row[0] for row in plan_rows)
        row_count = connection.execute("SELECT count(*) FROM poc02_benchmark_vectors").fetchone()[0]
        extension_version = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]

    mean_recall = statistics.mean(recalls)
    if (
        row_count != VECTOR_COUNT
        or extension_version != "0.8.6"
        or "hnsw" not in plan_text.lower()
        or mean_recall < MINIMUM_MEAN_TOP5_RECALL
    ):
        raise RuntimeError("100k vector count, extension version, HNSW plan, or recall verification failed")

    return {
        "status": "PASS",
        "database": BENCH_DB,
        "vector_count": row_count,
        "dimensions": DIMENSIONS,
        "seed": SEED,
        "data_sha256": data_hash,
        "load_seconds": round(load_seconds, 3),
        "hnsw_build_seconds": round(index_seconds, 3),
        "query_count": QUERY_COUNT,
        "top_k": TOP_K,
        "mean_top5_recall": round(mean_recall, 4),
        "minimum_accepted_mean_top5_recall": MINIMUM_MEAN_TOP5_RECALL,
        "min_top5_recall": round(min(recalls), 4),
        "exact_latency_ms_p50": round(statistics.median(exact_latency_ms), 3),
        "exact_latency_ms_p95": round(percentile(exact_latency_ms, 0.95), 3),
        "hnsw_latency_ms_p50": round(statistics.median(hnsw_latency_ms), 3),
        "hnsw_latency_ms_p95": round(percentile(hnsw_latency_ms, 0.95), 3),
        "query_plan": plan_text,
        "pgvector_version": extension_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent
    arguments.output.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    result: dict[str, object] = {
        "status": "PASS",
        "python_version": os.sys.version.split()[0],
        "sqlalchemy_psycopg_connection": "PASS",
    }
    try:
        result["migrations"] = migration_validation(root, arguments.port)
        result["benchmark"] = benchmark_validation(arguments.port)
        result["total_seconds"] = round(time.perf_counter() - started, 3)
    except Exception as error:
        result["status"] = "FAIL"
        result["error"] = f"{type(error).__name__}: {error}"
        result["total_seconds"] = round(time.perf_counter() - started, 3)
        raise
    finally:
        arguments.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
