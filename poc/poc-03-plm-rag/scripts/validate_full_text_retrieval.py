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

from poc03_rag.project_isolation import FULL_TEXT_SQL, ProjectRetrievalRequest  # noqa: E402
from poc03_rag.retrieval_metrics import top_k_recall  # noqa: E402


SCENARIOS = (
    ("Q01", "产品 结构 管理"),
    ("Q02", "工程 变更 审批"),
    ("Q03", "文档 版本 控制"),
    ("Q04", "物料 编码 规则"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PostgreSQL full-text Top-5.")
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
            for scenario_id, terms in SCENARIOS:
                tokens = terms.split()
                for number in range(1, 6):
                    records.append(
                        (
                            f"{scenario_id}-R-{number:02d}",
                            "PROJECT",
                            "PROJECT-FTS",
                            f"{terms} 标准 能力 合成 记录 {number}",
                            "[1,0,0]",
                        )
                    )
                for number in range(1, 6):
                    records.append(
                        (
                            f"{scenario_id}-D-{number:02d}",
                            "PROJECT",
                            "PROJECT-FTS",
                            f"{tokens[0]} {tokens[1]} 其他 干扰 记录 {number}",
                            "[0,1,0]",
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
                "CREATE INDEX poc03_isolation_body_fts_idx "
                "ON poc03_isolation.retrieval_document "
                "USING gin (to_tsvector('simple', body))"
            )
            cursor.execute("ANALYZE poc03_isolation.retrieval_document")
            cursor.execute("SET enable_seqscan = off")
            cursor.execute("SELECT version()")
            database_version = cursor.fetchone()[0]

        scenario_results = []
        recalls = []
        gin_index_used = True
        for scenario_id, terms in SCENARIOS:
            request = ProjectRetrievalRequest(
                project_id="PROJECT-FTS",
                query_text=terms,
                query_vector=(1.0, 0.0, 0.0),
                limit=5,
            )
            with connection.cursor() as cursor:
                cursor.execute(FULL_TEXT_SQL, request.parameters)
                rows = cursor.fetchall()
                cursor.execute("EXPLAIN " + FULL_TEXT_SQL, request.parameters)
                plan = "\n".join(str(row[0]) for row in cursor.fetchall())
            actual_ids = [str(row[0]) for row in rows]
            expected_ids = [f"{scenario_id}-R-{number:02d}" for number in range(1, 6)]
            recall = top_k_recall(expected_ids, actual_ids, k=5)
            recalls.append(recall)
            gin_index_used = gin_index_used and "poc03_isolation_body_fts_idx" in plan
            scenario_results.append(
                {
                    "scenario_id": scenario_id,
                    "expected_count": len(expected_ids),
                    "result_count": len(actual_ids),
                    "top5_recall": recall,
                }
            )
        average_recall = sum(recalls) / len(recalls)
        minimum_recall = min(recalls)
        status = (
            "PASS"
            if average_recall >= 0.95 and minimum_recall >= 0.95 and gin_index_used
            else "FAIL"
        )
        report = {
            "schema_version": "poc-03.full-text-result.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "status": status,
            "environment": {
                "postgresql_version": str(database_version).split(",")[0],
                "text_search_configuration": "simple",
                "chinese_tokenization": "upstream_whitespace_normalized_terms",
            },
            "summary": {
                "scenario_count": len(scenario_results),
                "synthetic_record_count": len(records),
                "top_k": 5,
                "average_top5_recall": average_recall,
                "minimum_top5_recall": minimum_recall,
                "gin_index_used": gin_index_used,
            },
            "scenarios": scenario_results,
            "privacy": {
                "customer_content_used": False,
                "query_text_committed": False,
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
