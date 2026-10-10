from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.project_isolation import HYBRID_SQL, ProjectRetrievalRequest  # noqa: E402
from poc03_rag.retrieval_metrics import top_k_recall  # noqa: E402


SCENARIOS = (
    ("H01", "产品 结构 管理", (1.0, 0.0, 0.0)),
    ("H02", "工程 变更 审批", (0.0, 1.0, 0.0)),
    ("H03", "文档 版本 控制", (0.0, 0.0, 1.0)),
    ("H04", "物料 编码 规则", (-1.0, 0.0, 0.0)),
)


def _vector_literal(values: tuple[float, float, float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hybrid retrieval Top-5.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute("DROP SCHEMA IF EXISTS poc03_isolation CASCADE")
            cursor.execute("CREATE SCHEMA poc03_isolation")
            cursor.execute(
                """
                CREATE TABLE poc03_isolation.retrieval_document (
                  id text PRIMARY KEY,
                  scope text NOT NULL CHECK (scope = 'PROJECT'),
                  project_id text NOT NULL,
                  body text NOT NULL,
                  embedding vector(3) NOT NULL
                )
                """
            )
            records = []
            for scenario_id, terms, query_vector in SCENARIOS:
                for number in range(1, 6):
                    records.append(
                        (
                            f"{scenario_id}-R-{number:02d}",
                            "PROJECT",
                            "PROJECT-HYBRID",
                            f"{terms} synthetic combined relevant {number}",
                            _vector_literal(query_vector),
                        )
                    )
                for number in range(1, 6):
                    records.append(
                        (
                            f"{scenario_id}-T-{number:02d}",
                            "PROJECT",
                            "PROJECT-HYBRID",
                            f"{terms} synthetic text only {number}",
                            "[0.3,0.4,0.5]",
                        )
                    )
                for number in range(1, 6):
                    records.append(
                        (
                            f"{scenario_id}-V-{number:02d}",
                            "PROJECT",
                            "PROJECT-HYBRID",
                            f"unrelated synthetic vector only {number}",
                            _vector_literal(query_vector),
                        )
                    )
            for number in range(1, 941):
                angle = (number * 0.754877666) % (2 * math.pi)
                z = ((number * 29) % 200 - 100) / 100.0
                records.append(
                    (
                        f"D-{number:04d}",
                        "PROJECT",
                        "PROJECT-HYBRID",
                        "unrelated synthetic distractor",
                        _vector_literal((math.cos(angle) * 0.5, math.sin(angle) * 0.5, z)),
                    )
                )
            cursor.executemany(
                """
                INSERT INTO poc03_isolation.retrieval_document
                  (id, scope, project_id, body, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                records,
            )
            cursor.execute(
                "CREATE INDEX poc03_hybrid_fts_idx "
                "ON poc03_isolation.retrieval_document "
                "USING gin (to_tsvector('simple', body))"
            )
            cursor.execute(
                "CREATE INDEX poc03_hybrid_hnsw_idx "
                "ON poc03_isolation.retrieval_document "
                "USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 32, ef_construction = 200)"
            )
            cursor.execute("ANALYZE poc03_isolation.retrieval_document")
            cursor.execute("SET enable_seqscan = off")
            cursor.execute("SET hnsw.ef_search = 200")
            cursor.execute("SELECT version(), extversion FROM pg_extension WHERE extname='vector'")
            database_version, pgvector_version = cursor.fetchone()

        scenario_results = []
        recalls = []
        gin_index_used = True
        hnsw_index_used = True
        for scenario_id, terms, query_vector in SCENARIOS:
            request = ProjectRetrievalRequest(
                project_id="PROJECT-HYBRID",
                query_text=terms,
                query_vector=query_vector,
                limit=5,
            )
            with connection.cursor() as cursor:
                cursor.execute(HYBRID_SQL, request.parameters)
                rows = cursor.fetchall()
                cursor.execute("EXPLAIN " + HYBRID_SQL, request.parameters)
                plan = "\n".join(str(row[0]) for row in cursor.fetchall())
            actual_ids = [str(row[0]) for row in rows]
            expected_ids = [f"{scenario_id}-R-{number:02d}" for number in range(1, 6)]
            recall = top_k_recall(expected_ids, actual_ids, k=5)
            recalls.append(recall)
            gin_index_used = gin_index_used and "poc03_hybrid_fts_idx" in plan
            hnsw_index_used = hnsw_index_used and "poc03_hybrid_hnsw_idx" in plan
            scenario_results.append(
                {
                    "scenario_id": scenario_id,
                    "expected_count": 5,
                    "result_count": len(actual_ids),
                    "top5_recall": recall,
                    "result_ids": actual_ids,
                }
            )
        average_recall = sum(recalls) / len(recalls)
        minimum_recall = min(recalls)
        status = (
            "PASS"
            if average_recall >= 0.95
            and minimum_recall >= 0.95
            and gin_index_used
            and hnsw_index_used
            else "FAIL"
        )
        report = {
            "schema_version": "poc-03.hybrid-retrieval-result.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "status": status,
            "environment": {
                "postgresql_version": str(database_version).split(",")[0],
                "pgvector_version": str(pgvector_version),
            },
            "fusion": {
                "vector_weight": 0.6,
                "full_text_weight": 0.4,
                "candidate_limit_per_channel": 20,
                "hnsw_ef_search": 200,
                "hnsw_m": 32,
                "hnsw_ef_construction": 200,
            },
            "summary": {
                "scenario_count": len(scenario_results),
                "synthetic_record_count": len(records),
                "top_k": 5,
                "average_top5_recall": average_recall,
                "minimum_top5_recall": minimum_recall,
                "gin_index_used": gin_index_used,
                "hnsw_index_used": hnsw_index_used,
            },
            "scenarios": scenario_results,
            "privacy": {
                "customer_content_used": False,
                "query_text_committed": False,
                "vector_values_committed": False,
                "synthetic_rows_persisted": False,
            },
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if status == "PASS" else 1
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS poc03_isolation CASCADE")
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
