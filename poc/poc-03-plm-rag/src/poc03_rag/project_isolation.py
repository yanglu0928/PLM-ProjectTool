from __future__ import annotations

from dataclasses import dataclass


class ProjectScopeError(ValueError):
    """Raised when a PROJECT retrieval request has no usable ProjectId."""


@dataclass(frozen=True, slots=True)
class ProjectRetrievalRequest:
    project_id: str
    query_text: str
    query_vector: tuple[float, ...]
    limit: int = 5

    def __post_init__(self) -> None:
        normalized_project_id = self.project_id.strip()
        if not normalized_project_id:
            raise ProjectScopeError("PROJECT retrieval requires project_id")
        if not self.query_text.strip():
            raise ProjectScopeError("query_text is required")
        if not self.query_vector:
            raise ProjectScopeError("query_vector is required")
        if self.limit < 1 or self.limit > 100:
            raise ProjectScopeError("limit must be between 1 and 100")
        object.__setattr__(self, "project_id", normalized_project_id)

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "query_text": self.query_text.strip(),
            "query_vector": "[" + ",".join(str(value) for value in self.query_vector) + "]",
            "limit": self.limit,
        }


VECTOR_SQL = """
SELECT id, project_id, 1 - (embedding <=> %(query_vector)s::vector) AS score
FROM poc03_isolation.retrieval_document
WHERE scope = 'PROJECT' AND project_id = %(project_id)s
ORDER BY embedding <=> %(query_vector)s::vector, id
LIMIT %(limit)s
""".strip()


FULL_TEXT_SQL = """
SELECT id, project_id,
       ts_rank(to_tsvector('simple', body), plainto_tsquery('simple', %(query_text)s)) AS score
FROM poc03_isolation.retrieval_document
WHERE scope = 'PROJECT'
  AND project_id = %(project_id)s
  AND to_tsvector('simple', body) @@ plainto_tsquery('simple', %(query_text)s)
ORDER BY score DESC, id
LIMIT %(limit)s
""".strip()


HYBRID_SQL = """
WITH vector_hits AS (
  SELECT id, project_id, 1 - (embedding <=> %(query_vector)s::vector) AS score
  FROM poc03_isolation.retrieval_document
  WHERE scope = 'PROJECT' AND project_id = %(project_id)s
  ORDER BY embedding <=> %(query_vector)s::vector, id
  LIMIT %(limit)s
), text_hits AS (
  SELECT id, project_id,
         ts_rank(to_tsvector('simple', body), plainto_tsquery('simple', %(query_text)s)) AS score
  FROM poc03_isolation.retrieval_document
  WHERE scope = 'PROJECT'
    AND project_id = %(project_id)s
    AND to_tsvector('simple', body) @@ plainto_tsquery('simple', %(query_text)s)
  ORDER BY score DESC, id
  LIMIT %(limit)s
), combined AS (
  SELECT id, project_id, score * 0.6 AS score FROM vector_hits
  UNION ALL
  SELECT id, project_id, score * 0.4 AS score FROM text_hits
)
SELECT id, project_id, sum(score) AS score
FROM combined
GROUP BY id, project_id
ORDER BY score DESC, id
LIMIT %(limit)s
""".strip()


def assert_project_isolated(rows: list[tuple[object, ...]], project_id: str) -> int:
    leakage = sum(len(row) < 2 or str(row[1]) != project_id for row in rows)
    if leakage:
        raise ProjectScopeError("cross-project retrieval leakage detected")
    return leakage
