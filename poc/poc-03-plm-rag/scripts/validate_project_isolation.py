from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import psycopg


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.project_isolation import (  # noqa: E402
    FULL_TEXT_SQL,
    HYBRID_SQL,
    VECTOR_SQL,
    ProjectRetrievalRequest,
    ProjectScopeError,
    assert_project_isolated,
)


def _query(connection: psycopg.Connection, sql: str, request: ProjectRetrievalRequest):
    with connection.cursor() as cursor:
        cursor.execute(sql, request.parameters)
        return cursor.fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PROJECT/ProjectId isolation.")
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
    query_results: list[dict[str, object]] = []
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
            for project_id, marker in (("PROJECT-A", "alpha"), ("PROJECT-B", "beta")):
                for number in range(1, 21):
                    records.append(
                        (
                            f"{project_id}-{number:02d}",
                            "PROJECT",
                            project_id,
                            f"shared pump assembly {marker} synthetic record {number}",
                            "[1,0,0]",
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
                "CREATE INDEX poc03_isolation_project_idx "
                "ON poc03_isolation.retrieval_document (project_id)"
            )
            cursor.execute(
                "CREATE INDEX poc03_isolation_embedding_idx "
                "ON poc03_isolation.retrieval_document "
                "USING hnsw (embedding vector_cosine_ops)"
            )
            cursor.execute("SELECT version(), extversion FROM pg_extension WHERE extname='vector'")
            database_version, pgvector_version = cursor.fetchone()

        missing_project_id_rejected = False
        try:
            ProjectRetrievalRequest(
                project_id="",
                query_text="shared pump",
                query_vector=(1.0, 0.0, 0.0),
            )
        except ProjectScopeError:
            missing_project_id_rejected = True

        leakage_count = 0
        for project_id in ("PROJECT-A", "PROJECT-B"):
            request = ProjectRetrievalRequest(
                project_id=project_id,
                query_text="shared pump",
                query_vector=(1.0, 0.0, 0.0),
                limit=5,
            )
            for query_type, sql in (
                ("vector", VECTOR_SQL),
                ("full_text", FULL_TEXT_SQL),
                ("hybrid", HYBRID_SQL),
            ):
                rows = _query(connection, sql, request)
                leakage = assert_project_isolated(rows, project_id)
                leakage_count += leakage
                query_results.append(
                    {
                        "project": project_id,
                        "query_type": query_type,
                        "result_count": len(rows),
                        "leakage_count": leakage,
                    }
                )

        injection_request = ProjectRetrievalRequest(
            project_id="PROJECT-A' OR '1'='1",
            query_text="shared pump",
            query_vector=(1.0, 0.0, 0.0),
            limit=5,
        )
        injection_result_count = len(_query(connection, VECTOR_SQL, injection_request))
        status = (
            "PASS"
            if missing_project_id_rejected
            and leakage_count == 0
            and injection_result_count == 0
            and len(query_results) == 6
            and all(item["result_count"] == 5 for item in query_results)
            else "FAIL"
        )
        report = {
            "schema_version": "poc-03.project-isolation-result.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "status": status,
            "environment": {
                "postgresql_version": str(database_version).split(",")[0],
                "pgvector_version": str(pgvector_version),
                "listen_address": args.host,
                "port": args.port,
            },
            "summary": {
                "synthetic_project_count": 2,
                "synthetic_record_count": 40,
                "query_scenario_count": len(query_results),
                "result_row_count": sum(int(item["result_count"]) for item in query_results),
                "cross_project_leakage_count": leakage_count,
                "missing_project_id_rejected": missing_project_id_rejected,
                "parameter_injection_result_count": injection_result_count,
            },
            "query_results": query_results,
            "privacy": {
                "customer_content_used": False,
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
